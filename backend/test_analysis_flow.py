import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from starlette.requests import Request

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import analysis as analysis_api
from app.core import config as config_module
from app.models.models import AnalysisRun, AnalysisSettings, Base, Task
from app.services.analysis_provider import GeminiProviderAdapter, build_analysis_provider_adapter
from app.services.analysis_service import (
    ANALYSIS_API_KEY_SOURCE_DOTENV_FILE,
    ANALYSIS_API_KEY_SOURCE_MISSING,
    ANALYSIS_API_KEY_SOURCE_PROCESS_ENV,
    ANALYSIS_STATUS_FAILED,
    ANALYSIS_STATUS_QUEUED,
    ANALYSIS_STATUS_SUCCEEDED,
    AnalysisApiKeyInfo,
    build_latest_analysis_response,
    build_latest_analysis_batch_response,
    create_analysis_run,
    get_recoverable_active_analysis_run,
)


class _DummyGeminiClient:
    def __init__(self):
        self.deleted_file_name = None

    def test_model(self, *, model: str) -> int:
        return 123 if model else 1

    def upload_video(self, file_path: str, *, display_name: str | None = None) -> dict:
        return {
            "name": "files/abc",
            "uri": "gs://bucket/video.mp4",
            "mime_type": "video/mp4",
            "display_name": display_name or file_path,
        }

    def generate_story_intro(
        self,
        *,
        model: str,
        prompt: str,
        video_file_uri: str,
        mime_type: str = "video/mp4",
    ) -> tuple[dict, dict]:
        return (
            {
                "story_intro_markdown": "ok",
                "summary": "summary",
                "provider": "gemini",
                "model": model,
            },
            {
                "video_file_uri": video_file_uri,
                "mime_type": mime_type,
                "prompt": prompt,
            },
        )

    def delete_file(self, file_name: str) -> None:
        self.deleted_file_name = file_name


class TestAnalysisProviderAdapter(unittest.TestCase):
    def test_build_gemini_adapter_from_factory(self):
        shadow_settings = AnalysisSettings(
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-2.5-flash",
            prompt_template="prompt",
            analysis_enabled=True,
            request_timeout_sec=120,
        )
        client = _DummyGeminiClient()
        with patch(
            "app.services.analysis_provider.settings",
            SimpleNamespace(
                ANALYSIS_API_KEY="unit-test-key",
                ANALYSIS_FILE_POLL_INTERVAL_SEC=1.0,
                ANALYSIS_FILE_MAX_WAIT_SEC=30,
            ),
        ), patch(
            "app.services.analysis_provider.GeminiClient",
            return_value=client,
        ):
            adapter = build_analysis_provider_adapter(shadow_settings)

        self.assertIsInstance(adapter, GeminiProviderAdapter)
        self.assertEqual(adapter.test_connection(model="gemini-2.5-flash"), 123)
        uploaded = adapter.upload_video("/tmp/video.mp4", display_name="demo")
        self.assertEqual(uploaded.uri, "gs://bucket/video.mp4")
        normalized, raw = adapter.generate_story_intro(
            model="gemini-2.5-flash",
            prompt="hello",
            uploaded_video=uploaded,
        )
        self.assertEqual(normalized["provider"], "gemini")
        self.assertEqual(raw["video_file_uri"], "gs://bucket/video.mp4")
        adapter.cleanup(uploaded)
        self.assertEqual(client.deleted_file_name, "files/abc")

    def test_build_adapter_rejects_unsupported_provider(self):
        shadow_settings = AnalysisSettings(
            provider="openai_compatible",
            base_url="https://example.com",
            model="gpt",
            prompt_template="prompt",
            analysis_enabled=True,
            request_timeout_sec=120,
        )
        with patch(
            "app.services.analysis_provider.settings",
            SimpleNamespace(
                ANALYSIS_API_KEY="unit-test-key",
                ANALYSIS_FILE_POLL_INTERVAL_SEC=1.0,
                ANALYSIS_FILE_MAX_WAIT_SEC=30,
            ),
        ):
            with self.assertRaises(ValueError):
                build_analysis_provider_adapter(shadow_settings)


