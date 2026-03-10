from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from redis import Redis
from rq import Queue, Retry
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import ANALYSIS_API_KEY_ENV_VAR, BACKEND_ENV_FILE, settings
from app.core.telemetry import increment_counter, log_event
from app.models.models import AnalysisRun, AnalysisSettings, Task
from app.services.analysis_gemini import GeminiAPIError
from app.services.analysis_provider import (
    AnalysisProviderAdapter,
    build_analysis_provider_adapter,
    get_supported_analysis_providers,
)

logger = logging.getLogger(__name__)

ANALYSIS_API_KEY_SOURCE_DOTENV_FILE = "dotenv_file"
ANALYSIS_API_KEY_SOURCE_PROCESS_ENV = "process_env"
ANALYSIS_API_KEY_SOURCE_MISSING = "missing"

ANALYSIS_TYPE_STORY_INTRO = "story_intro"
ANALYSIS_STATUS_QUEUED = "QUEUED"
ANALYSIS_STATUS_RUNNING = "RUNNING"
ANALYSIS_STATUS_SUCCEEDED = "SUCCEEDED"
ANALYSIS_STATUS_FAILED = "FAILED"
ANALYSIS_ACTIVE_STATUSES = {ANALYSIS_STATUS_QUEUED, ANALYSIS_STATUS_RUNNING}
RQ_ACTIVE_JOB_STATUSES = {"queued", "started", "deferred", "scheduled"}

_analysis_redis_conn: Redis | None = None
_analysis_queue: Queue | None = None


