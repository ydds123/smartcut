import json
import logging
import random
import re
import subprocess
import time
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from redis import Redis
from rq import Queue, Retry
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.core.telemetry import get_counters_snapshot, increment_counter, log_event
from app.models.models import Scene, Task
from app.schemas.task import (
    ProcessTaskRequest,
    ProcessTaskResponse,
    SaveReviewDataRequest,
    TaskResponse,
)
from app.services.processing_param_specs import build_processing_config_meta
from app.services.file_service import FileService
from app.services.quality_tuning import resolve_quality_config
from app.workers.video_tasks import (
    detect_scenes_for_review,
    process_video_task,
    split_video_after_review,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_redis_conn: Redis | None = None
_queue: Queue | None = None

ACTIVE_STATUSES_BY_OPERATION: dict[str, set[str]] = {
    "process": {"QUEUED", "PROCESSING"},
    "review": {"QUEUED", "DETECTING"},
    "split": {"REVIEW_APPROVED", "SPLITTING"},
}
RQ_ACTIVE_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}


def _get_queue() -> Queue:
    """懒加载 RQ queue，避免模块导入阶段因 Redis 不可用导致服务崩溃。"""
    global _redis_conn, _queue
    if _queue is not None:
        return _queue

    retry_times = max(1, int(getattr(settings, "REDIS_CONNECT_RETRIES", 3)))
    retry_delay_sec = max(0.1, float(getattr(settings, "REDIS_RETRY_DELAY_SEC", 0.5)))
    retry_max_delay_sec = max(
        retry_delay_sec,
        float(getattr(settings, "REDIS_RETRY_MAX_DELAY_SEC", 3.0)),
    )
    last_error: Exception | None = None

    for attempt in range(1, retry_times + 1):
        try:
            conn = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=5,
                health_check_interval=30,
            )
            conn.ping()
            _redis_conn = conn
            _queue = Queue(connection=conn)
            return _queue
        except Exception as exc:  # pragma: no cover - depends on runtime redis state
            last_error = exc
            _redis_conn = None
            _queue = None
            logger.warning(
                "RQ 连接失败（第 %s/%s 次）: %s",
                attempt,
                retry_times,
                exc,
            )
            if isinstance(exc, ValueError):
                break
            if attempt < retry_times:
                backoff_cap = min(retry_max_delay_sec, retry_delay_sec * (2 ** (attempt - 1)))
                time.sleep(random.uniform(0, backoff_cap))

    raise HTTPException(status_code=503, detail=f"Queue unavailable: {last_error}")


