from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.models.models import AnalysisSettings
from app.services.analysis_gemini import GeminiClient


@dataclass(frozen=True)
class UploadedVideoRef:
    provider_payload: dict[str, Any]
    uri: str
    mime_type: str


class AnalysisProviderAdapter(ABC):
    provider_name: str

    @abstractmethod
    def test_connection(self, *, model: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def upload_video(
        self,
        file_path: str,
        *,
        display_name: str | None = None,
    ) -> UploadedVideoRef:
        raise NotImplementedError

    @abstractmethod
    def generate_story_intro(
        self,
        *,
        model: str,
        prompt: str,
        uploaded_video: UploadedVideoRef,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self, uploaded_video: UploadedVideoRef | None) -> None:
        raise NotImplementedError


class GeminiProviderAdapter(AnalysisProviderAdapter):
    provider_name = "gemini"

    def __init__(self, client: GeminiClient):
        self._client = client

    def test_connection(self, *, model: str) -> int:
        return self._client.test_model(model=model)

    def upload_video(
        self,
        file_path: str,
        *,
        display_name: str | None = None,
    ) -> UploadedVideoRef:
        uploaded = self._client.upload_video(
            file_path=file_path,
            display_name=display_name,
        )
        return UploadedVideoRef(
            provider_payload=uploaded,
            uri=str(uploaded.get("uri") or ""),
            mime_type=str(uploaded.get("mime_type") or "video/mp4"),
        )

    def generate_story_intro(
        self,
        *,
        model: str,
        prompt: str,
        uploaded_video: UploadedVideoRef,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return self._client.generate_story_intro(
            model=model,
            prompt=prompt,
            video_file_uri=uploaded_video.uri,
            mime_type=uploaded_video.mime_type,
        )

    def cleanup(self, uploaded_video: UploadedVideoRef | None) -> None:
        if uploaded_video is None:
            return
        file_name = uploaded_video.provider_payload.get("name")
        if isinstance(file_name, str) and file_name.strip():
            self._client.delete_file(file_name)


SUPPORTED_ANALYSIS_PROVIDERS = frozenset({"gemini"})


def get_supported_analysis_providers() -> set[str]:
    return set(SUPPORTED_ANALYSIS_PROVIDERS)


def build_analysis_provider_adapter(settings_model: AnalysisSettings) -> AnalysisProviderAdapter:
    provider = (settings_model.provider or "").strip().lower()
    if provider not in SUPPORTED_ANALYSIS_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider or '<empty>'}")

    api_key = (getattr(settings, "ANALYSIS_API_KEY", "") or "").strip()
    if not api_key:
        raise ValueError("ANALYSIS_API_KEY is missing")

    client = GeminiClient(
        api_key=api_key,
        base_url=settings_model.base_url,
        timeout_sec=int(settings_model.request_timeout_sec or 180),
        file_poll_interval_sec=float(getattr(settings, "ANALYSIS_FILE_POLL_INTERVAL_SEC", 2.0)),
        file_max_wait_sec=int(getattr(settings, "ANALYSIS_FILE_MAX_WAIT_SEC", 120)),
    )
    return GeminiProviderAdapter(client)
