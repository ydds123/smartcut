import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from starlette.requests import Request

from app.api.progress import _build_progress_event
from app.api.tasks import (
    _build_job_id,
    _build_retry_policy,
    _enqueue_with_dedup,
    _normalize_idempotency_key,
)
from fastapi import HTTPException


def _make_request_with_headers(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": headers,
    }
    return Request(scope)


class TestTaskQueueIdempotency(unittest.TestCase):
    def test_normalize_idempotency_key(self):
        normalized = _normalize_idempotency_key("  abc 123/\\中文  ")
        self.assertEqual(normalized, "abc-123----")

    def test_build_job_id_with_idempotency_key(self):
        request = _make_request_with_headers([(b"idempotency-key", b"fixed-key")])
        job_id, deterministic = _build_job_id("task-1", "process", request)
        self.assertTrue(deterministic)
        self.assertEqual(job_id, "task:task-1:process:fixed-key")

    def test_build_job_id_without_idempotency_key(self):
        request = _make_request_with_headers([])
        job_id, deterministic = _build_job_id("task-1", "process", request)
        self.assertFalse(deterministic)
        self.assertTrue(job_id.startswith("task:task-1:process:"))
        self.assertGreater(len(job_id), len("task:task-1:process:"))

    def test_build_retry_policy_none_when_retry_disabled(self):
        with patch("app.api.tasks.settings", SimpleNamespace(RQ_JOB_RETRY_MAX=0)):
            self.assertIsNone(_build_retry_policy())

    def test_enqueue_with_dedup_reuses_active_job(self):
        class _ActiveJob:
            id = "job-active"

            def get_status(self, refresh=False):
                return "queued"

        class _Queue:
            def fetch_job(self, job_id):
                return _ActiveJob()

            def enqueue(self, *args, **kwargs):
                raise AssertionError("should not enqueue when active job exists")

        job, dedup = _enqueue_with_dedup(
            _Queue(),
            job_id="job-active",
            func=lambda: None,
            args=[],
            job_timeout=10,
            result_ttl=10,
        )
        self.assertTrue(dedup)
        self.assertEqual(job.id, "job-active")

    def test_enqueue_with_dedup_rejects_finished_job_conflict(self):
        class _FinishedJob:
            id = "job-done"

            def get_status(self, refresh=False):
                return "finished"

        class _Queue:
            def fetch_job(self, job_id):
                return _FinishedJob()

            def enqueue(self, *args, **kwargs):
                raise AssertionError("should not enqueue when key conflicts with finished job")

        with self.assertRaises(HTTPException) as ctx:
            _enqueue_with_dedup(
                _Queue(),
                job_id="job-done",
                func=lambda: None,
                args=[],
                job_timeout=10,
                result_ttl=10,
            )
        self.assertEqual(ctx.exception.status_code, 409)


class TestProgressEventSchema(unittest.TestCase):
    def test_progress_event_contains_type_and_timestamp(self):
        encoded = _build_progress_event(
            event_type="progress",
            task_id="task-1",
            status="PROCESSING",
            progress=42,
            total_scenes=12,
        )
        payload = json.loads(encoded.removeprefix("data: ").strip())
        self.assertEqual(payload["type"], "progress")
        self.assertEqual(payload["task_id"], "task-1")
        self.assertEqual(payload["status"], "PROCESSING")
        self.assertEqual(payload["progress"], 42)
        self.assertEqual(payload["total_scenes"], 12)
        self.assertIn("timestamp", payload)

    def test_error_event_contains_error_fields(self):
        encoded = _build_progress_event(
            event_type="error",
            task_id="task-2",
            error_code="db_query_failed",
            error_message="database query failed",
        )
        payload = json.loads(encoded.removeprefix("data: ").strip())
        self.assertEqual(payload["type"], "error")
        self.assertEqual(payload["task_id"], "task-2")
        self.assertEqual(payload["error_code"], "db_query_failed")
        self.assertEqual(payload["error_message"], "database query failed")


if __name__ == "__main__":
    unittest.main()
