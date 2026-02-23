from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger)
    status = Column(String, default="PENDING")  # PENDING, QUEUED, PROCESSING, COMPLETED, FAILED, DETECTING, REVIEW_PENDING, REVIEW_APPROVED, SPLITTING, TIMELINE_READY
    progress = Column(Integer, default=0)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    sequence_index = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    file_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    error_type = Column(String)
    error_message = Column(Text)
    stack_trace = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
