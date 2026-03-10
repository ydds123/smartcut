from __future__ import annotations

import ipaddress
import threading
import time
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import AnalysisSettings, Task
from app.schemas.analysis import (
    AnalysisLatestBatchRequest,
    AnalysisLatestBatchResponse,
    AnalysisLatestResponse,
    AnalysisOpenEnvFileResponse,
    AnalysisRetryResponse,
    AnalysisSettingsResponse,
    AnalysisSettingsTestRequest,
    AnalysisSettingsTestResponse,
    AnalysisSettingsUpsertRequest,
)
from app.services.analysis_service import (
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_API_KEY_SOURCE_PROCESS_ENV,
    build_latest_analysis_batch_response,
    build_latest_analysis_response,
    can_open_env_file_on_platform,
    get_analysis_api_key_info,
    get_or_create_analysis_settings,
    open_analysis_env_file,
    retry_analysis_for_task,
    settings_to_response,
    test_settings_connection,
    upsert_analysis_settings,
)

router = APIRouter()

OPEN_ENV_FILE_HEADER_NAME = "X-SmartCut-Local-Action"
OPEN_ENV_FILE_HEADER_VALUE = "open-analysis-env-file"
OPEN_ENV_FILE_THROTTLE_SECONDS = 1.5

_open_env_file_lock = threading.Lock()
_open_env_file_last_called_at = 0.0


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_local_loopback_request(request: Request) -> bool:
    client = request.client
    client_host = client.host if client else None
    return _is_loopback_host(client_host)


def _is_allowed_local_origin(origin: str | None) -> bool:
    if not origin:
        return False
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not _is_loopback_host(parsed.hostname):
        return False

    allowed_origins = {item.rstrip("/") for item in getattr(settings, "CORS_ORIGINS", [])}
    return origin.rstrip("/") in allowed_origins


def _build_settings_response(
    settings_model: AnalysisSettings,
    *,
    request: Request,
) -> dict:
    key_info = get_analysis_api_key_info()
    is_local_request = _is_local_loopback_request(request)
    can_open = (
        is_local_request
        and key_info.env_file_exists
        and key_info.source != ANALYSIS_API_KEY_SOURCE_PROCESS_ENV
        and can_open_env_file_on_platform()
    )
    expose_env_file_path = is_local_request and key_info.source != ANALYSIS_API_KEY_SOURCE_PROCESS_ENV
    return settings_to_response(
        settings_model,
        expose_env_file_path=expose_env_file_path,
        can_open_env_file=can_open,
    )


def _consume_open_env_file_rate_limit() -> bool:
    global _open_env_file_last_called_at
    with _open_env_file_lock:
        now = time.monotonic()
        if now - _open_env_file_last_called_at < OPEN_ENV_FILE_THROTTLE_SECONDS:
            return False
        _open_env_file_last_called_at = now
        return True


@router.get("/analysis/settings", response_model=AnalysisSettingsResponse)
def get_analysis_settings(
    request: Request,
    db: Session = Depends(get_db),
):
    settings_model = get_or_create_analysis_settings(db)
    return _build_settings_response(settings_model, request=request)


@router.put("/analysis/settings", response_model=AnalysisSettingsResponse)
def put_analysis_settings(
    request: Request,
    payload: AnalysisSettingsUpsertRequest,
    db: Session = Depends(get_db),
):
    settings_model = upsert_analysis_settings(db, payload.model_dump())
    return _build_settings_response(settings_model, request=request)


@router.post("/analysis/settings/test", response_model=AnalysisSettingsTestResponse)
def test_analysis_settings(
    payload: AnalysisSettingsTestRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    current = get_or_create_analysis_settings(db)
    merged = {
        "provider": current.provider,
        "base_url": current.base_url,
        "model": current.model,
        "prompt_template": current.prompt_template,
        "analysis_enabled": current.analysis_enabled,
        "request_timeout_sec": int(current.request_timeout_sec or 180),
    }
    if payload is not None:
        patch = payload.model_dump(exclude_none=True)
        merged.update(patch)

    shadow = AnalysisSettings(
        id="default",
        provider=(merged["provider"] or "").strip(),
        base_url=(merged["base_url"] or "").strip(),
        model=(merged["model"] or "").strip(),
        prompt_template=merged["prompt_template"] if isinstance(merged["prompt_template"], str) else "",
        analysis_enabled=bool(merged["analysis_enabled"]),
        request_timeout_sec=max(10, min(900, int(merged["request_timeout_sec"]))),
    )
    success, message, latency_ms = test_settings_connection(shadow)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {
        "success": True,
        "message": message,
        "latency_ms": latency_ms,
    }


@router.post("/analysis/settings/open-env-file", response_model=AnalysisOpenEnvFileResponse)
def open_analysis_settings_env_file(request: Request):
    key_info = get_analysis_api_key_info()

    if not _is_local_loopback_request(request):
        raise HTTPException(status_code=403, detail="仅支持在本机运行场景下打开配置文件")

    if not _is_allowed_local_origin(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="当前请求来源不允许触发本地配置文件操作")

    header_value = (request.headers.get(OPEN_ENV_FILE_HEADER_NAME) or "").strip()
    if header_value != OPEN_ENV_FILE_HEADER_VALUE:
        raise HTTPException(status_code=403, detail="缺少受信任的本地操作标识")

    if key_info.source == ANALYSIS_API_KEY_SOURCE_PROCESS_ENV:
        raise HTTPException(
            status_code=409,
            detail="当前 API Key 来自进程环境变量，不对应 .env 文件",
        )

    if not key_info.env_file_exists:
        raise HTTPException(status_code=400, detail="推荐配置文件不存在，请先创建 backend/.env")

    if not can_open_env_file_on_platform():
        raise HTTPException(status_code=400, detail="当前运行环境不支持自动打开配置文件")

    if not _consume_open_env_file_rate_limit():
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")

    success, message = open_analysis_env_file()
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "success": True,
        "message": message,
        "path": str(key_info.env_file_path),
    }


@router.get("/tasks/{task_id}/analysis/latest", response_model=AnalysisLatestResponse)
def get_task_analysis_latest(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return build_latest_analysis_response(db, task=task)


@router.post("/analysis/tasks/latest-batch", response_model=AnalysisLatestBatchResponse)
def get_tasks_analysis_latest_batch(
    payload: AnalysisLatestBatchRequest,
    db: Session = Depends(get_db),
):
    if not payload.task_ids:
        return {"items": []}
    return {
        "items": build_latest_analysis_batch_response(db, task_ids=payload.task_ids),
    }


@router.post("/tasks/{task_id}/analysis/retry", response_model=AnalysisRetryResponse)
def retry_task_analysis(task_id: str, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    run, deduplicated = retry_analysis_for_task(db, task)
    message = "已有分析任务在处理中" if deduplicated else None
    if run.status == ANALYSIS_STATUS_FAILED and not deduplicated:
        message = (run.error_message or "").strip() or "重试请求未通过，请检查分析配置"
    return {
        "task_id": task.id,
        "analysis_type": run.analysis_type,
        "run_id": run.id,
        "status": run.status,
        "deduplicated": deduplicated,
        "message": message,
    }
