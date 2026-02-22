"""RQ worker tasks for SmartCut video processing."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from rq import get_current_job

from app.core.database import SessionLocal
from app.models.models import Scene, Task
from app.services.file_service import FileService
from app.services.quality_tuning import (
    DEFAULT_QUALITY_CONFIG,
    analyze_scene_quality,
    should_retry_quality,
    tune_config_for_next_attempt,
)
from app.services.video_processor import VideoProcessor

logger = logging.getLogger(__name__)


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _from_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def process_video_task(
    task_id: str,
    video_path: str,
    resolved_config: dict[str, Any] | None = None,
    max_quality_retries: int = 0,
) -> dict:
    """RQ entrypoint: process one task with quality-first tuning."""
    job = get_current_job()
    db = SessionLocal()

    def update_progress(progress: int, status: str | None = None):
        if job:
            job.meta["progress"] = progress
            if status:
                job.meta["status"] = status
            job.save_meta()

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress = progress
            if status:
                task.status = status
            db.commit()

    try:
        logger.info("开始处理任务 %s", task_id)
        update_progress(0, "PROCESSING")

        active_config = dict(DEFAULT_QUALITY_CONFIG)
        if resolved_config:
            active_config.update(resolved_config)

        processor = VideoProcessor(task_id, video_path, processing_config=active_config)

        total_started_at = time.perf_counter()
        detect_started_at = time.perf_counter()

        tuning_history: list[dict[str, Any]] = []
        final_flags: dict[str, Any] = {}
        final_suspects: list[dict[str, Any]] = []
        final_scenes: list[tuple[int, int]] = []
        final_detection_report: dict[str, Any] = {}

        for attempt_index in range(max_quality_retries + 1):
            processor.set_processing_config(active_config)
            attempt_started_at = time.perf_counter()

            final_scenes = processor.detect_scenes()
            detection_report = dict(processor.last_detection_report or {})
            final_detection_report = detection_report
            video_duration_ms = processor._get_video_duration_ms()
            final_flags, final_suspects = analyze_scene_quality(final_scenes, video_duration_ms)

            tuning_history.append(
                {
                    "attempt": attempt_index + 1,
                    "config": dict(active_config),
                    "scene_count": len(final_scenes),
                    "detection_report": detection_report,
                    "quality_flags": final_flags,
                    "suspect_count": len(final_suspects),
                    "elapsed_sec": round(time.perf_counter() - attempt_started_at, 3),
                }
            )

            if not should_retry_quality(final_flags, attempt_index=attempt_index, max_retries=max_quality_retries):
                break

            next_config = tune_config_for_next_attempt(active_config, final_flags)
            logger.info(
                "任务 %s 触发质量重试，第 %s 轮，flags=%s",
                task_id,
                attempt_index + 1,
                final_flags,
            )
            active_config = next_config

        detect_elapsed_sec = round(time.perf_counter() - detect_started_at, 3)
        scenes_count = len(final_scenes)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            existing_history = _from_json(task.tuning_history, default=[])
            if not isinstance(existing_history, list):
                existing_history = []
            task.total_scenes = scenes_count
            task.resolved_config = _to_json(active_config)
            detection_flags = dict(final_flags)
            if final_detection_report:
                detection_flags["detection_report"] = final_detection_report
            task.quality_flags = _to_json(detection_flags)
            task.suspect_segments = _to_json(final_suspects)
            task.tuning_history = _to_json([*existing_history, *tuning_history])
        db.commit()

        def progress_callback(progress_percent: int):
            update_progress(progress_percent)

        update_progress(10)
        split_started_at = time.perf_counter()
        output_files = processor.split_video(final_scenes, progress_callback=progress_callback)
        split_elapsed_sec = round(time.perf_counter() - split_started_at, 3)

        if len(output_files) != len(final_scenes):
            raise RuntimeError(
                f"split outputs mismatch: expected={len(final_scenes)}, actual={len(output_files)}"
            )

        update_progress(50)
        thumb_started_at = time.perf_counter()
        thumbnails = processor.generate_thumbnails_batch(
            output_files,
            final_scenes,
            progress_callback=progress_callback,
        )
        thumbnail_elapsed_sec = round(time.perf_counter() - thumb_started_at, 3)

        if len(thumbnails) != len(output_files):
            raise RuntimeError(
                f"thumbnail outputs mismatch: expected={len(output_files)}, actual={len(thumbnails)}"
            )

        failed_count = sum(1 for thumb in thumbnails if thumb is None)
        if failed_count > 0:
            logger.warning("任务 %s: %s/%s 个镜头缩略图生成失败", task_id, failed_count, len(output_files))

        db_started_at = time.perf_counter()
        db.query(Scene).filter(Scene.task_id == task_id).delete()

        scene_rows: list[Scene] = []
        for index, (start_ms, end_ms) in enumerate(final_scenes):
            scene_rows.append(
                Scene(
                    id=f"{task_id}_scene_{index}",
                    task_id=task_id,
                    sequence_index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    file_path=output_files[index] if index < len(output_files) else None,
                    thumbnail_path=thumbnails[index] if index < len(thumbnails) else None,
                )
            )
        if scene_rows:
            db.bulk_save_objects(scene_rows)

        metrics = {
            "detect_and_quality_sec": detect_elapsed_sec,
            "split_sec": split_elapsed_sec,
            "thumbnail_sec": thumbnail_elapsed_sec,
            "db_persist_sec": round(time.perf_counter() - db_started_at, 3),
            "total_sec": round(time.perf_counter() - total_started_at, 3),
        }

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "COMPLETED"
            task.progress = 100
            task.total_scenes = scenes_count
            # 将指标附加到 quality_flags，便于前端一次读取。
            merged_flags = dict(final_flags)
            if final_detection_report:
                merged_flags["detection_report"] = final_detection_report
            merged_flags["metrics"] = metrics
            task.quality_flags = _to_json(merged_flags)
        db.commit()

        logger.info("任务 %s 处理完成，共 %s 个镜头", task_id, scenes_count)
        return {
            "success": True,
            "scenes_count": scenes_count,
            "output_files": output_files,
            "thumbnails": thumbnails,
            "resolved_config": active_config,
            "quality_flags": final_flags,
            "suspect_segments": final_suspects,
            "metrics": metrics,
        }

    except Exception as exc:
        logger.exception("任务 %s 处理异常", task_id)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.progress = 0
            task.review_notes = str(exc)
        db.commit()

        return {
            "success": False,
            "error": str(exc),
        }

    finally:
        db.close()


def detect_scenes_for_review(
    task_id: str,
    video_path: str,
    resolved_config: dict[str, Any] | None = None,
) -> dict:
    """RQ entrypoint: 仅检测场景，结果存入 detection_result，状态设为 REVIEW_PENDING。"""
    job = get_current_job()
    db = SessionLocal()

    def update_progress(progress: int, status: str | None = None):
        if job:
            job.meta["progress"] = progress
            if status:
                job.meta["status"] = status
            job.save_meta()
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress = progress
            if status:
                task.status = status
            db.commit()

    try:
        logger.info("开始场景检测（预览模式）任务 %s", task_id)
        update_progress(0, "DETECTING")

        active_config = dict(DEFAULT_QUALITY_CONFIG)
        if resolved_config:
            active_config.update(resolved_config)

        processor = VideoProcessor(task_id, video_path, processing_config=active_config)
        result = processor.detect_scenes_only()

        scenes = result["scenes"]
        duration_ms = result["duration_ms"]
        report = result["report"]

        detection_data = {
            "scenes": [{"start_ms": s, "end_ms": e} for s, e in scenes],
            "duration_ms": duration_ms,
            "report": report,
        }

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.detection_result = _to_json(detection_data)
            task.total_scenes = len(scenes)
            task.status = "REVIEW_PENDING"
            task.progress = 100
        db.commit()

        logger.info("任务 %s 场景检测完成，共 %s 个场景，等待用户确认", task_id, len(scenes))
        return {"success": True, "scenes_count": len(scenes)}

    except Exception as exc:
        logger.exception("任务 %s 场景检测异常", task_id)
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.progress = 0
            task.review_notes = str(exc)
        db.commit()
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


def split_video_after_review(task_id: str) -> dict:
    """RQ entrypoint: 读取用户编辑后的场景列表，执行切分 + 缩略图，状态设为 TIMELINE_READY。"""
    job = get_current_job()
    db = SessionLocal()

    def update_progress(progress: int, status: str | None = None):
        if job:
            job.meta["progress"] = progress
            if status:
                job.meta["status"] = status
            job.save_meta()
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress = progress
            if status:
                task.status = status
            db.commit()

    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}

        # 优先使用用户编辑后的场景，回退到检测结果
        raw = _from_json(task.user_edited_scenes, default=None) or \
              _from_json(task.detection_result, default={}).get("scenes", [])

        scenes: list[tuple[int, int]] = [(s["start_ms"], s["end_ms"]) for s in raw]
        if not scenes:
            raise ValueError("No scenes available for splitting")

        video_path = task.file_path
        active_config = _from_json(task.resolved_config, default={})

        logger.info("开始切分任务 %s，共 %s 个场景", task_id, len(scenes))
        update_progress(0, "SPLITTING")

        processor = VideoProcessor(task_id, video_path, processing_config=active_config)

        def progress_callback(p: int):
            update_progress(p)

        result = processor.split_video_from_scenes(scenes, progress_callback=progress_callback)
        output_files = result["output_files"]
        thumbnails = result["thumbnails"]

        if len(output_files) != len(scenes):
            raise RuntimeError(
                f"split outputs mismatch: expected={len(scenes)}, actual={len(output_files)}"
            )
        if len(thumbnails) != len(output_files):
            raise RuntimeError(
                f"thumbnail outputs mismatch: expected={len(output_files)}, actual={len(thumbnails)}"
            )

        db.query(Scene).filter(Scene.task_id == task_id).delete()
        scene_rows = [
            Scene(
                id=f"{task_id}_scene_{i}",
                task_id=task_id,
                sequence_index=i,
                start_ms=start_ms,
                end_ms=end_ms,
                file_path=output_files[i] if i < len(output_files) else None,
                thumbnail_path=thumbnails[i] if i < len(thumbnails) else None,
            )
            for i, (start_ms, end_ms) in enumerate(scenes)
        ]
        if scene_rows:
            db.bulk_save_objects(scene_rows)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "TIMELINE_READY"
            task.progress = 100
            task.total_scenes = len(scenes)
        db.commit()

        # 保留本轮最新切分目录，清理同任务历史切分目录，避免旧切片残留。
        try:
            FileService.delete_split_assets(task_id, keep_task_dir_path=str(processor.task_dir))
        except Exception as cleanup_exc:
            logger.warning("任务 %s 清理历史切片目录失败: %s", task_id, cleanup_exc)

        logger.info("任务 %s 切分完成，状态 TIMELINE_READY", task_id)
        return {"success": True, "scenes_count": len(scenes)}

    except Exception as exc:
        logger.exception("任务 %s 切分异常", task_id)
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "FAILED"
            task.progress = 0
            task.review_notes = str(exc)
        db.commit()
        return {"success": False, "error": str(exc)}

    finally:
        db.close()
