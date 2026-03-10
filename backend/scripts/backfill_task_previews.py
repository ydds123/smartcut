#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Task
from app.services.file_service import FileService


def resolve_video_path(task: Task) -> Path | None:
    direct_path = Path(task.file_path)
    if direct_path.is_absolute() and direct_path.exists():
        return direct_path

    normalized = (task.file_path or "").replace("\\", "/").strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]

    if normalized.startswith("/data/"):
        data_relative = normalized.removeprefix("/data/")
        candidate = (BACKEND_ROOT / "data" / data_relative).resolve()
        if candidate.exists():
            return candidate

    if normalized.startswith("data/"):
        candidate = (BACKEND_ROOT / normalized).resolve()
        if candidate.exists():
            return candidate

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    candidate = (upload_root / normalized).resolve()
    if candidate.exists():
        return candidate

    candidate = (upload_root.parent.parent / normalized).resolve()
    if candidate.exists():
        return candidate

    return None


def iter_target_tasks(db: Session, *, task_id: str | None) -> list[Task]:
    query = db.query(Task).order_by(Task.created_at.asc(), Task.id.asc())
    if task_id:
        query = query.filter(Task.id == task_id)
    return list(query.all())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="为现有任务批量补齐上传缩略图。")
    parser.add_argument("--task-id", help="仅处理指定 task_id")
    parser.add_argument("--force", action="store_true", help="即使已有缩略图也重新生成")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    processed = 0
    generated = 0
    skipped_existing = 0
    skipped_missing_video = 0
    failed = 0

    db = SessionLocal()
    try:
        tasks = iter_target_tasks(db, task_id=args.task_id)
        if not tasks:
            print("未找到可处理的任务。")
            return 0

        for task in tasks:
            processed += 1
            preview_path = FileService.build_upload_preview_path(task.id)
            has_existing_preview = preview_path.exists() and preview_path.stat().st_size > 0
            if has_existing_preview and not args.force:
                skipped_existing += 1
                print(f"[skip-existing] {task.id} {task.display_name}")
                continue

            video_path = resolve_video_path(task)
            if video_path is None:
                skipped_missing_video += 1
                print(f"[skip-missing-video] {task.id} {task.display_name}")
                continue

            preview_result = FileService.generate_upload_preview(str(video_path), task.id)
            if preview_result:
                generated += 1
                print(f"[generated] {task.id} {task.display_name} -> {preview_result}")
            else:
                failed += 1
                print(f"[failed] {task.id} {task.display_name}")
    finally:
        db.close()

    print(
        "\n总结:"
        f" processed={processed}"
        f" generated={generated}"
        f" skipped_existing={skipped_existing}"
        f" skipped_missing_video={skipped_missing_video}"
        f" failed={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
