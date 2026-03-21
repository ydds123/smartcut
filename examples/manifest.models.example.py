from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


BoundaryType = Literal[
    "hard_cut",
    "dissolve",
    "fade_in",
    "fade_out",
    "wipe",
    "unknown",
]

ReviewState = Literal[
    "unreviewed",
    "accepted",
    "rejected",
    "adjusted",
    "merged",
    "inserted",
]

ReviewActionType = Literal[
    "accept",
    "reject",
    "adjust",
    "merge",
    "insert",
]


class VideoSource(BaseModel):
    path: str
    fps: float
    width: int
    height: int
    total_frames: int
    duration_sec: float


class PySceneDetectEvidence(BaseModel):
    triggered: bool
    score: float | None = None
    scores: list[float] | None = None
    detector: str | None = None


class TransNetV2Evidence(BaseModel):
    triggered: bool
    score: float | None = None
    window_id: str | None = None


class ManualReviewEvidence(BaseModel):
    triggered: bool
    decision: str
    reason: str | None = None


class PySceneDetectGroupEvidence(BaseModel):
    content: PySceneDetectEvidence | None = None
    adaptive: PySceneDetectEvidence | None = None
    threshold: PySceneDetectEvidence | None = None


class DetectorEvidence(BaseModel):
    pyscenedetect: PySceneDetectGroupEvidence | None = None
    transnetv2: TransNetV2Evidence | None = None
    manual_review: ManualReviewEvidence | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BoundaryCandidate(BaseModel):
    id: str
    start_frame: int
    end_frame: int
    recommended_cut_frame: int
    boundary_type: BoundaryType
    confidence: float
    review_state: ReviewState
    detector_evidence: DetectorEvidence
    notes: list[str] = Field(default_factory=list)
    source_boundary_ids: list[str] = Field(default_factory=list)


class SuspiciousWindow(BaseModel):
    id: str
    start_frame: int
    end_frame: int
    reason: str
    source_boundary_ids: list[str] = Field(default_factory=list)


class ReviewActionPayload(BaseModel):
    old_start_frame: int | None = None
    old_end_frame: int | None = None
    old_recommended_cut_frame: int | None = None
    new_start_frame: int | None = None
    new_end_frame: int | None = None
    new_recommended_cut_frame: int | None = None
    merged_start_frame: int | None = None
    merged_end_frame: int | None = None
    merged_recommended_cut_frame: int | None = None
    merged_boundary_type: BoundaryType | None = None
    start_frame: int | None = None
    end_frame: int | None = None
    recommended_cut_frame: int | None = None
    boundary_type: BoundaryType | None = None
    reason: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ReviewAction(BaseModel):
    id: str
    action: ReviewActionType
    target_boundary_ids: list[str]
    result_boundary_id: str | None = None
    created_by: str
    created_at: datetime
    payload: ReviewActionPayload


class ReviewActionCommand(BaseModel):
    action: ReviewActionType
    target_boundary_ids: list[str]
    created_by: str
    payload: ReviewActionPayload


class ManifestSummaryCounts(BaseModel):
    coarse_boundaries: int
    suspicious_windows: int
    refined_boundaries: int
    final_boundaries: int
    accepted: int
    adjusted: int
    merged: int
    inserted: int
    rejected: int


class ManifestSummary(BaseModel):
    counts: ManifestSummaryCounts


class ProjectManifest(BaseModel):
    version: str
    manifest_id: str
    video: VideoSource
    config: dict[str, Any]
    coarse_boundaries: list[BoundaryCandidate]
    suspicious_windows: list[SuspiciousWindow]
    refined_boundaries: list[BoundaryCandidate]
    final_boundaries: list[BoundaryCandidate]
    review_actions: list[ReviewAction]
    summary: ManifestSummary | None = None
