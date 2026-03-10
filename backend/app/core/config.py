import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic_settings import BaseSettings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_FILE = (BACKEND_ROOT / ".env").resolve()
ANALYSIS_API_KEY_ENV_VAR = "ANALYSIS_API_KEY"


def _read_env_file_value(env_path: Path, variable_name: str) -> str:
    if not env_path.is_file():
        return ""

    try:
        value = dotenv_values(env_path).get(variable_name)
    except Exception:
        return ""

    return value.strip() if isinstance(value, str) else ""


INITIAL_PROCESS_ENV_ANALYSIS_API_KEY = (os.environ.get(ANALYSIS_API_KEY_ENV_VAR) or "").strip()
INITIAL_DOTENV_ANALYSIS_API_KEY = _read_env_file_value(BACKEND_ENV_FILE, ANALYSIS_API_KEY_ENV_VAR)


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./data/database.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CONNECT_RETRIES: int = 3
    REDIS_RETRY_DELAY_SEC: float = 0.5
    REDIS_RETRY_MAX_DELAY_SEC: float = 3.0

    # 文件存储
    UPLOAD_DIR: str = "./data/uploads"
    TASK_DIR: str = "./data/tasks"
    MAX_UPLOAD_SIZE: int = 524288000  # 500MB
    ENABLE_INCREMENTAL_SPLIT: bool = True
    FFMPEG_PROCESS_TIMEOUT_SEC: int = 600
    FFPROBE_TIMEOUT_SEC: int = 30
    RQ_JOB_RETRY_MAX: int = 2

    # 访问控制
    API_AUTH_ENABLED: bool = False
    API_AUTH_TOKEN: str = ""
    DATA_PUBLIC_ACCESS: bool = True

    # 速率限制（轻量内存实现）
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_BACKEND: str = "memory"  # memory | redis
    RATE_LIMIT_TRUST_PROXY_HEADERS: bool = False
    RATE_LIMIT_WINDOW_SEC: int = 60
    RATE_LIMIT_MUTATION_MAX_REQUESTS: int = 30
    RATE_LIMIT_UPLOAD_MAX_REQUESTS: int = 8

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # AI 分析（故事介绍）
    ANALYSIS_API_KEY: str = ""
    ANALYSIS_PROVIDER_DEFAULT: str = "gemini"
    ANALYSIS_BASE_URL_DEFAULT: str = "https://generativelanguage.googleapis.com"
    ANALYSIS_MODEL_DEFAULT: str = "gemini-3.1-flash-lite-preview"
    ANALYSIS_PROMPT_TEMPLATE_DEFAULT: str = ""
    ANALYSIS_ENABLED_DEFAULT: bool = False
    ANALYSIS_REQUEST_TIMEOUT_SEC_DEFAULT: int = 180
    ANALYSIS_ALLOWED_MODELS: str = "gemini-3.1-flash-lite-preview,gemini-2.5-flash"
    ANALYSIS_MAX_VIDEO_SIZE_MB: int = 512
    ANALYSIS_MAX_VIDEO_DURATION_SEC: int = 1800
    ANALYSIS_FILE_POLL_INTERVAL_SEC: float = 2.0
    ANALYSIS_FILE_MAX_WAIT_SEC: int = 120

    @property
    def analysis_env_file_path(self) -> Path:
        return BACKEND_ENV_FILE

    @property
    def analysis_api_key_source(self) -> str:
        if not (self.ANALYSIS_API_KEY or "").strip():
            return "missing"
        if INITIAL_PROCESS_ENV_ANALYSIS_API_KEY:
            return "process_env"
        if INITIAL_DOTENV_ANALYSIS_API_KEY:
            return "dotenv_file"
        return "process_env"

    class Config:
        env_file = str(BACKEND_ENV_FILE)


settings = Settings()
