from __future__ import annotations

import json
import mimetypes
import os
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import certifi


class GeminiAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, details: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _normalize_base_url(raw: str) -> str:
    base = (raw or "").strip().rstrip("/")
    if not base:
        return "https://generativelanguage.googleapis.com"

    for suffix in ("/upload/v1beta", "/upload/v1", "/v1beta", "/v1"):
        if base.endswith(suffix):
            return base[: -len(suffix)]
    return base


def _coerce_error_message(payload_text: str) -> str:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return payload_text.strip() or "unknown error"

    if isinstance(payload, dict):
        if isinstance(payload.get("error"), dict):
            message = payload["error"].get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return payload_text.strip() or "unknown error"


def _read_http_error(exc: HTTPError) -> str:
    try:
        data = exc.read()
    except Exception:
        data = b""
    text = data.decode("utf-8", errors="ignore") if data else ""
    return _coerce_error_message(text)


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_sec: int,
        file_poll_interval_sec: float = 2.0,
        file_max_wait_sec: int = 120,
    ):
        normalized_api_key = (api_key or "").strip()
        if not normalized_api_key:
            raise ValueError("Gemini API key is required")

        self.api_key = normalized_api_key
        self.base_url = _normalize_base_url(base_url)
        self.timeout_sec = max(10, int(timeout_sec))
        self.file_poll_interval_sec = max(0.5, float(file_poll_interval_sec))
        self.file_max_wait_sec = max(10, int(file_max_wait_sec))
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def _request_raw(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout_sec: int | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        req = Request(url=url, data=body, method=method.upper())
        for key, value in (headers or {}).items():
            req.add_header(key, value)

        timeout = max(1, int(timeout_sec or self.timeout_sec))
        try:
            with urlopen(req, timeout=timeout, context=self.ssl_context) as resp:
                status = int(getattr(resp, "status", 200))
                response_headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
                payload = resp.read() or b""
                return status, response_headers, payload
        except HTTPError as exc:
            message = _read_http_error(exc)
            raise GeminiAPIError(
                f"Gemini API request failed ({exc.code}): {message}",
                status_code=int(exc.code),
                details=message,
            ) from exc
        except URLError as exc:
            raise GeminiAPIError(f"Gemini API request failed: {exc.reason}") from exc
        except Exception as exc:
            raise GeminiAPIError(f"Gemini API request failed: {exc}") from exc

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        body: bytes | None = None,
        timeout_sec: int | None = None,
    ) -> dict[str, Any]:
        if payload is not None and body is not None:
            raise ValueError("payload and body cannot both be provided")

        request_headers = dict(headers or {})
        request_body = body
        if payload is not None:
            request_headers.setdefault("Content-Type", "application/json")
            request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        _status, _resp_headers, response_payload = self._request_raw(
            method,
            url,
            headers=request_headers,
            body=request_body,
            timeout_sec=timeout_sec,
        )

        if not response_payload:
            return {}

        try:
            parsed = json.loads(response_payload.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _build_keyed_url(self, path: str) -> str:
        separator = "&" if "?" in path else "?"
        return f"{self.base_url}{path}{separator}key={quote(self.api_key, safe='')}"

    def _extract_text(self, response_json: dict[str, Any]) -> str:
        candidates = response_json.get("candidates")
        if not isinstance(candidates, list):
            return ""

        chunks: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())

        return "\n\n".join(chunks).strip()

    @staticmethod
    def _build_summary(text: str) -> str:
        if not text.strip():
            return ""
        for line in text.splitlines():
            clean = line.strip().lstrip("#").strip()
            if clean:
                return clean[:160]
        return text.strip()[:160]

    @staticmethod
    def _resolve_file_state(payload: dict[str, Any]) -> str:
        state = payload.get("state")
        if isinstance(state, dict):
            maybe_name = state.get("name")
            if isinstance(maybe_name, str):
                return maybe_name.upper()
        if isinstance(state, str):
            return state.upper()
        return ""

    def get_file(self, file_name: str) -> dict[str, Any]:
        return self._request_json(
            "GET",
            self._build_keyed_url(f"/v1beta/{file_name}"),
        )

    def wait_until_file_active(self, file_payload: dict[str, Any]) -> dict[str, Any]:
        current = dict(file_payload)
        name = current.get("name")
        if not isinstance(name, str) or not name.strip():
            raise GeminiAPIError("Gemini file upload did not return file name")

        deadline = time.monotonic() + self.file_max_wait_sec
        while True:
            current_state = self._resolve_file_state(current)
            if current_state.endswith("ACTIVE") and isinstance(current.get("uri"), str):
                return current
            if current_state.endswith("FAILED"):
                raise GeminiAPIError("Gemini file processing failed")

            if time.monotonic() >= deadline:
                raise GeminiAPIError("Gemini file processing timed out")

            time.sleep(self.file_poll_interval_sec)
            current = self.get_file(name)

    def upload_video(self, file_path: str, *, display_name: str | None = None) -> dict[str, Any]:
        resolved_path = Path(file_path).resolve()
        if not resolved_path.exists():
            raise GeminiAPIError("Video file does not exist")

        mime_type, _ = mimetypes.guess_type(str(resolved_path))
        if not mime_type:
            mime_type = "video/mp4"

        file_size = os.path.getsize(resolved_path)
        if file_size <= 0:
            raise GeminiAPIError("Video file is empty")

        start_url = self._build_keyed_url("/upload/v1beta/files")
        start_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        start_payload = {
            "file": {
                "display_name": display_name or resolved_path.name,
            }
        }
        _status, response_headers, _body = self._request_raw(
            "POST",
            start_url,
            headers=start_headers,
            body=json.dumps(start_payload, ensure_ascii=False).encode("utf-8"),
        )

        upload_url = response_headers.get("x-goog-upload-url")
        if not upload_url:
            raise GeminiAPIError("Gemini upload session URL missing")

        with open(resolved_path, "rb") as fh:
            file_bytes = fh.read()

        upload_response = self._request_json(
            "POST",
            upload_url,
            headers={
                "Content-Length": str(file_size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
                "Content-Type": mime_type,
            },
            body=file_bytes,
            timeout_sec=max(self.timeout_sec, 120),
        )
        uploaded_file = upload_response.get("file") if isinstance(upload_response.get("file"), dict) else upload_response
        if not isinstance(uploaded_file, dict):
            raise GeminiAPIError("Gemini upload response is invalid")

        active_file = self.wait_until_file_active(uploaded_file)
        uri = active_file.get("uri")
        name = active_file.get("name")
        if not isinstance(uri, str) or not uri.strip():
            raise GeminiAPIError("Gemini uploaded file URI missing")
        if not isinstance(name, str) or not name.strip():
            raise GeminiAPIError("Gemini uploaded file name missing")

        return {
            "name": name,
            "uri": uri,
            "mime_type": mime_type,
        }

    def delete_file(self, file_name: str) -> None:
        if not file_name:
            return
        try:
            self._request_raw("DELETE", self._build_keyed_url(f"/v1beta/{file_name}"))
        except Exception:
            # best effort cleanup，不阻断主流程
            return

    def generate_story_intro(
        self,
        *,
        model: str,
        prompt: str,
        video_file_uri: str,
        mime_type: str = "video/mp4",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = self._build_keyed_url(f"/v1beta/models/{quote(model, safe='')}:generateContent")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "file_data": {
                                "mime_type": mime_type,
                                "file_uri": video_file_uri,
                            }
                        },
                    ],
                }
            ]
        }
        raw_response = self._request_json(
            "POST",
            endpoint,
            payload=payload,
            timeout_sec=self.timeout_sec,
        )
        text = self._extract_text(raw_response)
        if not text:
            raise GeminiAPIError("Gemini response has no usable text content")

        normalized = {
            "story_intro_markdown": text,
            "summary": self._build_summary(text),
            "provider": "gemini",
            "model": model,
        }
        return normalized, raw_response

    def test_model(self, *, model: str) -> int:
        started = time.perf_counter()
        endpoint = self._build_keyed_url(f"/v1beta/models/{quote(model, safe='')}:generateContent")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "ping"}],
                }
            ]
        }
        self._request_json("POST", endpoint, payload=payload, timeout_sec=min(self.timeout_sec, 60))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return max(1, elapsed_ms)
