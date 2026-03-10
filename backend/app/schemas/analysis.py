from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisSettingsUpsertRequest(BaseModel):
    provider: str = Field(default="gemini", min_length=1, max_length=64)
    base_url: str = Field(default="https://generativelanguage.googleapis.com", min_length=1, max_length=512)
    model: str = Field(default="gemini-3.1-flash-lite-preview", min_length=1, max_length=128)
    prompt_template: str = Field(default="", max_length=20000)
    analysis_enabled: bool = False
    request_timeout_sec: int = Field(default=180, ge=10, le=900)


class AnalysisSettingsResponse(BaseModel):
    provider: str
    base_url: str
    model: str
    prompt_template: str
    analysis_enabled: bool
    request_timeout_sec: int
    has_api_key: bool
    api_key_source: str
    env_file_path: Optional[str] = None
    env_file_exists: bool = False
    can_open_env_file: bool = False
    env_variable_name: str = "ANALYSIS_API_KEY"
    is_complete: bool
    incomplete_reasons: list[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class AnalysisSettingsTestRequest(BaseModel):
    provider: Optional[str] = Field(default=None, min_length=1, max_length=64)
    base_url: Optional[str] = Field(default=None, min_length=1, max_length=512)
    model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    prompt_template: Optional[str] = Field(default=None, max_length=20000)
    analysis_enabled: Optional[bool] = None
    request_timeout_sec: Optional[int] = Field(default=None, ge=10, le=900)


class AnalysisSettingsTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[int] = None


class AnalysisOpenEnvFileResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None


class AnalysisLatestResponse(BaseModel):
    task_id: str
    analysis_type: str = "story_intro"
    status: str
    run_id: Optional[str] = None
    is_configured: bool
    has_api_key: bool
    api_key_source: str = "missing"
    can_retry: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    story_intro_markdown: Optional[str] = None
    summary: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class AnalysisRetryResponse(BaseModel):
    task_id: str
    analysis_type: str = "story_intro"
    run_id: str
    status: str
    deduplicated: bool = False
    message: Optional[str] = None


class AnalysisLatestBatchRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if len(cleaned) > 200:
            raise ValueError("task_ids 最多允许 200 条")
        return cleaned


class AnalysisLatestBatchItem(BaseModel):
    task_id: str
    status: str
    run_id: Optional[str] = None
    can_retry: bool = False
    updated_at: Optional[datetime] = None


class AnalysisLatestBatchResponse(BaseModel):
    items: list[AnalysisLatestBatchItem] = Field(default_factory=list)
