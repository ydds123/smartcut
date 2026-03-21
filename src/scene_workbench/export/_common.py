from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scene_workbench.models import BoundaryCandidate, ProjectManifest


ACTIVE_REVIEW_STATES = {"accepted", "adjusted", "merged", "inserted"}


@dataclass(slots=True, frozen=True)
class Segment:
    index: int
    start_frame: int
    end_frame: int


def should_export_reviewed_only(manifest: ProjectManifest) -> bool:
    export_config = manifest.config.get("export", {})
    value = export_config.get("accepted_only", True)
    return bool(value)


def select_export_boundaries(
    manifest: ProjectManifest,
    *,
    reviewed_only: bool | None = None,
) -> list[BoundaryCandidate]:
    use_reviewed_only = (
        should_export_reviewed_only(manifest)
        if reviewed_only is None
        else reviewed_only
    )
    boundaries = list(manifest.final_boundaries)
    if use_reviewed_only:
        boundaries = [
            boundary
            for boundary in boundaries
            if boundary.review_state in ACTIVE_REVIEW_STATES
        ]
    return sorted(boundaries, key=lambda item: (item.start_frame, item.end_frame, item.id))


def frame_to_seconds(frame: int, fps: float) -> float:
    if fps <= 0:
        return 0.0
    return frame / fps


def frame_to_timecode(frame: int, fps: float) -> str:
    safe_fps = max(int(round(fps)), 1)
    total_seconds, frames = divmod(max(frame, 0), safe_fps)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def frame_to_timestamp(frame: int, fps: float) -> str:
    total_seconds = frame_to_seconds(frame, fps)
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"


def build_segments(manifest: ProjectManifest, boundaries: list[BoundaryCandidate]) -> list[Segment]:
    if manifest.video.total_frames <= 0:
        return []

    cut_frames = sorted(
        {
            max(0, min(boundary.recommended_cut_frame, manifest.video.total_frames - 1))
            for boundary in boundaries
        }
    )

    starts = [0, *cut_frames]
    segments: list[Segment] = []
    for index, start_frame in enumerate(starts, start=1):
        if index - 1 < len(cut_frames):
            end_frame = cut_frames[index - 1] - 1
        else:
            end_frame = manifest.video.total_frames - 1
        if end_frame < start_frame:
            continue
        segments.append(
            Segment(index=index, start_frame=start_frame, end_frame=end_frame)
        )
    return segments


def ensure_output_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
