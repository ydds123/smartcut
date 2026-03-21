from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class VideoSource(StrictModel):
    path: str
    fps: float
    width: int
    height: int
    total_frames: int
    duration_sec: float


class PySceneDetectEvidence(FlexibleModel):
    triggered: bool
    score: float | None = None
    scores: list[float] | None = None
    detector: str | None = None


class TransNetV2Evidence(FlexibleModel):
    triggered: bool
    score: float | None = None
    window_id: str | None = None


class ManualReviewEvidence(FlexibleModel):
    triggered: bool
    decision: str
    reason: str | None = None


class PySceneDetectGroupEvidence(StrictModel):
    content: PySceneDetectEvidence | None = None
    adaptive: PySceneDetectEvidence | None = None
    threshold: PySceneDetectEvidence | None = None


class DetectorEvidence(FlexibleModel):
    pyscenedetect: PySceneDetectGroupEvidence | None = None
    transnetv2: TransNetV2Evidence | None = None
    manual_review: ManualReviewEvidence | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BoundaryCandidate(StrictModel):
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


class SuspiciousWindow(StrictModel):
    id: str
    start_frame: int
    end_frame: int
    reason: str
    source_boundary_ids: list[str] = Field(default_factory=list)


class ReviewActionPayload(FlexibleModel):
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


class ReviewAction(StrictModel):
    id: str
    action: ReviewActionType
    target_boundary_ids: list[str]
    result_boundary_id: str | None = None
    created_by: str
    created_at: datetime
    payload: ReviewActionPayload


class ReviewActionCommand(StrictModel):
    action: ReviewActionType
    target_boundary_ids: list[str]
    created_by: str
    payload: ReviewActionPayload


class ManifestSummaryCounts(StrictModel):
    coarse_boundaries: int
    suspicious_windows: int
    refined_boundaries: int
    final_boundaries: int
    accepted: int
    adjusted: int
    merged: int
    inserted: int
    rejected: int


class ManifestSummary(StrictModel):
    counts: ManifestSummaryCounts


class ProjectManifest(StrictModel):
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


def build_manifest_summary(
    *,
    coarse_boundaries: list[BoundaryCandidate],
    suspicious_windows: list[SuspiciousWindow],
    refined_boundaries: list[BoundaryCandidate],
    final_boundaries: list[BoundaryCandidate],
    review_actions: list[ReviewAction],
) -> ManifestSummary:
    action_counts = Counter(action.action for action in review_actions)
    state_counts = Counter(boundary.review_state for boundary in final_boundaries)

    return ManifestSummary(
        counts=ManifestSummaryCounts(
            coarse_boundaries=len(coarse_boundaries),
            suspicious_windows=len(suspicious_windows),
            refined_boundaries=len(refined_boundaries),
            final_boundaries=len(final_boundaries),
            accepted=state_counts["accepted"],
            adjusted=state_counts["adjusted"],
            merged=state_counts["merged"],
            inserted=state_counts["inserted"],
            rejected=action_counts["reject"],
        )
    )
