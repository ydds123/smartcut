import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers, UploadFile

from app.api.upload import upload_video
from app.models.models import Base


def _upload_file(data: bytes, content_type: str, filename: str = "demo.mp4") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class TestUploadAutoPreview(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.tempdir = tempfile.TemporaryDirectory()
        self.upload_path = Path(self.tempdir.name) / "demo.mp4"
        self.upload_path.write_bytes(b"video-bytes")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tempdir.cleanup()

    async def test_upload_auto_enqueues_review_and_returns_queued_task(self):
        file = _upload_file(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32, "video/mp4")

        def _mark_review_queued(db, *, task, payload, job_id):
            task.status = "QUEUED"
            task.active_operation = "review"
            task.active_job_id = job_id
            db.commit()
            db.refresh(task)
            return {"status": "QUEUED", "job_id": job_id, "deduplicated": False}

        with patch("app.api.upload.enforce_rate_limit"), patch(
            "app.api.upload.FileService.validate_video_type",
            new=AsyncMock(return_value=True),
        ), patch(
            "app.api.upload.FileService.save_upload",
            new=AsyncMock(return_value=str(self.upload_path)),
        ), patch(
            "app.api.upload.FileService.get_video_duration_ms",
            return_value=12_345,
        ), patch(
            "app.api.upload.FileService.generate_upload_preview",
            return_value=None,
        ), patch(
            "app.api.upload.enqueue_review_task",
            side_effect=_mark_review_queued,
        ) as enqueue_review_task, patch(
            "app.api.upload.trigger_auto_analysis_for_task",
            return_value=None,
        ) as trigger_auto_analysis_for_task:
            task = await upload_video(object(), file=file, displayName="demo.mp4", db=self.db)

        self.assertEqual(task.status, "QUEUED")
        self.assertEqual(task.active_operation, "review")
        self.assertEqual(task.active_job_id, f"task:{task.id}:review:auto-upload")
        enqueue_review_task.assert_called_once()
        trigger_auto_analysis_for_task.assert_called_once()

    async def test_upload_marks_task_failed_when_auto_preview_enqueue_fails(self):
        file = _upload_file(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32, "video/mp4")

        with patch("app.api.upload.enforce_rate_limit"), patch(
            "app.api.upload.FileService.validate_video_type",
            new=AsyncMock(return_value=True),
        ), patch(
            "app.api.upload.FileService.save_upload",
            new=AsyncMock(return_value=str(self.upload_path)),
        ), patch(
            "app.api.upload.FileService.get_video_duration_ms",
            return_value=12_345,
        ), patch(
            "app.api.upload.FileService.generate_upload_preview",
            return_value=None,
        ), patch(
            "app.api.upload.enqueue_review_task",
            side_effect=HTTPException(status_code=503, detail="Queue unavailable"),
        ), patch(
            "app.api.upload.trigger_auto_analysis_for_task",
            return_value=None,
        ):
            task = await upload_video(object(), file=file, displayName="demo.mp4", db=self.db)

        self.assertEqual(task.status, "FAILED")
        self.assertEqual(task.progress, 0)
        self.assertIsNone(task.active_operation)
        self.assertIsNone(task.active_job_id)
        self.assertIn("Queue unavailable", task.review_notes or "")


if __name__ == "__main__":
    unittest.main()
