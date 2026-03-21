"""Suspicious windows 生成逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field

from scene_workbench.config import WorkbenchConfig, coerce_config
from scene_workbench.models import BoundaryCandidate, SuspiciousWindow, VideoSource


@dataclass(slots=True)
class WindowDraft:
    start_frame: int
    end_frame: int
    reasons: set[str] = field(default_factory=set)
    source_boundary_ids: list[str] = field(default_factory=list)


def _clamp_window(
    start_frame: int,
    end_frame: int,
    total_frames: int,
) -> tuple[int, int]:
    start = max(0, start_frame)
    end = min(total_frames - 1, end_frame)
    if end < start:
        end = start
    return start, end


def _append_draft(
    drafts: list[WindowDraft],
    start_frame: int,
    end_frame: int,
    reason: str,
    source_boundary_ids: list[str],
    total_frames: int,
) -> None:
    start, end = _clamp_window(start_frame, end_frame, total_frames)
    drafts.append(
        WindowDraft(
            start_frame=start,
            end_frame=end,
            reasons={reason},
            source_boundary_ids=list(source_boundary_ids),
        )
    )


def _is_gradual_suspect(candidate: BoundaryCandidate) -> bool:
    pyscenedetect = candidate.detector_evidence.pyscenedetect
    if pyscenedetect and pyscenedetect.threshold and pyscenedetect.threshold.triggered:
        return True
    return candidate.boundary_type in {"dissolve", "fade_in", "fade_out", "wipe", "unknown"}


def _merge_drafts(
    drafts: list[WindowDraft],
    merge_gap_frames: int,
) -> list[WindowDraft]:
    if not drafts:
        return []

    drafts = sorted(drafts, key=lambda item: (item.start_frame, item.end_frame))
    merged: list[WindowDraft] = [drafts[0]]

    for current in drafts[1:]:
        previous = merged[-1]
        if current.start_frame <= previous.end_frame + merge_gap_frames:
            previous.end_frame = max(previous.end_frame, current.end_frame)
            previous.reasons.update(current.reasons)
            for boundary_id in current.source_boundary_ids:
                if boundary_id not in previous.source_boundary_ids:
                    previous.source_boundary_ids.append(boundary_id)
            continue
        merged.append(current)

    return merged


def _build_long_scene_windows(
    video_source: VideoSource,
    coarse_boundaries: list[BoundaryCandidate],
    config: WorkbenchConfig,
) -> list[WindowDraft]:
    cut_frames = sorted(boundary.recommended_cut_frame for boundary in coarse_boundaries)
    scene_markers = [0, *cut_frames, video_source.total_frames]
    drafts: list[WindowDraft] = []
    threshold = config.refinement.long_scene_threshold_frames
    max_window = config.refinement.max_window_frames

    for start_marker, end_marker in zip(scene_markers, scene_markers[1:]):
        scene_start = start_marker
        scene_end = max(scene_start, end_marker - 1)
        scene_len = scene_end - scene_start + 1
        if scene_len <= threshold:
            continue

        midpoint = scene_start + scene_len // 2
        half_span = max_window // 2
        window_start = midpoint - half_span
        window_end = window_start + max_window - 1
        if window_start < scene_start:
            window_start = scene_start
            window_end = min(scene_end, scene_start + max_window - 1)
        if window_end > scene_end:
            window_end = scene_end
            window_start = max(scene_start, scene_end - max_window + 1)

        drafts.append(
            WindowDraft(
                start_frame=window_start,
                end_frame=window_end,
                reasons={"long_scene"},
                source_boundary_ids=[],
            )
        )

    return drafts


def build_suspicious_windows(
    video_source: VideoSource,
    coarse_boundaries: list[BoundaryCandidate],
    config: WorkbenchConfig | dict | None = None,
) -> list[SuspiciousWindow]:
    """根据 coarse 结果生成 refinement 窗口。"""
    workbench_config = coerce_config(config)
    drafts: list[WindowDraft] = []
    padding = workbench_config.refinement.window_padding_frames
    merge_gap = workbench_config.fusion.merge_gap_frames
    total_frames = video_source.total_frames

    for candidate in coarse_boundaries:
        source_ids = [candidate.id]
        _append_draft(
            drafts,
            candidate.start_frame - padding,
            candidate.end_frame + padding,
            "candidate_padding",
            source_ids,
            total_frames,
        )

        if candidate.confidence < 0.65:
            _append_draft(
                drafts,
                candidate.start_frame - padding,
                candidate.end_frame + padding,
                "low_confidence",
                source_ids,
                total_frames,
            )

        if _is_gradual_suspect(candidate):
            _append_draft(
                drafts,
                candidate.start_frame - padding,
                candidate.end_frame + padding,
                "gradual_suspect",
                source_ids,
                total_frames,
            )

    drafts.extend(
        _build_long_scene_windows(video_source, coarse_boundaries, workbench_config)
    )

    merged_drafts = _merge_drafts(drafts, merge_gap)
    windows: list[SuspiciousWindow] = []
    for index, draft in enumerate(merged_drafts, start=1):
        reason = "+".join(sorted(draft.reasons))
        windows.append(
            SuspiciousWindow(
                id=f"w_{index:04d}",
                start_frame=draft.start_frame,
                end_frame=draft.end_frame,
                reason=reason,
                source_boundary_ids=draft.source_boundary_ids,
            )
        )
    return windows
