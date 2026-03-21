from __future__ import annotations

from pathlib import Path

from scene_workbench.export._common import (
    build_segments,
    ensure_output_path,
    frame_to_timecode,
    select_export_boundaries,
)
from scene_workbench.models import ProjectManifest


def export_edl(
    manifest: ProjectManifest,
    output_path: str | Path,
    *,
    reviewed_only: bool | None = None,
) -> Path:
    boundaries = select_export_boundaries(manifest, reviewed_only=reviewed_only)
    segments = build_segments(manifest, boundaries)
    fps = manifest.video.fps

    lines = [
        f"TITLE: {manifest.manifest_id}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    record_cursor = 0
    for segment in segments:
        duration_frames = segment.end_frame - segment.start_frame + 1
        source_in = frame_to_timecode(segment.start_frame, fps)
        source_out = frame_to_timecode(segment.end_frame + 1, fps)
        record_in = frame_to_timecode(record_cursor, fps)
        record_out = frame_to_timecode(record_cursor + duration_frames, fps)
        lines.append(
            f"{segment.index:03d}  AX       V     C        {source_in} {source_out} {record_in} {record_out}"
        )
        lines.append(f"* FROM CLIP NAME: {Path(manifest.video.path).name}")
        record_cursor += duration_frames

    path = ensure_output_path(output_path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
