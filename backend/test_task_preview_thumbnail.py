import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.tasks import _resolve_task_preview, get_frame
from app.models.models import Base, Task
from app.services.file_service import FileService


class TestTaskPreviewThumbnail(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tempdir.cleanup()

    def _create_task(self, task_id: str, *, file_path: str) -> Task:
        task = Task(
            id=task_id,
            display_name=f"Task {task_id}",
            file_path=file_path,
            file_size=1,
            duration_ms=7_000,
            status="REVIEW_PENDING",
            progress=100,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def test_resolve_task_preview_returns_none_when_video_file_is_missing(self):
        task = self._create_task(
            "task-preview-missing",
            file_path=str(Path(self.tempdir.name) / "missing.mp4"),
        )

        self.assertIsNone(_resolve_task_preview(task, self.db))

    def test_resolve_task_preview_prefers_existing_static_upload_preview(self):
        task = self._create_task(
            "task-preview-static",
            file_path=str(Path(self.tempdir.name) / "missing.mp4"),
        )
        preview_path = Path(self.tempdir.name) / f"{task.id}_preview.jpg"
        preview_path.write_bytes(b"jpeg-bytes")

        with patch("app.api.tasks.FileService.build_upload_preview_path", return_value=preview_path):
            preview_url = _resolve_task_preview(task, self.db)

        self.assertEqual(preview_url, FileService.to_public_data_path(str(preview_path)))

    def test_get_frame_returns_404_when_video_file_is_missing(self):
        task = self._create_task(
            "task-frame-missing",
            file_path=str(Path(self.tempdir.name) / "missing.mp4"),
        )

        with self.assertRaises(HTTPException) as context:
            get_frame(task.id, t=500, db=self.db)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Video file not found")

    def test_get_frame_logs_and_returns_500_when_ffmpeg_extraction_fails(self):
        video_path = Path(self.tempdir.name) / "demo.mp4"
        video_path.write_bytes(b"video-bytes")
        task = self._create_task("task-frame-fail", file_path=str(video_path))

        failed_process = SimpleNamespace(returncode=1, stderr=b"ffmpeg boom")

        with patch("app.api.tasks.subprocess.run", return_value=failed_process), patch(
            "app.api.tasks.log_event"
        ) as log_event:
            with self.assertRaises(HTTPException) as context:
                get_frame(task.id, t=500, db=self.db)

        self.assertEqual(context.exception.status_code, 500)
        self.assertEqual(context.exception.detail, "Frame extraction failed")
        log_event.assert_called_once()
        _, level, event_name = log_event.call_args.args
        self.assertEqual(level, 30)
        self.assertEqual(event_name, "task_frame_extraction_failed")
        self.assertEqual(log_event.call_args.kwargs["task_id"], task.id)
        self.assertEqual(log_event.call_args.kwargs["time_ms"], 500)
        self.assertEqual(log_event.call_args.kwargs["video_path"], str(video_path))
        self.assertEqual(log_event.call_args.kwargs["returncode"], 1)
        self.assertEqual(log_event.call_args.kwargs["ffmpeg_stderr"], "ffmpeg boom")


if __name__ == "__main__":
    unittest.main()
