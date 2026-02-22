import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Scene, Task
from app.schemas.task import ProcessTaskRequest, ProcessTaskResponse, TaskResponse
from app.services.file_service import FileService
from app.services.quality_tuning import resolve_quality_config
from app.workers.video_tasks import (
    detect_scenes_for_review,
    process_video_task,
    split_video_after_review,
)

router = APIRouter()

# RQ 队列
redis_conn = Redis.from_url(settings.REDIS_URL)
queue = Queue(connection=redis_conn)


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
        "file_path": task.file_path,
        "file_size": task.file_size or 0,
        "status": task.status,
        "progress": task.progress or 0,
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


@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    """获取所有任务列表"""
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
    return [_task_to_payload(task, db) for task in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """获取单个任务详情"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_payload(task, db)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """删除任务及相关文件"""
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

    FileService.delete_task_files(task_id, task_dir_path=task_dir_path)

    db.delete(task)
    db.commit()

    return {"success": True}


@router.post("/tasks/{task_id}/process", response_model=ProcessTaskResponse)
def process_task(
    task_id: str,
    request: ProcessTaskRequest = Body(default_factory=ProcessTaskRequest),
    db: Session = Depends(get_db),
):
    """开始处理任务（仅支持手动参数模式）。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "PENDING":
        raise HTTPException(status_code=409, detail="Task already processed")

    override_config = _to_dict(request.override_config) if request.override_config else None
    try:
        resolved_config, metadata = resolve_quality_config(
            video_path=task.file_path,
            mode=request.mode,
            profile=request.profile,
            override_config=override_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task.status = "QUEUED"
    task.process_mode = request.mode
    task.config_profile = request.profile
    task.requested_config = _to_json(override_config or {})
    task.resolved_config = _to_json(resolved_config)
    task.quality_flags = None
    task.suspect_segments = None
    task.tuning_history = _to_json([
        {
            "stage": "resolve",
            "metadata": metadata,
        }
    ])
    db.commit()

    try:
        job = queue.enqueue(
            process_video_task,
            task_id,
            task.file_path,
            resolved_config,
            job_timeout=600,
            result_ttl=3600,
        )
        return {
            "status": "QUEUED",
            "job_id": job.id,
            "resolved_config": resolved_config,
        }
    except Exception as exc:
        task.status = "PENDING"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(exc)}")


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


@router.post("/tasks/{task_id}/review")
def start_review(
    task_id: str,
    request: ProcessTaskRequest = Body(default_factory=ProcessTaskRequest),
    db: Session = Depends(get_db),
):
    """入队场景检测任务（预览确认流程第一步）。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "PENDING":
        raise HTTPException(status_code=409, detail="Task already processed")

    override_config = _to_dict(request.override_config) if request.override_config else None
    try:
        resolved_config, metadata = resolve_quality_config(
            video_path=task.file_path,
            mode=request.mode,
            profile=request.profile,
            override_config=override_config,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    task.status = "QUEUED"
    task.process_mode = request.mode
    task.config_profile = request.profile
    task.requested_config = _to_json(override_config or {})
    task.resolved_config = _to_json(resolved_config)
    db.commit()

    try:
        job = queue.enqueue(
            detect_scenes_for_review,
            task_id,
            task.file_path,
            resolved_config,
            job_timeout=300,
            result_ttl=3600,
        )
        return {"status": "QUEUED", "job_id": job.id}
    except Exception as exc:
        task.status = "PENDING"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(exc)}")


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
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """保存用户编辑后的场景列表。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("REVIEW_PENDING", "REVIEW_APPROVED", "TIMELINE_READY"):
        raise HTTPException(status_code=409, detail="Cannot edit in current status")

    scenes = body.get("scenes")
    if not isinstance(scenes, list):
        raise HTTPException(status_code=400, detail="scenes must be a list")

    task.user_edited_scenes = _to_json(scenes)
    db.commit()
    return {"success": True}


@router.post("/tasks/{task_id}/approve")
def approve_review(task_id: str, db: Session = Depends(get_db)):
    """用户确认场景，入队切分任务。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "REVIEW_PENDING":
        raise HTTPException(status_code=409, detail=f"Task not in REVIEW_PENDING state (current={task.status})")

    task.status = "REVIEW_APPROVED"
    task.reviewed_at = datetime.utcnow()
    db.commit()

    try:
        job = queue.enqueue(
            split_video_after_review,
            task_id,
            job_timeout=600,
            result_ttl=3600,
        )
        return {"status": "REVIEW_APPROVED", "job_id": job.id}
    except Exception as exc:
        task.status = "REVIEW_PENDING"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue split: {str(exc)}")


@router.post("/tasks/{task_id}/finalize")
def finalize_task(task_id: str, db: Session = Depends(get_db)):
    """用户点击「完成」，将 TIMELINE_READY 状态推进为 COMPLETED。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "TIMELINE_READY":
        raise HTTPException(status_code=409, detail="Task not in TIMELINE_READY state")

    task.status = "COMPLETED"
    db.commit()
    return {"success": True}


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
