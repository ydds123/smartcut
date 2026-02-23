from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./data/database.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # 文件存储
    UPLOAD_DIR: str = "./data/uploads"
    TASK_DIR: str = "./data/tasks"
    MAX_UPLOAD_SIZE: int = 524288000  # 500MB
    ENABLE_INCREMENTAL_SPLIT: bool = True

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"


settings = Settings()
