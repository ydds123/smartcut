import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import settings
from app.services.file_service import FileService
from app.services.video_processor import VideoProcessor


class TestTaskDirNaming(unittest.TestCase):
    def test_extract_original_upload_name(self):
        task_id = "abc-123"
        video_path = f"/tmp/uploads/{task_id}_demo video.mp4"
        original = VideoProcessor._extract_original_upload_name(task_id, video_path)
        self.assertEqual(original, "demo video.mp4")

    def test_sanitize_task_dir_name(self):
        raw_name = '黑色/环保\\短片:demo?.mp4'
        cleaned = VideoProcessor._sanitize_task_dir_name(raw_name)
        self.assertEqual(cleaned, "黑色_环保_短片_demo_.mp4")

    def test_unique_dir_numbering_with_extension(self):
        with TemporaryDirectory() as tmpdir:
            task_root = Path(tmpdir)

            first = VideoProcessor._ensure_unique_task_dir(task_root, "demo.mp4")
            second = VideoProcessor._ensure_unique_task_dir(task_root, "demo.mp4")
            third = VideoProcessor._ensure_unique_task_dir(task_root, "demo.mp4")

            self.assertEqual(first.name, "demo.mp4")
            self.assertEqual(second.name, "demo_001.mp4")
            self.assertEqual(third.name, "demo_002.mp4")

    def test_unique_dir_numbering_without_extension(self):
        with TemporaryDirectory() as tmpdir:
            task_root = Path(tmpdir)

            first = VideoProcessor._ensure_unique_task_dir(task_root, "clip")
            second = VideoProcessor._ensure_unique_task_dir(task_root, "clip")

            self.assertEqual(first.name, "clip")
            self.assertEqual(second.name, "clip_001")

    def test_delete_by_task_marker(self):
        original_task_dir = settings.TASK_DIR
        original_upload_dir = settings.UPLOAD_DIR

        try:
            with TemporaryDirectory() as tmpdir:
                task_root = Path(tmpdir) / "tasks"
                upload_root = Path(tmpdir) / "uploads"
                task_root.mkdir(parents=True, exist_ok=True)
                upload_root.mkdir(parents=True, exist_ok=True)

                settings.TASK_DIR = str(task_root)
                settings.UPLOAD_DIR = str(upload_root)

                task_id = "task-123"
                task_dir = task_root / "demo.mp4"
                task_dir.mkdir(parents=True, exist_ok=True)
                (task_dir / ".task_id").write_text(task_id, encoding="utf-8")

                upload_file = upload_root / f"{task_id}_demo.mp4"
                upload_file.write_bytes(b"test")

                FileService.delete_task_files(task_id)

                self.assertFalse(task_dir.exists())
                self.assertFalse(upload_file.exists())
        finally:
            settings.TASK_DIR = original_task_dir
            settings.UPLOAD_DIR = original_upload_dir


if __name__ == "__main__":
    unittest.main()
