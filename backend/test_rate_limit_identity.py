import unittest
from starlette.requests import Request

from app.core.rate_limit import _rate_limit_identity


def _request(path: str, headers: list[tuple[bytes, bytes]] | None = None, client_host: str = "127.0.0.1") -> Request:
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


class TestRateLimitIdentity(unittest.TestCase):
    def test_identity_contains_route_and_ip(self):
        req = _request("/api/tasks/abc/process")
        identity = _rate_limit_identity(req)
        self.assertIn("ip:127.0.0.1", identity)
        self.assertIn("route:/api/tasks/abc/process", identity)

    def test_identity_prefers_token_when_present(self):
        req = _request(
            "/api/tasks/abc/process",
            headers=[(b"x-api-token", b"token-value")],
            client_host="10.1.2.3",
        )
        identity = _rate_limit_identity(req)
        self.assertIn("token:", identity)
        self.assertIn("route:/api/tasks/abc/process", identity)
        self.assertNotIn("token-value", identity)


if __name__ == "__main__":
    unittest.main()
