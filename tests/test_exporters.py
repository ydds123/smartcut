from __future__ import annotations

import json
from pathlib import Path

from scene_workbench.export import (
    export_cut_list,
    export_edl,
    export_ffmpeg_split,
    export_json,
)
from scene_workbench.review.store import load_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _load_manifest():
    return load_manifest(FIXTURES_DIR / "manifest.v1.example.json")


def test_export_json_uses_final_boundaries(tmp_path: Path) -> None:
    manifest = _load_manifest()
    output = tmp_path / "out.json"

    export_json(manifest, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["manifest_id"] == manifest.manifest_id
    assert len(payload["boundaries"]) == 4
    assert payload["boundaries"][0]["id"] == "f_0001"


def test_export_cut_list_contains_timecodes(tmp_path: Path) -> None:
    manifest = _load_manifest()
    output = tmp_path / "cuts.txt"

    export_cut_list(manifest, output)
    content = output.read_text(encoding="utf-8")

    assert "boundary_id" in content
    assert "f_0001" in content
    assert "00:00:10:08" in content


def test_export_edl_creates_event_lines(tmp_path: Path) -> None:
    manifest = _load_manifest()
    output = tmp_path / "result.edl"

    export_edl(manifest, output)
    content = output.read_text(encoding="utf-8")

    assert "TITLE:" in content
    assert "001  AX" in content
    assert "FROM CLIP NAME" in content


def test_export_ffmpeg_creates_split_commands(tmp_path: Path) -> None:
    manifest = _load_manifest()
    output = tmp_path / "split.sh"

    export_ffmpeg_split(manifest, output)
    content = output.read_text(encoding="utf-8")

    assert "ffmpeg -y" in content
    assert "demo_shortfilm_segment_0001.mp4" in content
    assert "./fixtures/demo_shortfilm.mp4" in content


def test_export_reviewed_only_filters_unreviewed_boundaries(tmp_path: Path) -> None:
    manifest = _load_manifest()
    manifest.final_boundaries[0].review_state = "unreviewed"
    output = tmp_path / "filtered.json"

    export_json(manifest, output, reviewed_only=True)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert {item["id"] for item in payload["boundaries"]} == {"f_0002", "f_0003", "f_0004"}
