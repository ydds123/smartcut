from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from scene_workbench.models import ProjectManifest


class EvaluationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    video_path: str
    duration_sec: float
    false_splits: int
    missed_boundaries: int
    adjustments: int
    merges: int
    accepted: int
    reviewed_boundaries: int
    final_boundaries: int
    manual_review_actions: int
    review_completion_rate: float
    notes: list[str]


def build_evaluation_snapshot(manifest: ProjectManifest) -> EvaluationSnapshot:
    summary = manifest.summary or None
    counts = summary.counts if summary is not None else None

    accepted = counts.accepted if counts is not None else 0
    adjustments = counts.adjusted if counts is not None else 0
    merges = counts.merged if counts is not None else 0
    final_boundaries = counts.final_boundaries if counts is not None else len(manifest.final_boundaries)
    false_splits = counts.rejected if counts is not None else sum(
        1 for action in manifest.review_actions if action.action == "reject"
    )
    missed_boundaries = counts.inserted if counts is not None else sum(
        1 for action in manifest.review_actions if action.action == "insert"
    )

    reviewed_boundaries = accepted + adjustments + merges + missed_boundaries
    review_completion_rate = (
        reviewed_boundaries / final_boundaries if final_boundaries > 0 else 0.0
    )

    notes = [
        "false_splits 以 reject 动作为代理统计。",
        "missed_boundaries 以 insert 动作为代理统计。",
        "人工核对总时长需要额外采集，当前 snapshot 无法直接给出。",
    ]

    return EvaluationSnapshot(
        manifest_id=manifest.manifest_id,
        video_path=manifest.video.path,
        duration_sec=manifest.video.duration_sec,
        false_splits=false_splits,
        missed_boundaries=missed_boundaries,
        adjustments=adjustments,
        merges=merges,
        accepted=accepted,
        reviewed_boundaries=reviewed_boundaries,
        final_boundaries=final_boundaries,
        manual_review_actions=len(manifest.review_actions),
        review_completion_rate=round(review_completion_rate, 4),
        notes=notes,
    )
