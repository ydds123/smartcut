from __future__ import annotations

import json
from pathlib import Path

from scene_workbench.export._common import ensure_output_path, select_export_boundaries
from scene_workbench.models import ProjectManifest


def export_json(
    manifest: ProjectManifest,
    output_path: str | Path,
    *,
    reviewed_only: bool | None = None,
) -> Path:
    boundaries = select_export_boundaries(manifest, reviewed_only=reviewed_only)
    payload = {
        "manifest_id": manifest.manifest_id,
        "video": manifest.video.model_dump(mode="json"),
        "summary": {
            "exported_boundaries": len(boundaries),
        },
        "boundaries": [boundary.model_dump(mode="json") for boundary in boundaries],
    }
    path = ensure_output_path(output_path)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
