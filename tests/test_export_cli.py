from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scene_workbench.cli import app
from scene_workbench.review.store import load_manifest, save_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_export_command_writes_json(tmp_path: Path) -> None:
    runner = CliRunner()
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)
    output_path = tmp_path / "export.json"

    result = runner.invoke(
        app,
        [
            "export",
            str(manifest_path),
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["manifest_id"] == manifest.manifest_id


def test_export_command_rejects_unknown_format(tmp_path: Path) -> None:
    runner = CliRunner()
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)

    result = runner.invoke(
        app,
        [
            "export",
            str(manifest_path),
            "--format",
            "unknown",
            "--output",
            str(tmp_path / "out.txt"),
        ],
    )

    assert result.exit_code != 0
    assert "json, cutlist, edl, ffmpeg" in result.stderr
