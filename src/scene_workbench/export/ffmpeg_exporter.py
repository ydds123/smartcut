from __future__ import annotations

from pathlib import Path

from scene_workbench.export._common import (
    build_segments,
    ensure_output_path,
    frame_to_seconds,
    select_export_boundaries,
)
from scene_workbench.models import ProjectManifest


def export_ffmpeg_split(
    manifest: ProjectManifest,
    output_path: str | Path,
    *,
    reviewed_only: bool | None = None,
) -> Path:
    boundaries = select_export_boundaries(manifest, reviewed_only=reviewed_only)
    segments = build_segments(manifest, boundaries)
    fps = manifest.video.fps
    video_path = manifest.video.path.replace("\\", "/")
    stem = Path(manifest.video.path).stem or "video"

    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]
    for segment in segments:
        start_seconds = frame_to_seconds(segment.start_frame, fps)
        duration_seconds = frame_to_seconds(
            segment.end_frame - segment.start_frame + 1,
            fps,
        )
        output_name = f"{stem}_segment_{segment.index:04d}.mp4"
        lines.append(
            "ffmpeg -y "
            f"-ss {start_seconds:.3f} "
            f"-i \"{video_path}\" "
            f"-t {duration_seconds:.3f} "
            f"-c copy \"{output_name}\""
        )

    path = ensure_output_path(output_path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
