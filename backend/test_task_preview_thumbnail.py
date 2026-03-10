import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.tasks import _resolve_preview_ms_from_scene, _resolve_task_preview, get_frame
from app.models.models import Base, Scene, Task
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

    def _create_scene(self, task_id: str, *, thumbnail_path: str | None, start_ms: int = 0, end_ms: int = 1000) -> Scene:
        scene = Scene(
            id=f"{task_id}_scene_0",
            task_id=task_id,
            sequence_index=0,
            start_ms=start_ms,
            end_ms=end_ms,
            file_path=None,
            thumbnail_path=thumbnail_path,
        )
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        return scene

    def test_resolve_preview_ms_from_scene_matches_scene_thumbnail_timing_rule(self):
        self.assertEqual(_resolve_preview_ms_from_scene(0, 1000), 500)
        self.assertEqual(_resolve_preview_ms_from_scene(1000, 1800), 1400)
        self.assertEqual(_resolve_preview_ms_from_scene(0, 220), 110)

    def test_resolve_task_preview_prefers_review_frame_when_scene_data_exists(self):
        task = self._create_task(
            "task-preview-review-frame",
            file_path=str(Path(self.tempdir.name) / "video.mp4"),
        )
        scene_thumb_path = Path(self.tempdir.name) / "scene_000_thumb.jpg"
        Path(task.file_path).write_bytes(b"video-bytes")
        scene_thumb_path.write_bytes(b"jpeg-bytes")
        self._create_scene(task.id, thumbnail_path=str(scene_thumb_path), start_ms=0, end_ms=1000)

        preview_url = _resolve_task_preview(task, self.db)

        self.assertEqual(preview_url, f"/api/tasks/{task.id}/frame?t=500")

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

    def test_resolve_task_preview_falls_back_to_scene_thumbnail_when_video_missing(self):
        task = self._create_task(
            "task-preview-scene-thumb-fallback",
            file_path=str(Path(self.tempdir.name) / "missing.mp4"),
        )
        scene_thumb_path = Path(self.tempdir.name) / "scene_001_thumb.jpg"
        scene_thumb_path.write_bytes(b"jpeg-bytes")
        self._create_scene(task.id, thumbnail_path=str(scene_thumb_path), start_ms=0, end_ms=1000)

        preview_url = _resolve_task_preview(task, self.db)

        self.assertEqual(preview_url, FileService.to_public_data_path(str(scene_thumb_path)))

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
