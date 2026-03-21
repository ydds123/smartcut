from __future__ import annotations

import json
from pathlib import Path

from scene_workbench.config import SceneWorkbenchConfig, default_config
from scene_workbench.models import ProjectManifest, build_manifest_summary


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_manifest_example_deserializes() -> None:
    manifest = ProjectManifest.model_validate_json(
        (FIXTURES_DIR / "manifest.v1.example.json").read_text(encoding="utf-8-sig")
    )

    assert manifest.version == "v1"
    assert manifest.video.fps == 24.0
    assert len(manifest.coarse_boundaries) == 5
    assert manifest.final_boundaries[2].boundary_type == "dissolve"


def test_build_manifest_summary_matches_example_counts() -> None:
    manifest = ProjectManifest.model_validate_json(
        (FIXTURES_DIR / "manifest.v1.example.json").read_text(encoding="utf-8-sig")
    )

    summary = build_manifest_summary(
        coarse_boundaries=manifest.coarse_boundaries,
        suspicious_windows=manifest.suspicious_windows,
        refined_boundaries=manifest.refined_boundaries,
        final_boundaries=manifest.final_boundaries,
        review_actions=manifest.review_actions,
    )

    assert manifest.summary is not None
    assert summary == manifest.summary


def test_default_config_matches_document_defaults() -> None:
    config = default_config()

    assert isinstance(config, SceneWorkbenchConfig)
    assert config.coarse_detection.detectors == ["content", "adaptive", "threshold"]
    assert config.refinement.window_padding_frames == 12
    assert config.fusion.merge_gap_frames == 6
    assert config.export.default_formats == ["json", "edl", "ffmpeg"]

    manifest_config = json.loads(json.dumps(config.to_manifest_config()))
    assert manifest_config["review"]["autosave"] is True
