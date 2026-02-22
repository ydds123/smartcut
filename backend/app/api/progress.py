"""
SSE (Server-Sent Events) 实时进度推送
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from app.core.database import SessionLocal
from app.models.models import Task
import asyncio
import json
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()


def _fetch_task_snapshot(task_id: str):
    """使用短会话读取任务快照，降低连接池占用。"""
    with SessionLocal() as db:
        return (
            db.query(Task.id, Task.progress, Task.status, Task.total_scenes)
            .filter(Task.id == task_id)
            .first()
        )


async def task_progress_stream(task_id: str):
    """生成任务进度流（优化版：智能增量推送）"""
    last_progress = -1
    last_status = None
    last_total_scenes = None
    no_update_count = 0
    max_no_update = 30  # 最多 30 次无更新后关闭连接
    heartbeat_every = 5  # 定期发送注释帧，避免网关回收空闲连接

    try:
        while no_update_count < max_no_update:
            try:
                task = _fetch_task_snapshot(task_id)
            except SQLAlchemyError as exc:
                logger.warning(f"SSE DB query failed for task {task_id}: {exc}")
                yield f"data: {json.dumps({'error': 'db query failed'})}\n\n"
                await asyncio.sleep(1.5)
                continue

            if not task:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            # 检查是否有变化
            has_changes = (
                task.progress != last_progress or
                task.status != last_status or
                task.total_scenes != last_total_scenes
            )

            if has_changes:
                data = {
                    "task_id": task.id,
                    "progress": task.progress,
                    "status": task.status,
                    "total_scenes": task.total_scenes,
                    "timestamp": time.time(),
                }
                yield f"data: {json.dumps(data)}\n\n"

                last_progress = task.progress
                last_status = task.status
                last_total_scenes = task.total_scenes
                no_update_count = 0
            else:
                no_update_count += 1
                if no_update_count % heartbeat_every == 0:
                    yield ": keepalive\n\n"

            # 任务完成或失败时关闭
            if task.status in ["COMPLETED", "FAILED"]:
                logger.info(f"Task {task_id} finished with status {task.status}")
                break

            # 动态调整推送间隔，减少高并发时数据库压力
            if task.status == "PROCESSING":
                await asyncio.sleep(0.6)
            elif task.status == "QUEUED":
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(1.6)

    except asyncio.CancelledError:
        # 客户端断开连接
        logger.debug(f"SSE client disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"SSE error for task {task_id}: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.get("/tasks/{task_id}/progress")
async def get_task_progress(task_id: str):
    """
    获取任务实时进度（SSE）

    客户端可以使用 EventSource 连接此端点：
    const eventSource = new EventSource('/api/tasks/{task_id}/progress');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.progress, 'Status:', data.status);
    };
    """
    # 验证任务是否存在
    try:
        task = _fetch_task_snapshot(task_id)
    except SQLAlchemyError as exc:
        logger.error(f"Failed to query task before SSE stream start ({task_id}): {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        task_progress_stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
