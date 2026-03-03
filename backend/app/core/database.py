from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.models.models import Base
from app.core.config import settings

db_url = make_url(settings.DATABASE_URL)
is_sqlite = db_url.get_backend_name() == "sqlite"

if is_sqlite:
    # SQLite 在高频读写（SSE 轮询 + 后台写入）下更适合短连接策略，避免 QueuePool 饱和。
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
        poolclass=NullPool,
    )
else:
    # 非 SQLite 保留连接池，但显式给出容量和超时，便于排查连接耗尽问题。
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_tasks_columns():
    """
    兼容老版本数据库：为 tasks 表补齐新增字段。
    该项目当前以 create_all 为主，这里做轻量升级以避免手工迁移。
    """
    required_columns = {
        "active_operation": "TEXT",
        "active_job_id": "TEXT",
        "process_mode": "TEXT",
        "config_profile": "TEXT",
        "requested_config": "TEXT",
        "resolved_config": "TEXT",
        "duration_ms": "INTEGER",
        "quality_flags": "TEXT",
        "suspect_segments": "TEXT",
        "tuning_history": "TEXT",
        "review_notes": "TEXT",
        "split_stats": "TEXT",
        "detection_result": "TEXT",
        "user_edited_scenes": "TEXT",
        "reviewed_at": "DATETIME",
        "edit_history": "TEXT",
    }

    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("tasks")}
    missing = {name: ddl for name, ddl in required_columns.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.exec_driver_sql(f"ALTER TABLE tasks ADD COLUMN {name} {ddl};")


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    _ensure_tasks_columns()

    if is_sqlite:
        # 启用 WAL 与 busy timeout，降低写入期间读请求失败概率。
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=5000;")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
