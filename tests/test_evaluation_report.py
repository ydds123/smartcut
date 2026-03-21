from __future__ import annotations

import json
from pathlib import Path

from scene_workbench.evaluation import (
    build_baseline_report,
    export_baseline_report_json,
    export_baseline_report_markdown,
    load_manifests_for_report,
)
from scene_workbench.review.store import load_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_build_baseline_report_aggregates_snapshots() -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")

    report = build_baseline_report([manifest, manifest])

    assert report.aggregate.sample_count == 2
    assert report.aggregate.false_splits == 2
    assert report.aggregate.missed_boundaries == 2
    assert report.aggregate.manual_review_actions == 10


def test_export_baseline_report_files(tmp_path: Path) -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    report = build_baseline_report([manifest])
    json_path = tmp_path / "baseline.json"
    md_path = tmp_path / "baseline.md"

    export_baseline_report_json(report, json_path)
    export_baseline_report_markdown(report, md_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["aggregate"]["sample_count"] == 1
    assert "Baseline Report" in md_path.read_text(encoding="utf-8")


def test_load_manifests_for_report_reads_multiple_paths() -> None:
    paths = [
        FIXTURES_DIR / "manifest.v1.example.json",
        FIXTURES_DIR / "manifest.v1.example.json",
    ]
    manifests = load_manifests_for_report(paths)

    assert len(manifests) == 2
