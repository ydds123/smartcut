from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    display_name: str


class ProcessConfigOverride(BaseModel):
    detector: Optional[Literal["content", "adaptive"]] = None
    detection_mode: Optional[Literal["fast", "precision"]] = None
    use_transnet: Optional[bool] = None
    scene_threshold: Optional[float] = None
    min_scene_len_frames: Optional[int] = None
    downscale: Optional[int] = None
    frame_skip: Optional[int] = None
    adaptive_threshold: Optional[float] = None
    adaptive_min_content_val: Optional[float] = None
    adaptive_frame_window: Optional[int] = None
    thumbnail_retry: Optional[int] = None
    weight_hue: Optional[float] = None
    weight_sat: Optional[float] = None
    weight_lum: Optional[float] = None
    weight_edges: Optional[float] = None
    transnet_threshold: Optional[float] = None
    transnet_tolerance_frames: Optional[int] = None
    transnet_window_size: Optional[int] = None
    transnet_timeout_sec: Optional[int] = None
    transnet_additional_boundary_threshold: Optional[float] = None
    transnet_only_min_gap_frames: Optional[int] = None


class ProcessTaskRequest(BaseModel):
    mode: Literal["manual"] = "manual"
    profile: Literal["quality"] = "quality"
    override_config: Optional[ProcessConfigOverride] = None


class TaskResponse(BaseModel):
    id: str
    display_name: str
    file_path: str
    file_size: int
    status: str
    progress: int
    total_scenes: Optional[int]
    shots_count: Optional[int] = None
    preview_thumbnail_path: Optional[str] = None
    process_mode: Optional[str] = None
    config_profile: Optional[str] = None
    requested_config: Optional[dict[str, Any]] = None
    resolved_config: Optional[dict[str, Any]] = None
    quality_flags: Optional[dict[str, Any]] = None
    suspect_segments: Optional[list[dict[str, Any]]] = None
    tuning_history: Optional[list[dict[str, Any]]] = None
    review_notes: Optional[str] = None
    detection_result: Optional[dict[str, Any]] = None
    user_edited_scenes: Optional[list[dict[str, Any]]] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SceneResponse(BaseModel):
    id: str
    task_id: str
    sequence_index: int
    start_ms: int
    end_ms: int
    file_path: Optional[str]
    thumbnail_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessTaskResponse(BaseModel):
    status: str
    job_id: Optional[str] = None
    resolved_config: Optional[dict[str, Any]] = None
