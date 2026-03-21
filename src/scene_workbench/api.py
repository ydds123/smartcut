"""高层 API 入口。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from scene_workbench.config import (
    WorkbenchConfig,
    coerce_config,
    config_to_manifest_dict,
)
from scene_workbench.detectors.pyscenedetect_runner import run_pyscenedetect
from scene_workbench.detectors.suspicious_windows import build_suspicious_windows
from scene_workbench.detectors.transnetv2_runner import (
    TransNetPredictor,
    run_transnetv2,
)
from scene_workbench.fusion.decision import fuse_boundaries
from scene_workbench.ingest.media import load_video_source
from scene_workbench.models import (
    ManifestSummary,
    ManifestSummaryCounts,
    ProjectManifest,
    ReviewAction,
)


def build_summary(
    coarse_boundaries,
    suspicious_windows,
    refined_boundaries,
    final_boundaries,
    review_actions: list[ReviewAction],
) -> ManifestSummary:
    """基于当前 manifest 快照重算 summary。"""
    return ManifestSummary(
        counts=ManifestSummaryCounts(
            coarse_boundaries=len(coarse_boundaries),
            suspicious_windows=len(suspicious_windows),
            refined_boundaries=len(refined_boundaries),
            final_boundaries=len(final_boundaries),
            accepted=sum(1 for item in final_boundaries if item.review_state == "accepted"),
            adjusted=sum(1 for item in final_boundaries if item.review_state == "adjusted"),
            merged=sum(1 for item in final_boundaries if item.review_state == "merged"),
            inserted=sum(1 for item in final_boundaries if item.review_state == "inserted"),
            rejected=sum(1 for item in review_actions if item.action == "reject"),
        )
    )


def build_manifest_id(video_path: str | Path) -> str:
    """为当前分析任务生成 manifest ID。"""
    stem = Path(video_path).stem or "video"
    return f"{stem}_v1_{uuid4().hex[:8]}"


def save_manifest(manifest: ProjectManifest, output_path: str | Path) -> Path:
    """写出 manifest JSON。"""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output


def analyze_video(
    video_path: str | Path,
    config: WorkbenchConfig | dict | None = None,
    *,
    predictor: TransNetPredictor | None = None,
) -> ProjectManifest:
    """执行 Wave 1 的最小分析主链。"""
    workbench_config = coerce_config(config)
    video_source = load_video_source(video_path)
    coarse_boundaries = run_pyscenedetect(video_source, workbench_config)
    suspicious_windows = build_suspicious_windows(
        video_source,
        coarse_boundaries,
        workbench_config,
    )
    refined_boundaries = run_transnetv2(
        video_source,
        suspicious_windows,
        workbench_config,
        predictor=predictor,
    )
    final_boundaries = fuse_boundaries(
        coarse_boundaries,
        refined_boundaries,
        workbench_config,
    )
    review_actions: list[ReviewAction] = []

    manifest = ProjectManifest(
        version="v1",
        manifest_id=build_manifest_id(video_path),
        video=video_source,
        config=config_to_manifest_dict(workbench_config),
        coarse_boundaries=coarse_boundaries,
        suspicious_windows=suspicious_windows,
        refined_boundaries=refined_boundaries,
        final_boundaries=final_boundaries,
        review_actions=review_actions,
        summary=None,
    )
    manifest.summary = build_summary(
        manifest.coarse_boundaries,
        manifest.suspicious_windows,
        manifest.refined_boundaries,
        manifest.final_boundaries,
        manifest.review_actions,
    )
    return manifest
