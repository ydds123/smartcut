import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.tasks import enqueue_review_task, preview_local_precision_review
from app.models.models import Base, Task
from app.schemas.task import (
    LocalPrecisionPreviewRequest,
    ProcessConfigOverride,
    ProcessTaskRequest,
)


class _DummyVideoProcessor:
    created_instances: list["_DummyVideoProcessor"] = []

    def __init__(self, task_id: str, video_path: str, processing_config=None):
        self.task_id = task_id
        self.video_path = video_path
        self.processing_config = dict(processing_config or {})
        self.task_dir = Path(tempfile.mkdtemp(prefix="dummy-local-precision-"))
        _DummyVideoProcessor.created_instances.append(self)

    def detect_scenes_only(self, progress_callback=None):
        return {
            "scenes": [
                (0, 1200),
                (1200, 3800),
                (3800, 7000),
            ],
            "duration_ms": 7000,
            "report": {
                "detector": "mock-precision",
                "elapsed_ms": 1234,
            },
        }


class TestReviewFlowOptimization(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.tempdir = tempfile.TemporaryDirectory()
        self.video_path = Path(self.tempdir.name) / "demo.mp4"
        self.video_path.write_bytes(b"not-a-real-video")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tempdir.cleanup()
        _DummyVideoProcessor.created_instances.clear()

    def _create_task(self, task_id: str, **overrides) -> Task:
        defaults = {
            "id": task_id,
            "display_name": f"Task {task_id}",
            "file_path": str(self.video_path),
            "file_size": 1,
            "duration_ms": 7000,
            "status": "PENDING",
            "progress": 0,
        }
        defaults.update(overrides)
        task = Task(**defaults)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def test_enqueue_review_task_defaults_to_fast_without_override(self):
        task = self._create_task("task-fast-default")

        with patch("app.api.tasks._get_queue", return_value=object()), patch(
            "app.api.tasks._enqueue_with_dedup",
            return_value=(SimpleNamespace(id="job-fast"), False),
        ):
            response = enqueue_review_task(
                self.db,
                task=task,
                payload=ProcessTaskRequest(),
                job_id="job-fast",
            )

        self.db.refresh(task)
        resolved_config = json.loads(task.resolved_config)
        self.assertEqual(response["resolved_config"]["detection_mode"], "fast")
        self.assertFalse(response["resolved_config"]["use_transnet"])
        self.assertEqual(resolved_config["detection_mode"], "fast")
        self.assertFalse(resolved_config["use_transnet"])

    def test_enqueue_review_task_preserves_explicit_precision_override(self):
        task = self._create_task("task-precision-override")

        with patch("app.api.tasks._get_queue", return_value=object()), patch(
            "app.api.tasks._enqueue_with_dedup",
            return_value=(SimpleNamespace(id="job-precision"), False),
        ):
            response = enqueue_review_task(
                self.db,
                task=task,
                payload=ProcessTaskRequest(
                    override_config=ProcessConfigOverride(detection_mode="precision")
                ),
                job_id="job-precision",
            )

        self.db.refresh(task)
        resolved_config = json.loads(task.resolved_config)
        self.assertEqual(response["resolved_config"]["detection_mode"], "precision")
        self.assertTrue(response["resolved_config"]["use_transnet"])
        self.assertEqual(resolved_config["detection_mode"], "precision")
        self.assertTrue(resolved_config["use_transnet"])

    def test_local_precision_preview_clips_to_target_range_without_mutating_task(self):
        user_edited_scenes = [
            {"start_ms": 0, "end_ms": 1000},
            {"start_ms": 1000, "end_ms": 2000},
            {"start_ms": 2000, "end_ms": 3000},
            {"start_ms": 3000, "end_ms": 4000},
            {"start_ms": 4000, "end_ms": 5000},
            {"start_ms": 5000, "end_ms": 6000},
        ]
        detection_result = {
            "scenes": [
                {"start_ms": 0, "end_ms": 2000},
                {"start_ms": 2000, "end_ms": 4000},
                {"start_ms": 4000, "end_ms": 6000},
            ],
            "duration_ms": 7000,
            "report": {"detector": "fast"},
        }
        resolved_config = {
            "detection_mode": "fast",
            "use_transnet": False,
            "frame_skip": 2,
            "scene_threshold": 31.5,
        }
        task = self._create_task(
            "task-local-preview",
            status="REVIEW_PENDING",
            progress=60,
            detection_result=json.dumps(detection_result, ensure_ascii=False),
            user_edited_scenes=json.dumps(user_edited_scenes, ensure_ascii=False),
            resolved_config=json.dumps(resolved_config, ensure_ascii=False),
        )
        original_snapshot = {
            "status": task.status,
            "progress": task.progress,
            "user_edited_scenes": task.user_edited_scenes,
            "detection_result": task.detection_result,
            "resolved_config": task.resolved_config,
        }
        subclip_calls: list[tuple[int, int]] = []

        def _fake_build_local_precision_subclip(*, input_video_path, output_video_path, start_ms, end_ms):
            self.assertEqual(input_video_path, self.video_path)
            output_video_path.write_bytes(b"clip-bytes")
            subclip_calls.append((start_ms, end_ms))

        with patch(
            "app.api.tasks._build_local_precision_subclip",
            side_effect=_fake_build_local_precision_subclip,
        ), patch(
            "app.api.tasks.VideoProcessor",
            _DummyVideoProcessor,
        ):
            response = preview_local_precision_review(
                task.id,
                body=LocalPrecisionPreviewRequest(anchor_scene_index=3, radius=2),
                db=self.db,
            )

        self.db.refresh(task)
        self.assertEqual(subclip_calls, [(0, 7000)])
        self.assertEqual(
            response["target_range"],
            {
                "start_ms": 1000,
                "end_ms": 6000,
                "start_index": 1,
                "end_index": 5,
            },
        )
        self.assertEqual(response["original_scenes"], user_edited_scenes[1:6])
        self.assertEqual(
            response["proposed_scenes"],
            [
                {"start_ms": 1000, "end_ms": 1200},
                {"start_ms": 1200, "end_ms": 3800},
                {"start_ms": 3800, "end_ms": 6000},
            ],
        )
        self.assertEqual(task.status, original_snapshot["status"])
        self.assertEqual(task.progress, original_snapshot["progress"])
        self.assertEqual(task.user_edited_scenes, original_snapshot["user_edited_scenes"])
        self.assertEqual(task.detection_result, original_snapshot["detection_result"])
        self.assertEqual(task.resolved_config, original_snapshot["resolved_config"])

        self.assertEqual(len(_DummyVideoProcessor.created_instances), 1)
        processor = _DummyVideoProcessor.created_instances[0]
        self.assertEqual(processor.processing_config["detection_mode"], "precision")
        self.assertTrue(processor.processing_config["use_transnet"])
        self.assertEqual(processor.processing_config["frame_skip"], 0)
        self.assertEqual(processor.processing_config["scene_threshold"], 31.5)

        report = response["report"]
        self.assertTrue(report["local_precision"])
        self.assertEqual(report["context_padding_ms"], 1000)
        self.assertEqual(report["clip_start_ms"], 0)
        self.assertEqual(report["clip_end_ms"], 7000)
        self.assertEqual(report["target_scene_count"], 5)
        self.assertEqual(report["proposed_scene_count"], 3)
        self.assertEqual(report["detector"], "mock-precision")


if __name__ == "__main__":
    unittest.main()