class TestAnalysisRunConflictAndBatch(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX ux_analysis_runs_active_unique "
                "ON analysis_runs (task_id, analysis_type) "
                "WHERE status IN ('QUEUED', 'RUNNING');"
            )
        self.session_factory = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def _seed_basics(self, db):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add_all(
            [
                Task(
                    id="task-1",
                    display_name="Task 1",
                    file_path="/tmp/1.mp4",
                    file_size=1,
                    status="PENDING",
                    progress=0,
                    created_at=now,
                    updated_at=now,
                ),
                Task(
                    id="task-2",
                    display_name="Task 2",
                    file_path="/tmp/2.mp4",
                    file_size=1,
                    status="PENDING",
                    progress=0,
                    created_at=now,
                    updated_at=now,
                ),
                Task(
                    id="task-3",
                    display_name="Task 3",
                    file_path="/tmp/3.mp4",
                    file_size=1,
                    status="PENDING",
                    progress=0,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        settings_model = AnalysisSettings(
            id="default",
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-2.5-flash",
            prompt_template="prompt",
            analysis_enabled=True,
            request_timeout_sec=180,
            created_at=now,
            updated_at=now,
        )
        db.add(settings_model)
        db.commit()
        return settings_model

    def test_create_analysis_run_returns_active_when_unique_conflicts(self):
        db = self.session_factory()
        settings_model = self._seed_basics(db)
        first_run, first_dedup = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_QUEUED,
        )
        self.assertFalse(first_dedup)

        second_run, second_dedup = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_QUEUED,
        )
        self.assertTrue(second_dedup)
        self.assertEqual(second_run.id, first_run.id)
        db.close()

    def test_create_analysis_run_recovers_stale_active_run(self):
        db = self.session_factory()
        settings_model = self._seed_basics(db)
        first_run, _ = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_QUEUED,
        )
        stale_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        first_run.created_at = stale_at
        first_run.updated_at = stale_at
        db.add(first_run)
        db.commit()

        with patch("app.services.analysis_service._is_rq_job_active", return_value=False):
            active = get_recoverable_active_analysis_run(
                db,
                task_id="task-1",
                source="unit_test",
            )

        self.assertIsNone(active)
        stale_run = db.query(AnalysisRun).filter(AnalysisRun.id == first_run.id).first()
        self.assertIsNotNone(stale_run)
        self.assertEqual(stale_run.status, ANALYSIS_STATUS_FAILED)
        db.close()

    def test_get_recoverable_active_run_keeps_fresh_queued_during_enqueue_race_window(self):
        db = self.session_factory()
        settings_model = self._seed_basics(db)
        first_run, _ = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_QUEUED,
        )

        with patch("app.services.analysis_service._is_rq_job_active", return_value=False):
            active = get_recoverable_active_analysis_run(
                db,
                task_id="task-1",
                source="unit_test",
            )

        self.assertIsNotNone(active)
        self.assertEqual(active.id, first_run.id)
        self.assertEqual(active.status, ANALYSIS_STATUS_QUEUED)
        db.close()

    def test_latest_read_releases_stale_active_run_and_returns_failed_retryable(self):
        db = self.session_factory()
        settings_model = self._seed_basics(db)
        run, _ = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_QUEUED,
        )
        stale_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        run.created_at = stale_at
        run.updated_at = stale_at
        db.add(run)
        db.commit()

        task = db.query(Task).filter(Task.id == "task-1").first()
        self.assertIsNotNone(task)

        with patch("app.services.analysis_service._is_rq_job_active", return_value=False), patch(
            "app.services.analysis_service.has_analysis_api_key",
            return_value=True,
        ):
            payload = build_latest_analysis_response(db, task=task)

        self.assertEqual(payload["status"], ANALYSIS_STATUS_FAILED)
        self.assertTrue(payload["can_retry"])
        self.assertEqual(payload["run_id"], run.id)
        db.close()

    def test_latest_batch_response_semantics(self):
        db = self.session_factory()
        settings_model = self._seed_basics(db)

        run_success, _ = create_analysis_run(
            db,
            task_id="task-1",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_SUCCEEDED,
        )
        run_success.status = ANALYSIS_STATUS_SUCCEEDED
        run_success.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(run_success)
        db.commit()

        run_failed, _ = create_analysis_run(
            db,
            task_id="task-2",
            settings_model=settings_model,
            status=ANALYSIS_STATUS_FAILED,
            error_message="boom",
        )
        run_failed.status = ANALYSIS_STATUS_FAILED
        run_failed.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(run_failed)
        db.commit()

        with patch("app.services.analysis_service.has_analysis_api_key", return_value=True):
            items = build_latest_analysis_batch_response(
                db,
                task_ids=["task-1", "task-2", "task-3", "task-1"],
            )

        self.assertEqual(len(items), 3)
        item_map = {item["task_id"]: item for item in items}
        self.assertEqual(item_map["task-1"]["status"], ANALYSIS_STATUS_SUCCEEDED)
        self.assertFalse(item_map["task-1"]["can_retry"])
        self.assertEqual(item_map["task-2"]["status"], ANALYSIS_STATUS_FAILED)
        self.assertTrue(item_map["task-2"]["can_retry"])
        self.assertEqual(item_map["task-3"]["status"], "NOT_STARTED")
        self.assertTrue(item_map["task-3"]["can_retry"])
        db.close()


