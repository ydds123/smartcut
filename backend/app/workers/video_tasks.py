"""RQ worker tasks for SmartCut video processing."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from rq import get_current_job

from app.core.config import settings
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


def _has_nonempty_file(path: str | None) -> bool:
    if not path:
        return False
    file_path = Path(path)
    return file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0


def _build_incremental_plan(
    scenes: list[tuple[int, int]],
    existing_scene_rows: list[Scene],
) -> tuple[dict[int, Scene], list[tuple[int, int, int]]]:
    """
    基于镜头边界构建增量计划：
    - 可复用镜头：start/end 完全一致，且旧切片+缩略图都可用
    - 需重切镜头：新增或边界变化，或旧文件缺失
    """
    old_by_boundary: dict[tuple[int, int], deque[Scene]] = defaultdict(deque)
    for row in existing_scene_rows:
        key = (int(row.start_ms), int(row.end_ms))
        old_by_boundary[key].append(row)

    reused: dict[int, Scene] = {}
    to_render: list[tuple[int, int, int]] = []

    for index, (start_ms, end_ms) in enumerate(scenes):
        key = (int(start_ms), int(end_ms))
        candidates = old_by_boundary.get(key)
        matched = candidates.popleft() if candidates else None
        if matched and _has_nonempty_file(matched.file_path) and _has_nonempty_file(matched.thumbnail_path):
            reused[index] = matched
        else:
            to_render.append((index, int(start_ms), int(end_ms)))

    return reused, to_render


def _materialize_file(src_path: str, dst_path: Path) -> str:
    """将源文件落到新任务目录，优先硬链接，失败回退复制。"""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    if dst_path.exists():
        dst_path.unlink()

    src = Path(src_path)
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"source file missing: {src}")

    try:
        os.link(src, dst_path)
        mode = "link"
    except OSError:
        shutil.copy2(src, dst_path)
        mode = "copy"

    if not dst_path.exists() or dst_path.stat().st_size <= 0:
        raise RuntimeError(f"materialized file is empty: {dst_path}")
    return mode


def _run_full_review_split(
    processor: VideoProcessor,
    scenes: list[tuple[int, int]],
    progress_callback,
) -> tuple[list[str | None], list[str | None]]:
    result = processor.split_video_from_scenes(scenes, progress_callback=progress_callback)
    output_files = result["output_files"]
    thumbnails = result["thumbnails"]
    return output_files, thumbnails


def _collect_successful_scene_results(
    scenes: list[tuple[int, int]],
    output_files: list[str | None],
    thumbnails: list[str | None],
) -> tuple[list[tuple[int, int, str, str | None]], int]:
    """汇总成功切分结果（仅保留有输出视频的场景）。"""
    successful: list[tuple[int, int, str, str | None]] = []
    failed_split_count = 0

    for index, (start_ms, end_ms) in enumerate(scenes):
        video_path = output_files[index] if index < len(output_files) else None
        thumbnail_path = thumbnails[index] if index < len(thumbnails) else None
        if video_path:
            successful.append((start_ms, end_ms, video_path, thumbnail_path))
        else:
            failed_split_count += 1

    return successful, failed_split_count


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
        requested_scenes_count = len(final_scenes)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            existing_history = _from_json(task.tuning_history, default=[])
            if not isinstance(existing_history, list):
                existing_history = []
            task.total_scenes = requested_scenes_count
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

        update_progress(50)
        thumb_started_at = time.perf_counter()
        thumbnails = processor.generate_thumbnails_batch(
            output_files,
            final_scenes,
            progress_callback=progress_callback,
        )
        thumbnail_elapsed_sec = round(time.perf_counter() - thumb_started_at, 3)

        successful_results, failed_split_count = _collect_successful_scene_results(final_scenes, output_files, thumbnails)
        if not successful_results:
            raise RuntimeError("all scene splits failed")

        failed_thumbnail_count = sum(1 for _, _, _, thumb in successful_results if thumb is None)
        if failed_split_count > 0:
            logger.warning(
                "任务 %s: 切分部分失败（成功=%s, 失败=%s, 总计=%s）",
                task_id,
                len(successful_results),
                failed_split_count,
                len(final_scenes),
            )
        if failed_thumbnail_count > 0:
            logger.warning(
                "任务 %s: %s/%s 个已成功切片的缩略图生成失败",
                task_id,
                failed_thumbnail_count,
                len(successful_results),
            )

        db_started_at = time.perf_counter()
        db.query(Scene).filter(Scene.task_id == task_id).delete()

        scene_rows: list[Scene] = []
        for index, (start_ms, end_ms, file_path, thumbnail_path) in enumerate(successful_results):
            scene_rows.append(
                Scene(
                    id=f"{task_id}_scene_{index}",
                    task_id=task_id,
                    sequence_index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    file_path=file_path,
                    thumbnail_path=thumbnail_path,
                )
            )
        if scene_rows:
            db.bulk_save_objects(scene_rows)

        scenes_count = len(successful_results)
        metrics = {
            "detect_and_quality_sec": detect_elapsed_sec,
            "split_sec": split_elapsed_sec,
            "thumbnail_sec": thumbnail_elapsed_sec,
            "requested_scenes": requested_scenes_count,
            "successful_scenes": scenes_count,
            "failed_split_scenes": failed_split_count,
            "failed_thumbnail_scenes": failed_thumbnail_count,
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
    task_ref: Task | None = None
    last_db_commit_monotonic = 0.0
    last_db_progress = -1
    progress_db_min_interval_sec = 0.5
    progress_db_min_step = 2

    def update_progress(progress: int, status: str | None = None, force: bool = False):
        nonlocal last_db_commit_monotonic, last_db_progress
        clamped_progress = max(0, min(100, int(progress)))

        if job:
            job.meta["progress"] = clamped_progress
            if status:
                job.meta["status"] = status
            job.save_meta()

        if not task_ref:
            return

        task_ref.progress = clamped_progress
        if status:
            task_ref.status = status

        now = time.monotonic()
        should_commit = bool(force or status)
        if not should_commit:
            progress_delta = clamped_progress - last_db_progress
            time_delta = now - last_db_commit_monotonic
            should_commit = (
                progress_delta >= progress_db_min_step
                or time_delta >= progress_db_min_interval_sec
            )

        if should_commit:
            db.commit()
            last_db_progress = clamped_progress
            last_db_commit_monotonic = now

    try:
        total_started_at = time.perf_counter()
        task_ref = db.query(Task).filter(Task.id == task_id).first()
        if not task_ref:
            return {"success": False, "error": "Task not found"}

        # 优先使用用户编辑后的场景，回退到检测结果
        raw = _from_json(task_ref.user_edited_scenes, default=None) or \
              _from_json(task_ref.detection_result, default={}).get("scenes", [])

        scenes: list[tuple[int, int]] = [(s["start_ms"], s["end_ms"]) for s in raw]
        if not scenes:
            raise ValueError("No scenes available for splitting")

        video_path = task_ref.file_path
        active_config = _from_json(task_ref.resolved_config, default={})

        logger.info("开始切分任务 %s，共 %s 个场景", task_id, len(scenes))
        update_progress(0, "SPLITTING", force=True)

        existing_scene_rows = (
            db.query(Scene)
            .filter(Scene.task_id == task_id)
            .order_by(Scene.sequence_index.asc())
            .all()
        )

        processor = VideoProcessor(task_id, video_path, processing_config=active_config)
        plan_elapsed_ms = 0.0
        reuse_materialize_elapsed_ms = 0.0
        render_elapsed_ms = 0.0
        db_elapsed_ms = 0.0
        cleanup_elapsed_ms = 0.0

        incremental_enabled = bool(getattr(settings, "ENABLE_INCREMENTAL_SPLIT", True))
        fallback_full_resplit = False
        reused_count = 0
        rendered_count = len(scenes)
        link_success_count = 0
        copy_fallback_count = 0
        output_files: list[str | None] = []
        thumbnails: list[str | None] = []

        def progress_callback(p: int):
            update_progress(p)

        if incremental_enabled and existing_scene_rows:
            plan_started_at = time.perf_counter()
            reused_map, to_render = _build_incremental_plan(scenes, existing_scene_rows)
            plan_elapsed_ms = round((time.perf_counter() - plan_started_at) * 1000, 2)
            reused_count = len(reused_map)
            rendered_count = len(to_render)
            logger.info(
                "任务 %s 增量切分规划：total=%s reused=%s rendered=%s",
                task_id,
                len(scenes),
                reused_count,
                rendered_count,
            )

            if reused_count > 0 and rendered_count < len(scenes):
                try:
                    output_files = [None for _ in scenes]
                    thumbnails = [None for _ in scenes]

                    materialize_started_at = time.perf_counter()
                    for index, existing_scene in reused_map.items():
                        dst_video = processor.scenes_dir / f"scene_{index:03d}.mp4"
                        dst_thumb = processor.scenes_dir / f"scene_{index:03d}_thumb.jpg"
                        video_mode = _materialize_file(existing_scene.file_path, dst_video)
                        thumb_mode = _materialize_file(existing_scene.thumbnail_path, dst_thumb)
                        if video_mode == "link":
                            link_success_count += 1
                        else:
                            copy_fallback_count += 1
                        if thumb_mode == "link":
                            link_success_count += 1
                        else:
                            copy_fallback_count += 1
                        output_files[index] = str(dst_video)
                        thumbnails[index] = str(dst_thumb)
                    reuse_materialize_elapsed_ms = round((time.perf_counter() - materialize_started_at) * 1000, 2)

                    if to_render:
                        render_indices = [index for index, _, _ in to_render]
                        render_scenes = [(start_ms, end_ms) for _, start_ms, end_ms in to_render]

                        progress_base = int((reused_count / max(1, len(scenes))) * 50)
                        update_progress(progress_base)

                        def incremental_progress_callback(raw_progress: int):
                            mapped = progress_base + int((max(0, min(raw_progress, 100)) / 100) * (90 - progress_base))
                            update_progress(mapped)

                        render_started_at = time.perf_counter()
                        partial_result = processor.split_video_from_scenes(
                            render_scenes,
                            progress_callback=incremental_progress_callback,
                            output_indices=render_indices,
                        )
                        render_elapsed_ms = round((time.perf_counter() - render_started_at) * 1000, 2)
                        partial_outputs = partial_result["output_files"]
                        partial_thumbs = partial_result["thumbnails"]

                        for pos, target_index in enumerate(render_indices):
                            output_files[target_index] = partial_outputs[pos]
                            thumbnails[target_index] = partial_thumbs[pos]
                    else:
                        update_progress(90)
                except Exception as incremental_exc:
                    fallback_full_resplit = True
                    reused_count = 0
                    rendered_count = len(scenes)
                    logger.warning(
                        "任务 %s 增量切分失败，回退全量切分: %s",
                        task_id,
                        incremental_exc,
                    )
                    processor = VideoProcessor(task_id, video_path, processing_config=active_config)
                    render_started_at = time.perf_counter()
                    output_files, thumbnails = _run_full_review_split(
                        processor,
                        scenes,
                        progress_callback=progress_callback,
                    )
                    render_elapsed_ms = round((time.perf_counter() - render_started_at) * 1000, 2)
            else:
                # 无可复用镜头时直接全量切分，避免增量路径无收益。
                reused_count = 0
                rendered_count = len(scenes)
                render_started_at = time.perf_counter()
                output_files, thumbnails = _run_full_review_split(
                    processor,
                    scenes,
                    progress_callback=progress_callback,
                )
                render_elapsed_ms = round((time.perf_counter() - render_started_at) * 1000, 2)
        else:
            render_started_at = time.perf_counter()
            output_files, thumbnails = _run_full_review_split(
                processor,
                scenes,
                progress_callback=progress_callback,
            )
            render_elapsed_ms = round((time.perf_counter() - render_started_at) * 1000, 2)

        successful_results, failed_split_count = _collect_successful_scene_results(scenes, output_files, thumbnails)
        if not successful_results:
            raise RuntimeError("all review scenes failed to split")
        failed_thumbnail_count = sum(1 for _, _, _, thumb in successful_results if thumb is None)
        successful_count = len(successful_results)

        if failed_split_count > 0:
            logger.warning(
                "任务 %s 切分部分失败（成功=%s, 失败=%s, 总计=%s）",
                task_id,
                successful_count,
                failed_split_count,
                len(scenes),
            )

        db_started_at = time.perf_counter()
        db.query(Scene).filter(Scene.task_id == task_id).delete()
        scene_rows = [
            Scene(
                id=f"{task_id}_scene_{i}",
                task_id=task_id,
                sequence_index=i,
                start_ms=start_ms,
                end_ms=end_ms,
                file_path=file_path,
                thumbnail_path=thumbnail_path,
            )
            for i, (start_ms, end_ms, file_path, thumbnail_path) in enumerate(successful_results)
        ]
        if scene_rows:
            db.bulk_save_objects(scene_rows)

        if task_ref:
            task_ref.status = "TIMELINE_READY"
            task_ref.progress = 100
            task_ref.total_scenes = successful_count
            # 以本轮实际切分结果回写审核草稿，确保返回编辑与工作台镜头数一致。
            task_ref.user_edited_scenes = _to_json(
                [{"start_ms": start_ms, "end_ms": end_ms} for start_ms, end_ms, _, _ in successful_results]
            )
        db.commit()
        db_elapsed_ms = round((time.perf_counter() - db_started_at) * 1000, 2)
        last_db_commit_monotonic = time.monotonic()
        last_db_progress = 100

        # 保留本轮最新切分目录，清理同任务历史切分目录，避免旧切片残留。
        cleanup_started_at = time.perf_counter()
        try:
            FileService.delete_split_assets(task_id, keep_task_dir_path=str(processor.task_dir))
        except Exception as cleanup_exc:
            logger.warning("任务 %s 清理历史切片目录失败: %s", task_id, cleanup_exc)
        cleanup_elapsed_ms = round((time.perf_counter() - cleanup_started_at) * 1000, 2)

        reused_ratio = round(reused_count / max(1, len(scenes)), 4)
        split_stats = {
            "total_scenes": successful_count,
            "requested_scenes": len(scenes),
            "reused_count": reused_count,
            "rendered_count": rendered_count,
            "reused_ratio": reused_ratio,
            "failed_split_count": failed_split_count,
            "failed_thumbnail_count": failed_thumbnail_count,
            "incremental_enabled": incremental_enabled,
            "fallback_full_resplit": fallback_full_resplit,
            "link_success_count": link_success_count,
            "copy_fallback_count": copy_fallback_count,
            "plan_elapsed_ms": plan_elapsed_ms,
            "reuse_materialize_elapsed_ms": reuse_materialize_elapsed_ms,
            "render_elapsed_ms": render_elapsed_ms,
            "db_elapsed_ms": db_elapsed_ms,
            "cleanup_elapsed_ms": cleanup_elapsed_ms,
            "total_elapsed_ms": round((time.perf_counter() - total_started_at) * 1000, 2),
        }

        if task_ref:
            task_ref.split_stats = _to_json(split_stats)
            db.commit()
        update_progress(100, force=True)

        logger.info(
            "任务 %s 切分完成，状态 TIMELINE_READY，stats=%s",
            task_id,
            _to_json(split_stats),
        )
        return {"success": True, "scenes_count": successful_count, "split_stats": split_stats}

    except Exception as exc:
        logger.exception("任务 %s 切分异常", task_id)
        if not task_ref:
            task_ref = db.query(Task).filter(Task.id == task_id).first()
        if task_ref:
            task_ref.status = "FAILED"
            task_ref.progress = 0
            task_ref.review_notes = str(exc)
            task_ref.split_stats = None
        db.commit()
        return {"success": False, "error": str(exc)}

    finally:
        db.close()
