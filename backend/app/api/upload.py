from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.database import get_db
from app.models.models import Task
from app.services.file_service import FileService
import uuid

router = APIRouter()


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    displayName: str = Form(None),
    db: Session = Depends(get_db)
):
    """上传视频文件并创建任务"""
    # 文件校验
    if not FileService.validate_video_type(file):
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
    # 上传后立即尝试抽取首帧缩略图（失败不阻断）
    await run_in_threadpool(FileService.generate_upload_preview, file_path, task_id)

    # 创建任务记录
    task = Task(
        id=task_id,
        display_name=displayName or file.filename,
        file_path=file_path,
        file_size=file_size,
        status="PENDING"
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return task
