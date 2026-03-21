from __future__ import annotations

from pathlib import Path

from scene_workbench.export._common import (
    ensure_output_path,
    frame_to_timecode,
    frame_to_timestamp,
    select_export_boundaries,
)
from scene_workbench.models import ProjectManifest


def export_cut_list(
    manifest: ProjectManifest,
    output_path: str | Path,
    *,
    reviewed_only: bool | None = None,
) -> Path:
    boundaries = select_export_boundaries(manifest, reviewed_only=reviewed_only)
    fps = manifest.video.fps
    lines = [
        f"# scene-workbench cut list",
        f"# manifest_id: {manifest.manifest_id}",
        f"# video: {manifest.video.path}",
        "index\tboundary_id\ttimestamp\ttimecode\tboundary_type\treview_state\tstart_frame\tend_frame\trecommended_cut_frame",
    ]
    for index, boundary in enumerate(boundaries, start=1):
        lines.append(
            "\t".join(
                [
                    str(index),
                    boundary.id,
                    frame_to_timestamp(boundary.recommended_cut_frame, fps),
                    frame_to_timecode(boundary.recommended_cut_frame, fps),
                    boundary.boundary_type,
                    boundary.review_state,
                    str(boundary.start_frame),
                    str(boundary.end_frame),
                    str(boundary.recommended_cut_frame),
                ]
            )
        )

    path = ensure_output_path(output_path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
