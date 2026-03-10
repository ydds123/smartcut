from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pathlib import Path
import logging
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.api.tasks import enqueue_review_task
from app.models.models import Task
from app.schemas.task import ProcessTaskRequest
from app.services.analysis_service import trigger_auto_analysis_for_task
from app.services.file_service import FileService
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    displayName: str = Form(None),
    db: Session = Depends(get_db)
):
    """上传视频文件并创建任务"""
    enforce_rate_limit(
        request,
        "upload",
        max_requests=int(getattr(settings, "RATE_LIMIT_UPLOAD_MAX_REQUESTS", 8)),
        window_sec=int(getattr(settings, "RATE_LIMIT_WINDOW_SEC", 60)),
    )

    # 文件校验
    if not await FileService.validate_video_type(file):
        raise HTTPException(status_code=400, detail="Invalid file type")

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 保存文件
    try:
        file_path = await FileService.save_upload(file, task_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 413 if "max size" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    file_size = Path(file_path).stat().st_size if Path(file_path).exists() else (file.size or 0)
    duration_ms = await run_in_threadpool(FileService.get_video_duration_ms, file_path)
    # 上传后立即尝试抽取首帧缩略图（失败不阻断）
    await run_in_threadpool(FileService.generate_upload_preview, file_path, task_id)

    # 创建任务记录
    task = Task(
        id=task_id,
        display_name=displayName or file.filename,
        file_path=file_path,
        file_size=file_size,
        duration_ms=duration_ms,
        status="PENDING"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    auto_review_job_id = f"task:{task_id}:review:auto-upload"
    try:
        enqueue_review_task(
            db,
            task=task,
            payload=ProcessTaskRequest(),
            job_id=auto_review_job_id,
        )
        db.refresh(task)
    except Exception as exc:  # pragma: no cover - runtime state dependent
        db.rollback()
        failure_detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        task.status = "FAILED"
        task.progress = 0
        task.active_operation = None
        task.active_job_id = None
        task.review_notes = f"自动检测分镜入队失败: {failure_detail}"
        db.commit()
        db.refresh(task)
        logger.warning("auto review enqueue failed: task_id=%s err=%s", task_id, failure_detail)

    # 自动触发分析子链路（失败不影响上传主流程）
    try:
        trigger_auto_analysis_for_task(db, task)
    except Exception as exc:  # pragma: no cover - runtime state dependent
        db.rollback()
        logger.warning("auto analysis trigger failed: task_id=%s err=%s", task_id, exc)

    return task
