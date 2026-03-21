from __future__ import annotations

from pathlib import Path

from scene_workbench.evaluation import build_evaluation_snapshot
from scene_workbench.review.store import load_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_evaluation_snapshot_uses_manifest_summary() -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")

    snapshot = build_evaluation_snapshot(manifest)

    assert snapshot.manifest_id == manifest.manifest_id
    assert snapshot.false_splits == 1
    assert snapshot.missed_boundaries == 1
    assert snapshot.adjustments == 1
    assert snapshot.merges == 1
    assert snapshot.final_boundaries == 4
    assert snapshot.review_completion_rate == 1.0