class TestAnalysisApiKeySourceConfig(unittest.TestCase):
    def test_process_env_takes_priority_over_dotenv(self):
        with patch.object(config_module, "INITIAL_PROCESS_ENV_ANALYSIS_API_KEY", "process-key"), patch.object(
            config_module,
            "INITIAL_DOTENV_ANALYSIS_API_KEY",
            "dotenv-key",
        ):
            test_settings = config_module.Settings(ANALYSIS_API_KEY="active-key")
            self.assertEqual(test_settings.analysis_api_key_source, ANALYSIS_API_KEY_SOURCE_PROCESS_ENV)

    def test_dotenv_file_is_detected_when_process_env_missing(self):
        with patch.object(config_module, "INITIAL_PROCESS_ENV_ANALYSIS_API_KEY", ""), patch.object(
            config_module,
            "INITIAL_DOTENV_ANALYSIS_API_KEY",
            "dotenv-key",
        ):
            test_settings = config_module.Settings(ANALYSIS_API_KEY="active-key")
            self.assertEqual(test_settings.analysis_api_key_source, ANALYSIS_API_KEY_SOURCE_DOTENV_FILE)

    def test_missing_source_is_reported_when_no_runtime_key(self):
        with patch.object(config_module, "INITIAL_PROCESS_ENV_ANALYSIS_API_KEY", ""), patch.object(
            config_module,
            "INITIAL_DOTENV_ANALYSIS_API_KEY",
            "",
        ):
            test_settings = config_module.Settings(ANALYSIS_API_KEY="")
            self.assertEqual(test_settings.analysis_api_key_source, ANALYSIS_API_KEY_SOURCE_MISSING)


class TestOpenEnvFileEndpoint(unittest.TestCase):
    @staticmethod
    def _build_request(*, origin: str | None, trusted_header: str | None) -> Request:
        headers: list[tuple[bytes, bytes]] = []
        if origin is not None:
            headers.append((b"origin", origin.encode("utf-8")))
        if trusted_header is not None:
            headers.append(
                (
                    analysis_api.OPEN_ENV_FILE_HEADER_NAME.lower().encode("utf-8"),
                    trusted_header.encode("utf-8"),
                )
            )

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/analysis/settings/open-env-file",
            "headers": headers,
            "client": ("127.0.0.1", 5173),
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        return Request(scope, receive)

    def test_open_env_file_rejects_origin_mismatch(self):
        with patch("app.api.analysis._is_local_loopback_request", return_value=True), patch(
            "app.api.analysis._is_allowed_local_origin",
            return_value=False,
        ):
            with self.assertRaises(HTTPException) as context:
                analysis_api.open_analysis_settings_env_file(
                    self._build_request(
                        origin="http://malicious.local",
                        trusted_header=analysis_api.OPEN_ENV_FILE_HEADER_VALUE,
                    )
                )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail, "当前请求来源不允许触发本地配置文件操作")

    def test_open_env_file_rejects_missing_trusted_header(self):
        with patch("app.api.analysis._is_local_loopback_request", return_value=True), patch(
            "app.api.analysis._is_allowed_local_origin",
            return_value=True,
        ):
            with self.assertRaises(HTTPException) as context:
                analysis_api.open_analysis_settings_env_file(
                    self._build_request(origin="http://127.0.0.1:5173", trusted_header=None)
                )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail, "缺少受信任的本地操作标识")

    def test_open_env_file_rejects_process_env_source(self):
        with patch("app.api.analysis._is_local_loopback_request", return_value=True), patch(
            "app.api.analysis._is_allowed_local_origin",
            return_value=True,
        ), patch(
            "app.api.analysis.get_analysis_api_key_info",
            return_value=AnalysisApiKeyInfo(
                has_api_key=True,
                source=ANALYSIS_API_KEY_SOURCE_PROCESS_ENV,
                env_file_path=Path("/tmp/backend/.env"),
                env_file_exists=True,
            ),
        ):
            with self.assertRaises(HTTPException) as context:
                analysis_api.open_analysis_settings_env_file(
                    self._build_request(
                        origin="http://127.0.0.1:5173",
                        trusted_header=analysis_api.OPEN_ENV_FILE_HEADER_VALUE,
                    )
                )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "当前 API Key 来自进程环境变量，不对应 .env 文件")

    def test_open_env_file_opens_recommended_file_when_key_missing(self):
        with patch("app.api.analysis._is_local_loopback_request", return_value=True), patch(
            "app.api.analysis._is_allowed_local_origin",
            return_value=True,
        ), patch(
            "app.api.analysis.get_analysis_api_key_info",
            return_value=AnalysisApiKeyInfo(
                has_api_key=False,
                source=ANALYSIS_API_KEY_SOURCE_MISSING,
                env_file_path=Path("/tmp/backend/.env"),
                env_file_exists=True,
            ),
        ), patch(
            "app.api.analysis.can_open_env_file_on_platform",
            return_value=True,
        ), patch(
            "app.api.analysis._consume_open_env_file_rate_limit",
            return_value=True,
        ), patch(
            "app.api.analysis.open_analysis_env_file",
            return_value=(True, "已打开配置文件"),
        ):
            response = analysis_api.open_analysis_settings_env_file(
                self._build_request(
                    origin="http://127.0.0.1:5173",
                    trusted_header=analysis_api.OPEN_ENV_FILE_HEADER_VALUE,
                )
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "已打开配置文件")
        self.assertEqual(response["path"], "/tmp/backend/.env")


if __name__ == "__main__":
    unittest.main()
