from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"


settings = Settings()
