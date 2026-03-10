from sqlalchemy import Boolean, Column, String, Integer, BigInteger, DateTime, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


def utc_now_naive() -> datetime:
    """返回无时区的 UTC 时间，兼容现有 DateTime 列定义。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String, default="PENDING")  # PENDING, QUEUED, PROCESSING, COMPLETED, FAILED, DETECTING, REVIEW_PENDING, REVIEW_APPROVED, SPLITTING, TIMELINE_READY
    progress = Column(Integer, default=0)
    active_operation = Column(String, nullable=True)  # process, review, split
    active_job_id = Column(String, nullable=True)  # 当前活跃 worker job id（防陈旧写入覆盖）
    total_scenes = Column(Integer, nullable=True)
    process_mode = Column(String, nullable=True)
    config_profile = Column(String, nullable=True)
    requested_config = Column(Text, nullable=True)
    resolved_config = Column(Text, nullable=True)
    quality_flags = Column(Text, nullable=True)
    suspect_segments = Column(Text, nullable=True)
    tuning_history = Column(Text, nullable=True)
    review_notes = Column(Text, nullable=True)
    split_stats = Column(Text, nullable=True)       # JSON: 最近一次切分统计
    detection_result = Column(Text, nullable=True)   # JSON: 检测结果 [{start_ms, end_ms}, ...]
    user_edited_scenes = Column(Text, nullable=True) # JSON: 用户编辑后的场景列表
    reviewed_at = Column(DateTime, nullable=True)    # 用户确认时间
    edit_history = Column(Text, nullable=True)       # JSON: 编辑操作历史
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    sequence_index = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    file_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    error_type = Column(String)
    error_message = Column(Text)
    stack_trace = Column(Text)
    created_at = Column(DateTime, default=utc_now_naive)


class AnalysisSettings(Base):
    __tablename__ = "analysis_settings"

    id = Column(String, primary_key=True, default="default")
    provider = Column(String, nullable=False, default="gemini")
    base_url = Column(String, nullable=False, default="https://generativelanguage.googleapis.com")
    model = Column(String, nullable=False, default="gemini-3.1-flash-lite-preview")
    prompt_template = Column(Text, nullable=False, default="")
    analysis_enabled = Column(Boolean, nullable=False, default=False)
    request_timeout_sec = Column(Integer, nullable=False, default=180)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False, index=True)
    analysis_type = Column(String, nullable=False, default="story_intro")
    status = Column(String, nullable=False, default="QUEUED")  # QUEUED | RUNNING | SUCCEEDED | FAILED
    provider_snapshot = Column(String, nullable=True)
    base_url_snapshot = Column(String, nullable=True)
    model_snapshot = Column(String, nullable=True)
    request_timeout_sec_snapshot = Column(Integer, nullable=True)
    prompt_snapshot = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    raw_response_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    usage_json = Column(Text, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    finished_at = Column(DateTime, nullable=True)