@dataclass(frozen=True)
class AnalysisApiKeyInfo:
    has_api_key: bool
    source: str
    env_file_path: Path
    env_file_exists: bool
    env_variable_name: str = ANALYSIS_API_KEY_ENV_VAR


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _from_json(raw: str | None, default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _allowed_models() -> set[str]:
    raw = (getattr(settings, "ANALYSIS_ALLOWED_MODELS", "") or "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def get_analysis_env_file_path() -> Path:
    configured = getattr(settings, "analysis_env_file_path", None)
    if isinstance(configured, Path):
        return configured.resolve()
    if isinstance(configured, str) and configured.strip():
        return Path(configured).resolve()
    return BACKEND_ENV_FILE


def resolve_analysis_api_key_source() -> str:
    source = (getattr(settings, "analysis_api_key_source", "") or "").strip()
    if source in {
        ANALYSIS_API_KEY_SOURCE_DOTENV_FILE,
        ANALYSIS_API_KEY_SOURCE_PROCESS_ENV,
        ANALYSIS_API_KEY_SOURCE_MISSING,
    }:
        return source
    if (getattr(settings, "ANALYSIS_API_KEY", "") or "").strip():
        return ANALYSIS_API_KEY_SOURCE_PROCESS_ENV
    return ANALYSIS_API_KEY_SOURCE_MISSING


def get_analysis_api_key_info() -> AnalysisApiKeyInfo:
    env_file_path = get_analysis_env_file_path()
    return AnalysisApiKeyInfo(
        has_api_key=bool((getattr(settings, "ANALYSIS_API_KEY", "") or "").strip()),
        source=resolve_analysis_api_key_source(),
        env_file_path=env_file_path,
        env_file_exists=env_file_path.is_file(),
    )


def can_open_env_file_on_platform() -> bool:
    if sys.platform == "darwin":
        return shutil.which("open") is not None
    if sys.platform.startswith("linux"):
        return shutil.which("xdg-open") is not None
    return callable(getattr(os, "startfile", None))


def open_analysis_env_file() -> tuple[bool, str]:
    key_info = get_analysis_api_key_info()
    env_file_path = key_info.env_file_path
    if not key_info.env_file_exists:
        return False, "推荐配置文件不存在，请先创建 backend/.env"
    if not can_open_env_file_on_platform():
        return False, "当前运行环境不支持自动打开配置文件"

    try:
        if sys.platform == "darwin":
            command = shutil.which("open")
            if not command:
                return False, "系统未提供 open 命令"
            subprocess.run(
                [command, str(env_file_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform.startswith("linux"):
            command = shutil.which("xdg-open")
            if not command:
                return False, "系统未提供 xdg-open 命令"
            subprocess.run(
                [command, str(env_file_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            startfile = getattr(os, "startfile", None)
            if not callable(startfile):
                return False, "当前运行环境不支持自动打开配置文件"
            startfile(str(env_file_path))
    except Exception as exc:
        return False, f"打开配置文件失败：{exc}"

    return True, "已打开配置文件"


def _build_latest_not_started_payload(
    *,
    task_id: str,
    settings_model: AnalysisSettings,
    is_configured: bool,
    has_key: bool,
) -> dict[str, Any]:
    key_info = get_analysis_api_key_info()
    return {
        "task_id": task_id,
        "analysis_type": ANALYSIS_TYPE_STORY_INTRO,
        "status": "NOT_CONFIGURED" if not is_configured else "NOT_STARTED",
        "run_id": None,
        "is_configured": is_configured,
        "has_api_key": has_key,
        "api_key_source": key_info.source,
        "can_retry": bool(is_configured),
        "provider": settings_model.provider,
        "model": settings_model.model,
        "story_intro_markdown": None,
        "summary": None,
        "error_message": None,
        "retry_count": 0,
        "created_at": None,
        "updated_at": settings_model.updated_at,
        "finished_at": None,
    }


def _get_queue() -> Queue:
    global _analysis_redis_conn, _analysis_queue
    if _analysis_queue is not None:
        return _analysis_queue

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
            _analysis_redis_conn = conn
            _analysis_queue = Queue(connection=conn)
            return _analysis_queue
        except Exception as exc:  # pragma: no cover - runtime state dependent
            last_error = exc
            _analysis_redis_conn = None
            _analysis_queue = None
            if attempt < retry_times:
                backoff_cap = min(retry_max_delay_sec, retry_delay_sec * (2 ** (attempt - 1)))
                time.sleep(random.uniform(0, backoff_cap))

    raise RuntimeError(f"Analysis queue unavailable: {last_error}")


def _build_retry_policy() -> Retry | None:
    retry_max = max(0, int(getattr(settings, "RQ_JOB_RETRY_MAX", 2)))
    if retry_max <= 0:
        return None
    intervals = [5, 15, 30]
    return Retry(max=retry_max, interval=intervals[: max(1, retry_max)])


def has_analysis_api_key() -> bool:
    return get_analysis_api_key_info().has_api_key


def get_or_create_analysis_settings(db: Session) -> AnalysisSettings:
    model = (
        db.query(AnalysisSettings)
        .filter(AnalysisSettings.id == "default")
        .first()
    )
    if model:
        return model

    model = AnalysisSettings(
        id="default",
        provider=getattr(settings, "ANALYSIS_PROVIDER_DEFAULT", "gemini"),
        base_url=getattr(settings, "ANALYSIS_BASE_URL_DEFAULT", "https://generativelanguage.googleapis.com"),
        model=getattr(settings, "ANALYSIS_MODEL_DEFAULT", "gemini-3.1-flash-lite-preview"),
        prompt_template=getattr(settings, "ANALYSIS_PROMPT_TEMPLATE_DEFAULT", ""),
        analysis_enabled=bool(getattr(settings, "ANALYSIS_ENABLED_DEFAULT", False)),
        request_timeout_sec=max(10, int(getattr(settings, "ANALYSIS_REQUEST_TIMEOUT_SEC_DEFAULT", 180))),
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent_model = (
            db.query(AnalysisSettings)
            .filter(AnalysisSettings.id == "default")
            .first()
        )
        if concurrent_model is not None:
            return concurrent_model
        raise
    db.refresh(model)
    return model


def upsert_analysis_settings(db: Session, payload: dict[str, Any]) -> AnalysisSettings:
    model = get_or_create_analysis_settings(db)
    model.provider = (payload.get("provider") or model.provider or "gemini").strip()
    model.base_url = (payload.get("base_url") or model.base_url or "").strip()
    model.model = (payload.get("model") or model.model or "").strip()
    model.prompt_template = payload.get("prompt_template") if isinstance(payload.get("prompt_template"), str) else (model.prompt_template or "")
    model.analysis_enabled = bool(payload.get("analysis_enabled", model.analysis_enabled))
    if payload.get("request_timeout_sec") is not None:
        model.request_timeout_sec = max(10, min(900, int(payload["request_timeout_sec"])))
    model.updated_at = utc_now_naive()
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def evaluate_settings_completeness(
    settings_model: AnalysisSettings,
    *,
    has_api_key: bool,
    require_enabled: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not (settings_model.provider or "").strip():
        reasons.append("provider 未配置")
    if not (settings_model.base_url or "").strip():
        reasons.append("访问地址未配置")
    if not (settings_model.model or "").strip():
        reasons.append("model 未配置")
    if not (settings_model.prompt_template or "").strip():
        reasons.append("提示词未配置")
    if not has_api_key:
        reasons.append("服务端未配置 ANALYSIS_API_KEY")
    if require_enabled and not settings_model.analysis_enabled:
        reasons.append("自动分析未开启")
    return len(reasons) == 0, reasons


def settings_to_response(
    settings_model: AnalysisSettings,
    *,
    expose_env_file_path: bool,
    can_open_env_file: bool,
) -> dict[str, Any]:
    key_info = get_analysis_api_key_info()
    has_key = key_info.has_api_key
    is_complete, reasons = evaluate_settings_completeness(
        settings_model,
        has_api_key=has_key,
        require_enabled=False,
    )
    return {
        "provider": settings_model.provider,
        "base_url": settings_model.base_url,
        "model": settings_model.model,
        "prompt_template": settings_model.prompt_template,
        "analysis_enabled": bool(settings_model.analysis_enabled),
        "request_timeout_sec": int(settings_model.request_timeout_sec or 180),
        "has_api_key": has_key,
        "api_key_source": key_info.source,
        "env_file_path": str(key_info.env_file_path) if expose_env_file_path else None,
        "env_file_exists": key_info.env_file_exists,
        "can_open_env_file": can_open_env_file,
        "env_variable_name": key_info.env_variable_name,
        "is_complete": is_complete,
        "incomplete_reasons": reasons,
        "updated_at": settings_model.updated_at,
    }


def _check_admission(task: Task, settings_model: AnalysisSettings, *, require_enabled: bool) -> tuple[bool, str | None]:
    has_key = has_analysis_api_key()
    complete, reasons = evaluate_settings_completeness(
        settings_model,
        has_api_key=has_key,
        require_enabled=require_enabled,
    )
    if not complete:
        return False, "；".join(reasons)

    provider = (settings_model.provider or "").strip().lower()
    supported = get_supported_analysis_providers()
    if provider not in supported:
        supported_text = ", ".join(sorted(supported)) if supported else "none"
        return False, f"当前 provider 暂不支持：{settings_model.provider}（支持: {supported_text}）"

    base_url = (settings_model.base_url or "").strip().lower()
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        return False, "base_url 必须以 http:// 或 https:// 开头"

    timeout_sec = int(settings_model.request_timeout_sec or 180)
    if timeout_sec < 10 or timeout_sec > 900:
        return False, "request_timeout_sec 必须在 10-900 秒之间"

    allowed_models = _allowed_models()
    if allowed_models and settings_model.model not in allowed_models:
        return False, f"model 不在允许列表内：{settings_model.model}"

    max_size_bytes = max(1, int(getattr(settings, "ANALYSIS_MAX_VIDEO_SIZE_MB", 512))) * 1024 * 1024
    if task.file_size and int(task.file_size) > max_size_bytes:
        return False, f"视频体积超限（>{int(getattr(settings, 'ANALYSIS_MAX_VIDEO_SIZE_MB', 512))}MB）"

    max_duration_ms = max(1, int(getattr(settings, "ANALYSIS_MAX_VIDEO_DURATION_SEC", 1800))) * 1000
    if task.duration_ms and int(task.duration_ms) > max_duration_ms:
        return False, f"视频时长超限（>{int(getattr(settings, 'ANALYSIS_MAX_VIDEO_DURATION_SEC', 1800))}秒）"

    return True, None


def get_latest_analysis_run(
    db: Session,
    *,
    task_id: str,
    analysis_type: str = ANALYSIS_TYPE_STORY_INTRO,
) -> AnalysisRun | None:
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.task_id == task_id, AnalysisRun.analysis_type == analysis_type)
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )


def get_active_analysis_run(
    db: Session,
    *,
    task_id: str,
    analysis_type: str = ANALYSIS_TYPE_STORY_INTRO,
) -> AnalysisRun | None:
    return (
        db.query(AnalysisRun)
        .filter(
            AnalysisRun.task_id == task_id,
            AnalysisRun.analysis_type == analysis_type,
            AnalysisRun.status.in_(tuple(ANALYSIS_ACTIVE_STATUSES)),
        )
        .order_by(AnalysisRun.created_at.desc())
        .first()
    )


def _is_rq_job_active(job_id: str) -> bool | None:
    try:
        queue = _get_queue()
    except Exception:
        return None
    existing_job = queue.fetch_job(job_id)
    if existing_job is None:
        return False
    status = (existing_job.get_status(refresh=True) or "").lower()
    return status in RQ_ACTIVE_JOB_STATUSES


def _stale_queued_grace_seconds() -> int:
    return max(5, int(getattr(settings, "ANALYSIS_STALE_QUEUED_GRACE_SEC", 20)))


def _release_stale_active_run(
    db: Session,
    *,
    run: AnalysisRun,
    source: str,
) -> None:
    run.status = ANALYSIS_STATUS_FAILED
    stale_reason = "检测到队列中不存在对应活跃作业，系统自动释放卡住的分析任务"
    if (run.error_message or "").strip():
        run.error_message = f"{run.error_message}；{stale_reason}"
    else:
        run.error_message = stale_reason
    run.finished_at = utc_now_naive()
    run.updated_at = utc_now_naive()
    db.add(run)
    db.commit()

    increment_counter("analysis_failed_total")
    log_event(
        logger,
        logging.WARNING,
        "analysis_stale_active_run_released",
        source=source,
        task_id=run.task_id,
        run_id=run.id,
        provider=run.provider_snapshot,
        model=run.model_snapshot,
        retry_count=run.retry_count,
    )


def _recover_active_run_if_needed(
    db: Session,
    *,
    run: AnalysisRun,
    source: str,
) -> AnalysisRun | None:
    if run.status not in ANALYSIS_ACTIVE_STATUSES:
        return run

    is_job_active = _is_rq_job_active(run.id)
    if is_job_active is None:
        return run
    if is_job_active:
        return run

    if run.status == ANALYSIS_STATUS_QUEUED:
        now = utc_now_naive()
        baseline = run.updated_at or run.created_at or now
        age_sec = max(0.0, (now - baseline).total_seconds())
        if age_sec < _stale_queued_grace_seconds():
            # Avoid false stale-release in the commit->enqueue race window.
            return run

    _release_stale_active_run(db, run=run, source=source)
    return None


def get_recoverable_active_analysis_run(
    db: Session,
    *,
    task_id: str,
    source: str,
) -> AnalysisRun | None:
    active = get_active_analysis_run(db, task_id=task_id)
    if active is None:
        return None

    return _recover_active_run_if_needed(db, run=active, source=source)


def create_analysis_run(
    db: Session,
    *,
    task_id: str,
    settings_model: AnalysisSettings,
    status: str,
    retry_count: int = 0,
    error_message: str | None = None,
) -> tuple[AnalysisRun, bool]:
    run = AnalysisRun(
        id=str(uuid4()),
        task_id=task_id,
        analysis_type=ANALYSIS_TYPE_STORY_INTRO,
        status=status,
        provider_snapshot=settings_model.provider,
        base_url_snapshot=settings_model.base_url,
        model_snapshot=settings_model.model,
        request_timeout_sec_snapshot=int(settings_model.request_timeout_sec or 180),
        prompt_snapshot=settings_model.prompt_template,
        error_message=error_message,
        retry_count=max(0, int(retry_count)),
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
        finished_at=utc_now_naive() if status == ANALYSIS_STATUS_FAILED else None,
    )
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
        return run, False
    except IntegrityError:
        db.rollback()
        active = get_active_analysis_run(
            db,
            task_id=task_id,
            analysis_type=ANALYSIS_TYPE_STORY_INTRO,
        )
        if active is None:
            raise
        return active, True


def update_analysis_run_failure(
    db: Session,
    *,
    run: AnalysisRun,
    error_message: str,
    raw_response: dict[str, Any] | None = None,
) -> AnalysisRun:
    run.status = ANALYSIS_STATUS_FAILED
    run.error_message = error_message
    run.finished_at = utc_now_naive()
    run.updated_at = utc_now_naive()
    if raw_response is not None:
        run.raw_response_json = _to_json(raw_response)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def enqueue_analysis_run(run_id: str, *, timeout_sec: int) -> tuple[bool, bool, str | None]:
    queue = _get_queue()
    existing_job = queue.fetch_job(run_id)
    if existing_job is not None:
        existing_status = (existing_job.get_status(refresh=True) or "").lower()
        if existing_status in RQ_ACTIVE_JOB_STATUSES:
            return True, True, None

    from app.workers.analysis_tasks import run_story_intro_analysis

    enqueue_kwargs: dict[str, Any] = {
        "job_id": run_id,
        "job_timeout": max(120, int(timeout_sec) + 300),
        "result_ttl": 3600,
    }
    retry_policy = _build_retry_policy()
    if retry_policy is not None:
        enqueue_kwargs["retry"] = retry_policy

    try:
        queue.enqueue(run_story_intro_analysis, run_id, **enqueue_kwargs)
        return True, False, None
    except Exception as exc:
        return False, False, str(exc)


def trigger_auto_analysis_for_task(db: Session, task: Task) -> AnalysisRun | None:
    source = "auto_upload"
    settings_model = get_or_create_analysis_settings(db)
    if not settings_model.analysis_enabled:
        return None

    active = get_recoverable_active_analysis_run(
        db,
        task_id=task.id,
        source=source,
    )
    if active:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="active_run_exists",
            task_id=task.id,
            run_id=active.id,
            provider=active.provider_snapshot,
            model=active.model_snapshot,
        )
        return active

    ok, reason = _check_admission(task, settings_model, require_enabled=True)
    latest = get_latest_analysis_run(db, task_id=task.id)
    next_retry_count = (latest.retry_count + 1) if latest else 0

    if not ok:
        failed_run, _ = create_analysis_run(
            db,
            task_id=task.id,
            settings_model=settings_model,
            status=ANALYSIS_STATUS_FAILED,
            retry_count=next_retry_count,
            error_message=reason,
        )
        increment_counter("analysis_failed_total")
        log_event(
            logger,
            logging.WARNING,
            "analysis_admission_rejected",
            source=source,
            task_id=task.id,
            run_id=failed_run.id,
            provider=settings_model.provider,
            model=settings_model.model,
            retry_count=next_retry_count,
            error_message=reason,
        )
        return failed_run

    run, dedup_insert = create_analysis_run(
        db,
        task_id=task.id,
        settings_model=settings_model,
        status=ANALYSIS_STATUS_QUEUED,
        retry_count=next_retry_count,
    )
    if dedup_insert:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="active_run_unique_constraint",
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
        )
        return run

    queued, _deduplicated, queue_error = enqueue_analysis_run(
        run.id,
        timeout_sec=int(settings_model.request_timeout_sec or 180),
    )
    if _deduplicated:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="rq_existing_job",
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
        )
    if not queued:
        failed_run = update_analysis_run_failure(
            db,
            run=run,
            error_message=f"分析任务入队失败：{queue_error}",
        )
        increment_counter("analysis_failed_total")
        log_event(
            logger,
            logging.ERROR,
            "analysis_enqueue_failed",
            source=source,
            task_id=task.id,
            run_id=failed_run.id,
            provider=failed_run.provider_snapshot,
            model=failed_run.model_snapshot,
            error_message=queue_error,
        )
        return failed_run

    increment_counter("analysis_enqueue_total")
    log_event(
        logger,
        logging.INFO,
        "analysis_enqueued",
        source=source,
        task_id=task.id,
        run_id=run.id,
        provider=run.provider_snapshot,
        model=run.model_snapshot,
        retry_count=run.retry_count,
        timeout_sec=int(settings_model.request_timeout_sec or 180),
    )
    return run


def build_latest_analysis_response(db: Session, *, task: Task) -> dict[str, Any]:
    settings_model = get_or_create_analysis_settings(db)
    key_info = get_analysis_api_key_info()
    has_key = key_info.has_api_key
    is_configured, _reasons = evaluate_settings_completeness(
        settings_model,
        has_api_key=has_key,
        require_enabled=False,
    )
    latest = get_latest_analysis_run(db, task_id=task.id)
    if latest is not None and latest.status in ANALYSIS_ACTIVE_STATUSES:
        recovered = _recover_active_run_if_needed(
            db,
            run=latest,
            source="latest_read_single",
        )
        latest = recovered if recovered is not None else get_latest_analysis_run(db, task_id=task.id)

    if latest is None:
        return _build_latest_not_started_payload(
            task_id=task.id,
            settings_model=settings_model,
            is_configured=is_configured,
            has_key=has_key,
        )

    normalized_result = _from_json(latest.result_json, default={})
    if not isinstance(normalized_result, dict):
        normalized_result = {}

    return {
        "task_id": task.id,
        "analysis_type": latest.analysis_type,
        "status": latest.status,
        "run_id": latest.id,
        "is_configured": is_configured,
        "has_api_key": has_key,
        "api_key_source": key_info.source,
        "can_retry": latest.status == ANALYSIS_STATUS_FAILED,
        "provider": normalized_result.get("provider") or latest.provider_snapshot,
        "model": normalized_result.get("model") or latest.model_snapshot,
        "story_intro_markdown": normalized_result.get("story_intro_markdown"),
        "summary": normalized_result.get("summary"),
        "error_message": latest.error_message,
        "retry_count": int(latest.retry_count or 0),
        "created_at": latest.created_at,
        "updated_at": latest.updated_at,
        "finished_at": latest.finished_at,
    }


def build_latest_analysis_batch_response(
    db: Session,
    *,
    task_ids: list[str],
) -> list[dict[str, Any]]:
    ordered_task_ids: list[str] = []
    seen_task_ids: set[str] = set()
    for task_id in task_ids:
        normalized = (task_id or "").strip()
        if not normalized or normalized in seen_task_ids:
            continue
        ordered_task_ids.append(normalized)
        seen_task_ids.add(normalized)

    if not ordered_task_ids:
        return []

    settings_model = get_or_create_analysis_settings(db)
    has_key = has_analysis_api_key()
    is_configured, _ = evaluate_settings_completeness(
        settings_model,
        has_api_key=has_key,
        require_enabled=False,
    )

    ranked_latest = (
        db.query(
            AnalysisRun.id.label("run_id"),
            AnalysisRun.task_id.label("task_id"),
            func.row_number()
            .over(
                partition_by=AnalysisRun.task_id,
                order_by=(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()),
            )
            .label("rn"),
        )
        .filter(
            AnalysisRun.analysis_type == ANALYSIS_TYPE_STORY_INTRO,
            AnalysisRun.task_id.in_(ordered_task_ids),
        )
        .subquery()
    )
    latest_runs = (
        db.query(AnalysisRun)
        .join(ranked_latest, AnalysisRun.id == ranked_latest.c.run_id)
        .filter(ranked_latest.c.rn == 1)
        .all()
    )
    latest_map = {run.task_id: run for run in latest_runs}

    result: list[dict[str, Any]] = []
    for task_id in ordered_task_ids:
        latest = latest_map.get(task_id)
        if latest is not None and latest.status in ANALYSIS_ACTIVE_STATUSES:
            recovered = _recover_active_run_if_needed(
                db,
                run=latest,
                source="latest_read_batch",
            )
            latest = recovered if recovered is not None else get_latest_analysis_run(db, task_id=task_id)
        if latest is None:
            pending_payload = _build_latest_not_started_payload(
                task_id=task_id,
                settings_model=settings_model,
                is_configured=is_configured,
                has_key=has_key,
            )
            result.append(
                {
                    "task_id": task_id,
                    "status": pending_payload["status"],
                    "run_id": None,
                    "can_retry": pending_payload["can_retry"],
                    "updated_at": pending_payload["updated_at"],
                }
            )
            continue

        result.append(
            {
                "task_id": task_id,
                "status": latest.status,
                "run_id": latest.id,
                "can_retry": latest.status == ANALYSIS_STATUS_FAILED,
                "updated_at": latest.updated_at,
            }
        )

    return result


def retry_analysis_for_task(db: Session, task: Task) -> tuple[AnalysisRun, bool]:
    source = "manual_retry"
    increment_counter("analysis_retry_total")
    log_event(
        logger,
        logging.INFO,
        "analysis_retry_requested",
        source=source,
        task_id=task.id,
    )

    active = get_recoverable_active_analysis_run(
        db,
        task_id=task.id,
        source=source,
    )
    if active:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="active_run_exists",
            task_id=task.id,
            run_id=active.id,
            provider=active.provider_snapshot,
            model=active.model_snapshot,
        )
        return active, True

    settings_model = get_or_create_analysis_settings(db)
    ok, reason = _check_admission(task, settings_model, require_enabled=False)
    latest = get_latest_analysis_run(db, task_id=task.id)
    next_retry_count = (latest.retry_count + 1) if latest else 0

    if not ok:
        failed_run, _ = create_analysis_run(
            db,
            task_id=task.id,
            settings_model=settings_model,
            status=ANALYSIS_STATUS_FAILED,
            retry_count=next_retry_count,
            error_message=reason,
        )
        increment_counter("analysis_failed_total")
        log_event(
            logger,
            logging.WARNING,
            "analysis_admission_rejected",
            source=source,
            task_id=task.id,
            run_id=failed_run.id,
            provider=settings_model.provider,
            model=settings_model.model,
            retry_count=next_retry_count,
            error_message=reason,
        )
        return failed_run, False

    run, dedup_insert = create_analysis_run(
        db,
        task_id=task.id,
        settings_model=settings_model,
        status=ANALYSIS_STATUS_QUEUED,
        retry_count=next_retry_count,
    )
    if dedup_insert:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="active_run_unique_constraint",
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
        )
        return run, True

    queued, deduplicated, queue_error = enqueue_analysis_run(
        run.id,
        timeout_sec=int(settings_model.request_timeout_sec or 180),
    )
    if deduplicated:
        increment_counter("analysis_dedup_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueue_deduplicated",
            source=source,
            reason="rq_existing_job",
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
        )
    if not queued:
        run = update_analysis_run_failure(
            db,
            run=run,
            error_message=f"分析任务入队失败：{queue_error}",
        )
        increment_counter("analysis_failed_total")
        log_event(
            logger,
            logging.ERROR,
            "analysis_enqueue_failed",
            source=source,
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
            error_message=queue_error,
        )
        deduplicated = False
    else:
        increment_counter("analysis_enqueue_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_enqueued",
            source=source,
            task_id=task.id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
            retry_count=run.retry_count,
            timeout_sec=int(settings_model.request_timeout_sec or 180),
        )

    return run, deduplicated


def build_analysis_adapter(settings_model: AnalysisSettings) -> AnalysisProviderAdapter:
    return build_analysis_provider_adapter(settings_model)


def build_analysis_client(settings_model: AnalysisSettings) -> AnalysisProviderAdapter:
    # backward-compatible alias for existing imports.
    return build_analysis_adapter(settings_model)


def test_settings_connection(
    settings_payload: AnalysisSettings,
) -> tuple[bool, str, int | None]:
    try:
        adapter = build_analysis_adapter(settings_payload)
    except Exception as exc:
        return False, str(exc), None

    try:
        latency_ms = adapter.test_connection(model=settings_payload.model)
        return True, "连接测试成功", latency_ms
    except GeminiAPIError as exc:
        logger.warning("Analysis settings test failed: %s", exc)
        return False, str(exc), None
    except Exception as exc:
        logger.warning("Analysis settings test exception: %s", exc)
        return False, str(exc), None
