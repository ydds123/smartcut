import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models.models import Scene
from app.workers.video_tasks import (
    _build_incremental_plan,
    _collect_successful_scene_results,
    _materialize_file,
)


def _scene_row(
    task_id: str,
    index: int,
    start_ms: int,
    end_ms: int,
    file_path: str | None,
    thumbnail_path: str | None,
) -> Scene:
    return Scene(
        id=f"{task_id}_scene_{index}",
        task_id=task_id,
        sequence_index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        file_path=file_path,
        thumbnail_path=thumbnail_path,
    )


class TestIncrementalSplit(unittest.TestCase):
    def test_build_incremental_plan_reuses_exact_matches(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            video_a = base / "a.mp4"
            thumb_a = base / "a.jpg"
            video_b = base / "b.mp4"
            thumb_b = base / "b.jpg"
            video_a.write_bytes(b"video-a")
            thumb_a.write_bytes(b"thumb-a")
            video_b.write_bytes(b"video-b")
            thumb_b.write_bytes(b"thumb-b")

            existing = [
                _scene_row("task-1", 0, 0, 1000, str(video_a), str(thumb_a)),
                _scene_row("task-1", 1, 1000, 2200, str(video_b), str(thumb_b)),
            ]
            scenes = [(0, 1000), (1000, 2200)]

            reused, to_render = _build_incremental_plan(scenes, existing)

            self.assertEqual(set(reused.keys()), {0, 1})
            self.assertEqual(to_render, [])

    def test_build_incremental_plan_marks_missing_assets_for_render(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            video_a = base / "a.mp4"
            thumb_a = base / "a.jpg"
            video_b = base / "b.mp4"
            video_a.write_bytes(b"video-a")
            thumb_a.write_bytes(b"thumb-a")
            video_b.write_bytes(b"video-b")
            # b 的缩略图缺失，应进入重切队列。

            existing = [
                _scene_row("task-1", 0, 0, 1000, str(video_a), str(thumb_a)),
                _scene_row("task-1", 1, 1000, 2200, str(video_b), str(base / "missing.jpg")),
            ]
            scenes = [(0, 1000), (1000, 2200), (2200, 4000)]

            reused, to_render = _build_incremental_plan(scenes, existing)

            self.assertEqual(set(reused.keys()), {0})
            self.assertEqual(to_render, [(1, 1000, 2200), (2, 2200, 4000)])

    def test_materialize_file_copies_when_link_unavailable(self):
        with TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            src = base / "source.mp4"
            dst = base / "nested" / "target.mp4"
            src.write_bytes(b"abc123")

            _materialize_file(str(src), dst)

            self.assertTrue(dst.exists())
            self.assertEqual(dst.read_bytes(), b"abc123")

    def test_collect_successful_scene_results_filters_failed_items(self):
        scenes = [(0, 1000), (1000, 2200), (2200, 3000)]
        output_files = ["scene_000.mp4", None, "scene_002.mp4"]
        thumbnails = ["scene_000_thumb.jpg", None, None]

        successful, failed_count = _collect_successful_scene_results(scenes, output_files, thumbnails)

        self.assertEqual(failed_count, 1)
        self.assertEqual(len(successful), 2)
        self.assertEqual(successful[0][0:3], (0, 1000, "scene_000.mp4"))
        self.assertEqual(successful[1][0:3], (2200, 3000, "scene_002.mp4"))


if __name__ == "__main__":
    unittest.main()
