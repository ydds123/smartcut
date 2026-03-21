from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scene_workbench.cli import app
from scene_workbench.review.store import load_manifest, save_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_baseline_command_writes_json_and_markdown(tmp_path: Path) -> None:
    runner = CliRunner()
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)
    output_json = tmp_path / "baseline.json"
    output_md = tmp_path / "baseline.md"

    result = runner.invoke(
        app,
        [
            "baseline",
            str(manifest_path),
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["aggregate"]["sample_count"] == 1
    assert "Baseline Report" in output_md.read_text(encoding="utf-8")