def _normalize_idempotency_key(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    trimmed = raw_value.strip()
    if not trimmed:
        return None
    sanitized = re.sub(r"[^a-zA-Z0-9._:-]", "-", trimmed)[:96]
    return sanitized or None


def _build_job_id(task_id: str, operation: str, request: Request) -> tuple[str, bool]:
    idempotency_key = _normalize_idempotency_key(request.headers.get("Idempotency-Key"))
    if idempotency_key:
        return f"task:{task_id}:{operation}:{idempotency_key}", True
    return f"task:{task_id}:{operation}:{uuid4().hex}", False


def _build_retry_policy() -> Retry | None:
    retry_max = max(0, int(getattr(settings, "RQ_JOB_RETRY_MAX", 2)))
    if retry_max <= 0:
        return None
    # 轻量指数退避节奏，避免多 worker 同频重试。
    intervals = [5, 15, 30]
    return Retry(max=retry_max, interval=intervals[: max(1, retry_max)])


def _enqueue_with_dedup(
    queue: Queue,
    *,
    job_id: str,
    func: Any,
    args: list[Any],
    job_timeout: int,
    result_ttl: int,
) -> tuple[Any, bool]:
    existing_job = queue.fetch_job(job_id)
    if existing_job is not None:
        existing_status = (existing_job.get_status(refresh=True) or "").lower()
        if existing_status in RQ_ACTIVE_JOB_STATUSES:
            increment_counter("duplicate_enqueue_detected_total")
            log_event(
                logger,
                logging.INFO,
                "task_enqueue_deduplicated",
                job_id=job_id,
                job_status=existing_status,
            )
            return existing_job, True
        raise HTTPException(
            status_code=409,
            detail="Idempotency key conflicts with a finished job, please retry with a new key",
        )

    try:
        enqueue_kwargs: dict[str, Any] = {
            "job_id": job_id,
            "job_timeout": job_timeout,
            "result_ttl": result_ttl,
        }
        retry_policy = _build_retry_policy()
        if retry_policy is not None:
            enqueue_kwargs["retry"] = retry_policy
        job = queue.enqueue(
            func,
            *args,
            **enqueue_kwargs,
        )
        return job, False
    except Exception:
        existing_job = queue.fetch_job(job_id)
        if existing_job is not None:
            existing_status = (existing_job.get_status(refresh=True) or "").lower()
            if existing_status in RQ_ACTIVE_JOB_STATUSES:
                increment_counter("duplicate_enqueue_detected_total")
                log_event(
                    logger,
                    logging.INFO,
                    "task_enqueue_deduplicated_race",
                    job_id=job_id,
                    job_status=existing_status,
                )
                return existing_job, True
        raise


def _best_effort_cancel_job(queue: Queue, job_id: str) -> None:
    try:
        queue.cancel_job(job_id)
    except Exception:
        logger.debug("best-effort cancel job failed: %s", job_id, exc_info=True)


def _update_task_when_status_matches(
    db: Session,
    *,
    task_id: str,
    expected_statuses: set[str],
    updates: dict[str, Any],
) -> bool:
    rows = (
        db.query(Task)
        .filter(Task.id == task_id, Task.status.in_(tuple(expected_statuses)))
        .update(updates, synchronize_session=False)
    )
    if rows == 1:
        db.commit()
        return True
    db.rollback()
    return False


def _rollback_task_claim(
    db: Session,
    *,
    task_id: str,
    operation: str,
    active_job_id: str,
    rollback_updates: dict[str, Any],
) -> None:
    rows = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.active_operation == operation,
            Task.active_job_id == active_job_id,
        )
        .update(rollback_updates, synchronize_session=False)
    )
    if rows == 1:
        db.commit()
    else:
        db.rollback()


def _build_deduplicated_response(
    task: Task,
    *,
    config_meta: dict[str, Any],
) -> ProcessTaskResponse:
    return {
        "status": task.status,
        "job_id": task.active_job_id,
        "deduplicated": True,
        "resolved_config": _loads_json(task.resolved_config),
        "config_meta": config_meta,
    }


def _limit_task_mutation(request: Request) -> None:
    enforce_rate_limit(
        request,
        "task_mutation",
        max_requests=int(getattr(settings, "RATE_LIMIT_MUTATION_MAX_REQUESTS", 30)),
        window_sec=int(getattr(settings, "RATE_LIMIT_WINDOW_SEC", 60)),
    )


