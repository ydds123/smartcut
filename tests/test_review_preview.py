from __future__ import annotations

from pathlib import Path

from scene_workbench.review.preview import build_boundary_preview
from scene_workbench.review.store import load_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_boundary_preview_includes_context_and_evidence() -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    preview = build_boundary_preview(manifest.video, manifest.final_boundaries[2])

    assert preview.boundary_id == "f_0003"
    assert any(frame.label == "mid" for frame in preview.context_frames)
    assert any("transnetv2" in item for item in preview.evidence_summary)
