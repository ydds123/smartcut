from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.core.database import SessionLocal
from app.core.telemetry import increment_counter, log_event
from app.models.models import AnalysisRun, AnalysisSettings, Task
from app.services.analysis_gemini import GeminiAPIError
from app.services.analysis_provider import AnalysisProviderAdapter, UploadedVideoRef
from app.services.analysis_service import (
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_QUEUED,
    ANALYSIS_STATUS_RUNNING,
    ANALYSIS_STATUS_SUCCEEDED,
    build_analysis_adapter,
)

logger = logging.getLogger(__name__)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _to_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _mark_failed(
    db,
    run: AnalysisRun,
    message: str,
    *,
    error_code: str,
    duration_ms: int,
    raw_payload: dict[str, Any] | None = None,
) -> None:
    run.status = ANALYSIS_STATUS_FAILED
    run.error_message = message
    run.finished_at = _utc_now_naive()
    run.updated_at = _utc_now_naive()
    if raw_payload is not None:
        run.raw_response_json = _to_json(raw_payload)
    db.add(run)
    db.commit()
    increment_counter("analysis_failed_total")
    log_event(
        logger,
        logging.WARNING,
        "analysis_failed",
        task_id=run.task_id,
        run_id=run.id,
        provider=run.provider_snapshot,
        model=run.model_snapshot,
        retry_count=run.retry_count,
        duration_ms=duration_ms,
        error_code=error_code,
        error_message=message,
    )


def run_story_intro_analysis(run_id: str) -> dict[str, Any]:
    db = SessionLocal()
    started_at = time.perf_counter()
    uploaded_video: UploadedVideoRef | None = None
    adapter: AnalysisProviderAdapter | None = None

    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if not run:
            return {"status": "missing_run", "run_id": run_id}

        if run.status not in {ANALYSIS_STATUS_QUEUED, ANALYSIS_STATUS_RUNNING}:
            return {"status": "ignored", "run_id": run_id, "run_status": run.status}

        run.status = ANALYSIS_STATUS_RUNNING
        run.error_message = None
        run.updated_at = _utc_now_naive()
        db.add(run)
        db.commit()
        log_event(
            logger,
            logging.INFO,
            "analysis_started",
            task_id=run.task_id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
            retry_count=run.retry_count,
        )

        task = db.query(Task).filter(Task.id == run.task_id).first()
        if not task:
            _mark_failed(
                db,
                run,
                "关联任务不存在",
                error_code="task_not_found",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return {"status": "failed", "reason": "task_not_found", "run_id": run_id}

        ephemeral_settings = AnalysisSettings(
            provider=run.provider_snapshot or "gemini",
            base_url=run.base_url_snapshot or "https://generativelanguage.googleapis.com",
            model=run.model_snapshot or "",
            prompt_template=run.prompt_snapshot or "",
            analysis_enabled=True,
            request_timeout_sec=int(run.request_timeout_sec_snapshot or 180),
        )
        if run.model_snapshot:
            ephemeral_settings.model = run.model_snapshot
        if run.prompt_snapshot:
            ephemeral_settings.prompt_template = run.prompt_snapshot
        if run.base_url_snapshot:
            ephemeral_settings.base_url = run.base_url_snapshot

        if not (ephemeral_settings.prompt_template or "").strip():
            _mark_failed(
                db,
                run,
                "提示词为空，无法执行分析",
                error_code="empty_prompt",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return {"status": "failed", "reason": "empty_prompt", "run_id": run_id}

        adapter = build_analysis_adapter(ephemeral_settings)
        uploaded_video = adapter.upload_video(
            task.file_path,
            display_name=task.display_name,
        )
        if not uploaded_video.uri:
            _mark_failed(
                db,
                run,
                "视频上传成功但未返回可用 URI",
                error_code="missing_file_uri",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
            return {"status": "failed", "reason": "missing_file_uri", "run_id": run_id}

        normalized_result, raw_response = adapter.generate_story_intro(
            model=ephemeral_settings.model,
            prompt=ephemeral_settings.prompt_template,
            uploaded_video=uploaded_video,
        )

        run.status = ANALYSIS_STATUS_SUCCEEDED
        run.result_json = _to_json(normalized_result)
        run.raw_response_json = _to_json(raw_response)
        run.error_message = None
        run.finished_at = _utc_now_naive()
        run.updated_at = _utc_now_naive()
        db.add(run)
        db.commit()
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        increment_counter("analysis_success_total")
        log_event(
            logger,
            logging.INFO,
            "analysis_succeeded",
            task_id=run.task_id,
            run_id=run.id,
            provider=run.provider_snapshot,
            model=run.model_snapshot,
            retry_count=run.retry_count,
            duration_ms=duration_ms,
        )

        return {"status": "succeeded", "run_id": run_id}
    except GeminiAPIError as exc:
        logger.warning("analysis run failed run_id=%s err=%s", run_id, exc)
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if run:
            _mark_failed(
                db,
                run,
                str(exc),
                error_code="provider_error",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        return {"status": "failed", "run_id": run_id, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - runtime dependent
        logger.exception("analysis worker exception run_id=%s", run_id)
        run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
        if run:
            _mark_failed(
                db,
                run,
                str(exc),
                error_code="worker_exception",
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        return {"status": "failed", "run_id": run_id, "error": str(exc)}
    finally:
        try:
            if uploaded_video is not None:
                cleanup_adapter = adapter
                if cleanup_adapter is None:
                    run_for_cleanup = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
                    if run_for_cleanup:
                        cleanup_settings = AnalysisSettings(
                            provider=run_for_cleanup.provider_snapshot or "gemini",
                            base_url=run_for_cleanup.base_url_snapshot or "https://generativelanguage.googleapis.com",
                            model=run_for_cleanup.model_snapshot or "",
                            prompt_template=run_for_cleanup.prompt_snapshot or "",
                            analysis_enabled=True,
                            request_timeout_sec=int(run_for_cleanup.request_timeout_sec_snapshot or 180),
                        )
                        cleanup_adapter = build_analysis_adapter(cleanup_settings)
                if cleanup_adapter is not None:
                    cleanup_adapter.cleanup(uploaded_video)
        except Exception:
            logger.debug("analysis worker file cleanup failed run_id=%s", run_id, exc_info=True)
        db.close()