def _resolve_task_preview(task: Task, db: Session) -> str | None:
    """优先使用上传首帧缩略图，其次回退到第一镜头缩略图。"""
    upload_preview_path = Path(settings.UPLOAD_DIR) / f"{task.id}_preview.jpg"
    if upload_preview_path.exists() and upload_preview_path.is_file():
        return FileService.to_public_data_path(str(upload_preview_path))

    first_scene = (
        db.query(Scene.thumbnail_path)
        .filter(Scene.task_id == task.id)
        .order_by(Scene.sequence_index.asc())
        .first()
    )
    if first_scene and first_scene[0]:
        return FileService.to_public_data_path(first_scene[0])

    return None


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _task_to_payload(task: Task, db: Session) -> dict[str, Any]:
    return {
        "id": task.id,
        "display_name": task.display_name,
        "file_path": FileService.to_public_data_path(task.file_path),
        "file_size": task.file_size or 0,
        "duration_ms": task.duration_ms,
        "status": task.status,
        "progress": task.progress or 0,
        "active_operation": task.active_operation,
        "active_job_id": task.active_job_id,
        "total_scenes": task.total_scenes,
        "shots_count": task.total_scenes,
        "preview_thumbnail_path": _resolve_task_preview(task, db),
        "process_mode": task.process_mode,
        "config_profile": task.config_profile,
        "requested_config": _loads_json(task.requested_config),
        "resolved_config": _loads_json(task.resolved_config),
        "quality_flags": _loads_json(task.quality_flags),
        "suspect_segments": _loads_json(task.suspect_segments, default=[]),
        "tuning_history": _loads_json(task.tuning_history, default=[]),
        "review_notes": task.review_notes,
        "latest_split_stats": _loads_json(task.split_stats),
        "detection_result": _loads_json(task.detection_result),
        "user_edited_scenes": _loads_json(task.user_edited_scenes),
        "reviewed_at": task.reviewed_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def _data_root() -> Path:
    return (Path(__file__).resolve().parents[2] / "data").resolve()


def _resolve_local_data_file(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    normalized = path_value.replace("\\", "/").strip()
    if not normalized:
        return None

    root = _data_root()
    candidate: Path
    if normalized.startswith("/data/"):
        candidate = (root / normalized.removeprefix("/data/")).resolve()
    elif normalized.startswith("data/"):
        candidate = (root / normalized.removeprefix("data/")).resolve()
    else:
        raw_path = Path(normalized)
        candidate = raw_path.resolve() if raw_path.is_absolute() else (root / raw_path).resolve()

    if candidate == root or root in candidate.parents:
        return candidate
    return None


def _open_folder_in_file_manager(folder_path: Path) -> None:
    if sys.platform == "darwin":
        cmd = ["open", str(folder_path)]
    elif sys.platform.startswith("win"):
        cmd = ["explorer", str(folder_path)]
    else:
        cmd = ["xdg-open", str(folder_path)]

    subprocess.run(cmd, check=True, capture_output=True, timeout=10)


@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    """获取所有任务列表"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return [_task_to_payload(task, db) for task in tasks]


@router.get("/config/processing-meta")
def get_processing_config_meta():
    """返回参数配置元数据（后端单一事实源）。"""
    return build_processing_config_meta()


@router.get("/metrics/counters")
def get_metrics_counters():
    """返回进程级轻量计数器快照（用于排障与告警接入）。"""
    return {"counters": get_counters_snapshot()}


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """获取单个任务详情"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_payload(task, db)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    """删除任务及相关文件"""
    _limit_task_mutation(request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_dir_path = None
    scene_paths = (
        db.query(Scene.file_path, Scene.thumbnail_path)
        .filter(Scene.task_id == task_id)
        .order_by(Scene.sequence_index)
        .all()
    )

    for file_path, thumbnail_path in scene_paths:
        candidate_path = file_path or thumbnail_path
        if not candidate_path:
            continue

        candidate = Path(candidate_path)
        if candidate.parent.name == "scenes":
            task_dir_path = str(candidate.parent.parent)
        else:
            task_dir_path = str(candidate.parent)
        break

    FileService.delete_task_files(
        task_id,
        task_dir_path=task_dir_path,
        upload_file_path=task.file_path,
    )

    db.delete(task)
    db.commit()

    return {"success": True}


@router.post("/tasks/{task_id}/process", response_model=ProcessTaskResponse)
def process_task(
    task_id: str,
    http_request: Request,
    payload: ProcessTaskRequest = Body(default_factory=ProcessTaskRequest),
    db: Session = Depends(get_db),
):
    """开始处理任务（仅支持手动参数模式）。"""
    _limit_task_mutation(http_request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    config_meta = build_processing_config_meta()
    if task.status != "PENDING":
        if (
            task.active_operation == "process"
            and task.active_job_id
            and task.status in ACTIVE_STATUSES_BY_OPERATION["process"]
        ):
            increment_counter("duplicate_enqueue_detected_total")
            return _build_deduplicated_response(task, config_meta=config_meta)
        raise HTTPException(status_code=409, detail="Task already processed")

    queue = _get_queue()
    job_id, _job_idempotent = _build_job_id(task_id, "process", http_request)

    override_config = _to_dict(payload.override_config) if payload.override_config else None
    try:
        resolved_config, metadata = resolve_quality_config(
            video_path=task.file_path,
            mode=payload.mode,
            profile=payload.profile,
            override_config=override_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    claimed = _update_task_when_status_matches(
        db,
        task_id=task_id,
        expected_statuses={"PENDING"},
        updates={
            "status": "QUEUED",
            "active_operation": "process",
            "active_job_id": job_id,
            "process_mode": payload.mode,
            "config_profile": payload.profile,
            "requested_config": _to_json(override_config or {}),
            "resolved_config": _to_json(resolved_config),
            "quality_flags": None,
            "suspect_segments": None,
            "tuning_history": _to_json(
                [
                    {
                        "stage": "resolve",
                        "metadata": metadata,
                    }
                ]
            ),
            "split_stats": None,
        },
    )

    if not claimed:
        latest = db.query(Task).filter(Task.id == task_id).first()
        if (
            latest
            and latest.active_operation == "process"
            and latest.active_job_id
            and latest.status in ACTIVE_STATUSES_BY_OPERATION["process"]
        ):
            increment_counter("duplicate_enqueue_detected_total")
            return _build_deduplicated_response(latest, config_meta=config_meta)
        raise HTTPException(status_code=409, detail="Task already processed")

    try:
        job, deduplicated = _enqueue_with_dedup(
            queue,
            job_id=job_id,
            func=process_video_task,
            args=[task_id, task.file_path, resolved_config],
            job_timeout=600,
            result_ttl=3600,
        )
    except HTTPException:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="process",
            active_job_id=job_id,
            rollback_updates={
                "status": "PENDING",
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.WARNING,
            "task_enqueue_failed_rollback",
            task_id=task_id,
            operation="process",
            job_id=job_id,
        )
        raise
    except Exception as exc:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="process",
            active_job_id=job_id,
            rollback_updates={
                "status": "PENDING",
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.ERROR,
            "task_enqueue_exception_rollback",
            task_id=task_id,
            operation="process",
            job_id=job_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(exc)}") from exc

    log_event(
        logger,
        logging.INFO,
        "task_enqueued",
        task_id=task_id,
        operation="process",
        job_id=job.id,
        deduplicated=bool(deduplicated),
    )
    return {
        "status": "QUEUED",
        "job_id": job.id,
        "deduplicated": bool(deduplicated),
        "resolved_config": resolved_config,
        "config_meta": config_meta,
    }


@router.get("/tasks/{task_id}/result")
def get_task_result(task_id: str, db: Session = Depends(get_db)):
    """获取任务结果（镜头列表）"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scenes = db.query(Scene).filter(Scene.task_id == task_id).order_by(Scene.sequence_index).all()
    payload = _task_to_payload(task, db)

    return {
        **payload,
        "scenes": [
            {
                "id": scene.id,
                "task_id": scene.task_id,
                "sequence_index": scene.sequence_index,
                "start_ms": scene.start_ms,
                "end_ms": scene.end_ms,
                "file_path": FileService.to_public_data_path(scene.file_path),
                "thumbnail_path": FileService.to_public_data_path(scene.thumbnail_path),
            }
            for scene in scenes
        ],
    }


@router.post("/tasks/{task_id}/review", response_model=ProcessTaskResponse)
def start_review(
    task_id: str,
    http_request: Request,
    payload: ProcessTaskRequest = Body(default_factory=ProcessTaskRequest),
    db: Session = Depends(get_db),
):
    """入队场景检测任务（预览确认流程第一步）。"""
    _limit_task_mutation(http_request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    config_meta = build_processing_config_meta()
    if task.status != "PENDING":
        if (
            task.active_operation == "review"
            and task.active_job_id
            and task.status in ACTIVE_STATUSES_BY_OPERATION["review"]
        ):
            increment_counter("duplicate_enqueue_detected_total")
            return _build_deduplicated_response(task, config_meta=config_meta)
        raise HTTPException(status_code=409, detail="Task already processed")

    queue = _get_queue()
    job_id, _job_idempotent = _build_job_id(task_id, "review", http_request)

    override_config = _to_dict(payload.override_config) if payload.override_config else None
    try:
        resolved_config, _metadata = resolve_quality_config(
            video_path=task.file_path,
            mode=payload.mode,
            profile=payload.profile,
            override_config=override_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    claimed = _update_task_when_status_matches(
        db,
        task_id=task_id,
        expected_statuses={"PENDING"},
        updates={
            "status": "QUEUED",
            "active_operation": "review",
            "active_job_id": job_id,
            "process_mode": payload.mode,
            "config_profile": payload.profile,
            "requested_config": _to_json(override_config or {}),
            "resolved_config": _to_json(resolved_config),
            "split_stats": None,
        },
    )

    if not claimed:
        latest = db.query(Task).filter(Task.id == task_id).first()
        if (
            latest
            and latest.active_operation == "review"
            and latest.active_job_id
            and latest.status in ACTIVE_STATUSES_BY_OPERATION["review"]
        ):
            increment_counter("duplicate_enqueue_detected_total")
            return _build_deduplicated_response(latest, config_meta=config_meta)
        raise HTTPException(status_code=409, detail="Task already processed")

    try:
        job, deduplicated = _enqueue_with_dedup(
            queue,
            job_id=job_id,
            func=detect_scenes_for_review,
            args=[task_id, task.file_path, resolved_config],
            job_timeout=300,
            result_ttl=3600,
        )
    except HTTPException:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="review",
            active_job_id=job_id,
            rollback_updates={
                "status": "PENDING",
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.WARNING,
            "task_enqueue_failed_rollback",
            task_id=task_id,
            operation="review",
            job_id=job_id,
        )
        raise
    except Exception as exc:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="review",
            active_job_id=job_id,
            rollback_updates={
                "status": "PENDING",
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.ERROR,
            "task_enqueue_exception_rollback",
            task_id=task_id,
            operation="review",
            job_id=job_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(exc)}") from exc

    log_event(
        logger,
        logging.INFO,
        "task_enqueued",
        task_id=task_id,
        operation="review",
        job_id=job.id,
        deduplicated=bool(deduplicated),
    )
    return {
        "status": "QUEUED",
        "job_id": job.id,
        "deduplicated": bool(deduplicated),
        "resolved_config": resolved_config,
        "config_meta": config_meta,
    }


@router.get("/tasks/{task_id}/review-data")
def get_review_data(task_id: str, db: Session = Depends(get_db)):
    """返回检测结果（供 ReviewModal 展示）。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("REVIEW_PENDING", "REVIEW_APPROVED", "SPLITTING", "TIMELINE_READY"):
        raise HTTPException(status_code=409, detail="Review data not available")

    detection = _loads_json(task.detection_result) or {}
    user_edited = _loads_json(task.user_edited_scenes)
    return {
        "task_id": task_id,
        "detection_result": detection,
        "user_edited_scenes": user_edited,
        "status": task.status,
    }


@router.put("/tasks/{task_id}/review-data")
def save_review_data(
    task_id: str,
    request: Request,
    body: SaveReviewDataRequest = Body(...),
    db: Session = Depends(get_db),
):
    """保存用户编辑后的场景列表。"""
    _limit_task_mutation(request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("REVIEW_PENDING", "REVIEW_APPROVED", "TIMELINE_READY"):
        raise HTTPException(status_code=409, detail="Cannot edit in current status")

    normalized_scenes = [
        {
            "start_ms": int(scene.start_ms),
            "end_ms": int(scene.end_ms),
        }
        for scene in body.scenes
    ]

    for index in range(1, len(normalized_scenes)):
        previous = normalized_scenes[index - 1]
        current = normalized_scenes[index]
        if current["start_ms"] < previous["start_ms"]:
            raise HTTPException(status_code=400, detail="scenes must be sorted by start_ms")
        if current["start_ms"] < previous["end_ms"]:
            raise HTTPException(status_code=400, detail=f"scenes overlap at index={index}")

    task.user_edited_scenes = _to_json(normalized_scenes)
    db.commit()
    return {"success": True}


@router.post("/tasks/{task_id}/review/reset-from-timeline")
def reset_review_data_from_timeline(task_id: str, request: Request, db: Session = Depends(get_db)):
    """将审核页草稿重置为当前时间轴切分结果，避免返回编辑时镜头数不一致。"""
    _limit_task_mutation(request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "TIMELINE_READY":
        raise HTTPException(status_code=409, detail="Task not in TIMELINE_READY state")

    timeline_scenes = (
        db.query(Scene.start_ms, Scene.end_ms)
        .filter(Scene.task_id == task_id)
        .order_by(Scene.sequence_index.asc())
        .all()
    )
    if not timeline_scenes:
        raise HTTPException(status_code=409, detail="No timeline scenes available")

    normalized_scenes = [
        {"start_ms": int(start_ms), "end_ms": int(end_ms)}
        for start_ms, end_ms in timeline_scenes
    ]
    task.user_edited_scenes = _to_json(normalized_scenes)
    task.total_scenes = len(normalized_scenes)
    db.commit()

    return {
        "success": True,
        "scenes_count": len(normalized_scenes),
        "source": "timeline_scenes",
    }


@router.post("/tasks/{task_id}/approve")
def approve_review(task_id: str, request: Request, db: Session = Depends(get_db)):
    """用户确认场景，入队切分任务。"""
    _limit_task_mutation(request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if (
        task.active_operation == "split"
        and task.active_job_id
        and task.status in ACTIVE_STATUSES_BY_OPERATION["split"]
    ):
        increment_counter("duplicate_enqueue_detected_total")
        return {
            "status": task.status,
            "job_id": task.active_job_id,
            "deduplicated": True,
        }
    if task.status not in ("REVIEW_PENDING", "TIMELINE_READY"):
        raise HTTPException(status_code=409, detail=f"Task cannot be approved in current state (current={task.status})")

    previous_status = task.status
    previous_reviewed_at = task.reviewed_at
    queue = _get_queue()
    job_id, _job_idempotent = _build_job_id(task_id, "split", request)

    claimed = _update_task_when_status_matches(
        db,
        task_id=task_id,
        expected_statuses={"REVIEW_PENDING", "TIMELINE_READY"},
        updates={
            "status": "REVIEW_APPROVED",
            "reviewed_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "split_stats": None,
            "active_operation": "split",
            "active_job_id": job_id,
        },
    )
    if not claimed:
        latest = db.query(Task).filter(Task.id == task_id).first()
        if (
            latest
            and latest.active_operation == "split"
            and latest.active_job_id
            and latest.status in ACTIVE_STATUSES_BY_OPERATION["split"]
        ):
            increment_counter("duplicate_enqueue_detected_total")
            return {
                "status": latest.status,
                "job_id": latest.active_job_id,
                "deduplicated": True,
            }
        raise HTTPException(status_code=409, detail=f"Task cannot be approved in current state (current={latest.status if latest else 'unknown'})")

    try:
        job, deduplicated = _enqueue_with_dedup(
            queue,
            job_id=job_id,
            func=split_video_after_review,
            args=[task_id],
            job_timeout=600,
            result_ttl=3600,
        )
    except HTTPException:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="split",
            active_job_id=job_id,
            rollback_updates={
                "status": previous_status,
                "reviewed_at": previous_reviewed_at,
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.WARNING,
            "task_enqueue_failed_rollback",
            task_id=task_id,
            operation="split",
            job_id=job_id,
        )
        raise
    except Exception as exc:
        _rollback_task_claim(
            db,
            task_id=task_id,
            operation="split",
            active_job_id=job_id,
            rollback_updates={
                "status": previous_status,
                "reviewed_at": previous_reviewed_at,
                "active_operation": None,
                "active_job_id": None,
            },
        )
        log_event(
            logger,
            logging.ERROR,
            "task_enqueue_exception_rollback",
            task_id=task_id,
            operation="split",
            job_id=job_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Failed to queue split: {str(exc)}") from exc

    log_event(
        logger,
        logging.INFO,
        "task_enqueued",
        task_id=task_id,
        operation="split",
        job_id=job.id,
        deduplicated=bool(deduplicated),
    )
    return {"status": "REVIEW_APPROVED", "job_id": job.id, "deduplicated": bool(deduplicated)}


@router.post("/tasks/{task_id}/return-to-review")
def return_to_review(task_id: str, request: Request, db: Session = Depends(get_db)):
    """从 TIMELINE_READY 返回到 REVIEW_PENDING，删除已切分文件。"""
    _limit_task_mutation(request)

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "TIMELINE_READY":
        raise HTTPException(status_code=409, detail="Task not in TIMELINE_READY state")

    try:
        FileService.delete_split_assets(task_id)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "return_to_review_cleanup_failed",
            task_id=task_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Failed to cleanup split assets: {exc}") from exc

    rows = (
        db.query(Task)
        .filter(Task.id == task_id, Task.status == "TIMELINE_READY")
        .update(
            {
                "status": "REVIEW_PENDING",
                "total_scenes": None,
                "active_operation": None,
                "active_job_id": None,
            },
            synchronize_session=False,
        )
    )
    if rows != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Task not in TIMELINE_READY state")

    db.query(Scene).filter(Scene.task_id == task_id).delete()
    db.commit()
    log_event(
        logger,
        logging.INFO,
        "return_to_review_completed",
        task_id=task_id,
    )
    return {"success": True}


@router.post("/tasks/{task_id}/scenes/{scene_id}/open-folder")
def open_scene_folder(task_id: str, scene_id: str, db: Session = Depends(get_db)):
    """在系统文件管理器中打开指定切片所在目录。"""
    scene = db.query(Scene).filter(Scene.task_id == task_id, Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    if not scene.file_path:
        raise HTTPException(status_code=409, detail="Scene file path unavailable")

    clip_path = _resolve_local_data_file(scene.file_path)
    if not clip_path:
        raise HTTPException(status_code=400, detail="Invalid scene file path")
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Scene file not found")

    folder_path = clip_path if clip_path.is_dir() else clip_path.parent
    try:
        _open_folder_in_file_manager(folder_path)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Open folder timed out") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (
            exc.stderr.decode(errors="ignore")
            if isinstance(exc.stderr, bytes)
            else str(exc.stderr or "")
        )
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {stderr}") from exc

    return {"success": True, "folder_path": str(folder_path)}


@router.get("/tasks/{task_id}/frame")
def get_frame(
    task_id: str,
    t: int = Query(..., description="时间点（毫秒）"),
    db: Session = Depends(get_db),
):
    """从原始视频提取指定时间点的帧，用于时间轴缩略图。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    video_path = Path(task.file_path)
    if not video_path.is_absolute():
        upload_dir = Path(settings.UPLOAD_DIR).resolve()
        video_path = upload_dir.parent.parent / task.file_path
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    t_sec = t / 1000.0
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(t_sec),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "5",
            "-vf", "scale=160:-1",
            str(tmp_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size <= 0:
            raise HTTPException(status_code=500, detail="Frame extraction failed")

        data = tmp_path.read_bytes()
        return Response(content=data, media_type="image/jpeg")
    finally:
        tmp_path.unlink(missing_ok=True)
