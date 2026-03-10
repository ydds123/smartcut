from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.models.models import Base
from app.core.config import settings

db_url = make_url(settings.DATABASE_URL)
db_backend_name = db_url.get_backend_name()
is_sqlite = db_backend_name == "sqlite"

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


def _ensure_analysis_settings_columns():
    required_columns = {
        "provider": "TEXT",
        "base_url": "TEXT",
        "model": "TEXT",
        "prompt_template": "TEXT",
        "analysis_enabled": "INTEGER",
        "request_timeout_sec": "INTEGER",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }

    inspector = inspect(engine)
    if "analysis_settings" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("analysis_settings")}
    missing = {name: ddl for name, ddl in required_columns.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.exec_driver_sql(f"ALTER TABLE analysis_settings ADD COLUMN {name} {ddl};")


def _ensure_analysis_runs_columns_and_indexes():
    required_columns = {
        "task_id": "TEXT",
        "analysis_type": "TEXT",
        "status": "TEXT",
        "provider_snapshot": "TEXT",
        "base_url_snapshot": "TEXT",
        "model_snapshot": "TEXT",
        "request_timeout_sec_snapshot": "INTEGER",
        "prompt_snapshot": "TEXT",
        "result_json": "TEXT",
        "raw_response_json": "TEXT",
        "error_message": "TEXT",
        "retry_count": "INTEGER",
        "usage_json": "TEXT",
        "estimated_cost": "FLOAT",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "finished_at": "DATETIME",
    }

    inspector = inspect(engine)
    if "analysis_runs" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("analysis_runs")}
        missing = {name: ddl for name, ddl in required_columns.items() if name not in existing}
        if missing:
            with engine.begin() as conn:
                for name, ddl in missing.items():
                    conn.exec_driver_sql(f"ALTER TABLE analysis_runs ADD COLUMN {name} {ddl};")

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_analysis_runs_task_type_created "
            "ON analysis_runs (task_id, analysis_type, created_at);"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_analysis_runs_task_type_status "
            "ON analysis_runs (task_id, analysis_type, status);"
        )
        if db_backend_name in {"sqlite", "postgresql"}:
            conn.exec_driver_sql(
                """
                WITH ranked_active AS (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY task_id, analysis_type
                            ORDER BY created_at DESC, id DESC
                        ) AS rn
                    FROM analysis_runs
                    WHERE status IN ('QUEUED', 'RUNNING')
                )
                UPDATE analysis_runs
                SET
                    status = 'FAILED',
                    error_message = COALESCE(error_message, 'active run deduplicated during index migration'),
                    finished_at = COALESCE(finished_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT id FROM ranked_active WHERE rn > 1
                );
                """
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_analysis_runs_active_unique "
                "ON analysis_runs (task_id, analysis_type) "
                "WHERE status IN ('QUEUED', 'RUNNING');"
            )


def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    _ensure_tasks_columns()
    _ensure_analysis_settings_columns()
    _ensure_analysis_runs_columns_and_indexes()

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
