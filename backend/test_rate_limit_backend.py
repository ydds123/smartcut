import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

import app.core.rate_limit as rate_limit
from app.core.config import settings


def _request(
    path: str = "/api/tasks/t-1/process",
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": headers or [],
        "client": (client_host, 12345),
    }
    return Request(scope)


class TestRateLimitBackend(unittest.TestCase):
    def setUp(self) -> None:
        with rate_limit._hits_lock:
            rate_limit._hits.clear()
        rate_limit._redis_warned = False

    def test_redis_failure_fallback_to_memory_and_still_limits(self):
        original_enabled = settings.RATE_LIMIT_ENABLED
        original_backend = settings.RATE_LIMIT_BACKEND
        try:
            settings.RATE_LIMIT_ENABLED = True
            settings.RATE_LIMIT_BACKEND = "redis"

            req = _request()
            with patch("app.core.rate_limit._enforce_rate_limit_redis", side_effect=RuntimeError("redis down")):
                rate_limit.enforce_rate_limit(req, "task_mutation", max_requests=2, window_sec=60)
                rate_limit.enforce_rate_limit(req, "task_mutation", max_requests=2, window_sec=60)

                with self.assertRaises(HTTPException) as ctx:
                    rate_limit.enforce_rate_limit(req, "task_mutation", max_requests=2, window_sec=60)
                self.assertEqual(ctx.exception.status_code, 429)
                retry_after = int(ctx.exception.headers.get("Retry-After", "0"))
                self.assertGreaterEqual(retry_after, 1)
                self.assertLessEqual(retry_after, 60)
        finally:
            settings.RATE_LIMIT_ENABLED = original_enabled
            settings.RATE_LIMIT_BACKEND = original_backend

    def test_proxy_header_trust_switch(self):
        original_trust_proxy = settings.RATE_LIMIT_TRUST_PROXY_HEADERS
        try:
            req = _request(headers=[(b"x-forwarded-for", b"10.20.30.40")], client_host="127.0.0.1")

            settings.RATE_LIMIT_TRUST_PROXY_HEADERS = False
            identity_without_proxy = rate_limit._rate_limit_identity(req)
            self.assertIn("ip:127.0.0.1", identity_without_proxy)

            settings.RATE_LIMIT_TRUST_PROXY_HEADERS = True
            identity_with_proxy = rate_limit._rate_limit_identity(req)
            self.assertIn("ip:10.20.30.40", identity_with_proxy)
        finally:
            settings.RATE_LIMIT_TRUST_PROXY_HEADERS = original_trust_proxy


if __name__ == "__main__":
    unittest.main()
