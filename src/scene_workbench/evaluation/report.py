from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from pydantic import BaseModel, ConfigDict, Field

from scene_workbench.evaluation.metrics import EvaluationSnapshot, build_evaluation_snapshot
from scene_workbench.export._common import ensure_output_path
from scene_workbench.models import ProjectManifest
from scene_workbench.review.store import load_manifest


class BaselineAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_count: int
    total_duration_sec: float
    false_splits: int
    missed_boundaries: int
    adjustments: int
    merges: int
    accepted: int
    manual_review_actions: int
    avg_review_completion_rate: float


class BaselineReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "v1"
    aggregate: BaselineAggregate
    samples: list[EvaluationSnapshot] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def build_baseline_report(manifests: list[ProjectManifest]) -> BaselineReport:
    snapshots = [build_evaluation_snapshot(manifest) for manifest in manifests]
    if not snapshots:
        aggregate = BaselineAggregate(
            sample_count=0,
            total_duration_sec=0.0,
            false_splits=0,
            missed_boundaries=0,
            adjustments=0,
            merges=0,
            accepted=0,
            manual_review_actions=0,
            avg_review_completion_rate=0.0,
        )
    else:
        aggregate = BaselineAggregate(
            sample_count=len(snapshots),
            total_duration_sec=round(sum(item.duration_sec for item in snapshots), 3),
            false_splits=sum(item.false_splits for item in snapshots),
            missed_boundaries=sum(item.missed_boundaries for item in snapshots),
            adjustments=sum(item.adjustments for item in snapshots),
            merges=sum(item.merges for item in snapshots),
            accepted=sum(item.accepted for item in snapshots),
            manual_review_actions=sum(item.manual_review_actions for item in snapshots),
            avg_review_completion_rate=round(
                mean(item.review_completion_rate for item in snapshots), 4
            ),
        )

    notes = [
        "false_splits 目前以 reject 动作为代理统计。",
        "missed_boundaries 目前以 insert 动作为代理统计。",
        "人工核对总时长仍需结合真实评审会话采集。",
    ]
    return BaselineReport(aggregate=aggregate, samples=snapshots, notes=notes)


def load_manifests_for_report(paths: list[str | Path]) -> list[ProjectManifest]:
    return [load_manifest(path) for path in paths]


def export_baseline_report_json(
    report: BaselineReport,
    output_path: str | Path,
) -> Path:
    path = ensure_output_path(output_path)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def export_baseline_report_markdown(
    report: BaselineReport,
    output_path: str | Path,
) -> Path:
    lines = [
        "# Baseline Report",
        "",
        f"- sample_count: {report.aggregate.sample_count}",
        f"- total_duration_sec: {report.aggregate.total_duration_sec}",
        f"- false_splits: {report.aggregate.false_splits}",
        f"- missed_boundaries: {report.aggregate.missed_boundaries}",
        f"- adjustments: {report.aggregate.adjustments}",
        f"- merges: {report.aggregate.merges}",
        f"- accepted: {report.aggregate.accepted}",
        f"- manual_review_actions: {report.aggregate.manual_review_actions}",
        f"- avg_review_completion_rate: {report.aggregate.avg_review_completion_rate}",
        "",
        "## Samples",
        "",
    ]
    for sample in report.samples:
        lines.extend(
            [
                f"### {sample.manifest_id}",
                "",
                f"- video_path: {sample.video_path}",
                f"- duration_sec: {sample.duration_sec}",
                f"- false_splits: {sample.false_splits}",
                f"- missed_boundaries: {sample.missed_boundaries}",
                f"- adjustments: {sample.adjustments}",
                f"- merges: {sample.merges}",
                f"- accepted: {sample.accepted}",
                f"- manual_review_actions: {sample.manual_review_actions}",
                f"- review_completion_rate: {sample.review_completion_rate}",
                "",
            ]
        )
    lines.extend(["## Notes", ""])
    lines.extend([f"- {note}" for note in report.notes])

    path = ensure_output_path(output_path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
