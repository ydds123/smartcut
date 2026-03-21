import json

from typer.testing import CliRunner

from scene_workbench.cli import app
from scene_workbench.models import (
    ManifestSummary,
    ManifestSummaryCounts,
    ProjectManifest,
    VideoSource,
)


def test_version_flag_outputs_version():
    runner = CliRunner()

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_analyze_command_writes_manifest(monkeypatch, tmp_path):
    runner = CliRunner()
    output_path = tmp_path / "manifest.json"

    manifest = ProjectManifest(
        version="v1",
        manifest_id="demo_v1_0001",
        video=VideoSource(
            path="demo.mp4",
            fps=24.0,
            width=1920,
            height=1080,
            total_frames=240,
            duration_sec=10.0,
        ),
        config={},
        coarse_boundaries=[],
        suspicious_windows=[],
        refined_boundaries=[],
        final_boundaries=[],
        review_actions=[],
        summary=ManifestSummary(
            counts=ManifestSummaryCounts(
                coarse_boundaries=0,
                suspicious_windows=0,
                refined_boundaries=0,
                final_boundaries=0,
                accepted=0,
                adjusted=0,
                merged=0,
                inserted=0,
                rejected=0,
            )
        ),
    )
    monkeypatch.setattr("scene_workbench.cli.analyze_video", lambda *_args, **_kwargs: manifest)

    result = runner.invoke(
        app,
        ["analyze", "demo.mp4", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["manifest_id"] == "demo_v1_0001"


def test_review_command_launches_local_server(monkeypatch, tmp_path):
    runner = CliRunner()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    launched = {}

    def fake_launch(path, *, host, port, open_browser):
        launched["path"] = str(path)
        launched["host"] = host
        launched["port"] = port
        launched["open_browser"] = open_browser

    monkeypatch.setattr("scene_workbench.web.app.launch_review_server", fake_launch)

    result = runner.invoke(
        app,
        [
            "review",
            str(manifest_path),
            "--host",
            "127.0.0.1",
            "--port",
            "9000",
            "--no-open-browser",
        ],
    )

    assert result.exit_code == 0
    assert launched == {
        "path": str(manifest_path),
        "host": "127.0.0.1",
        "port": 9000,
        "open_browser": False,
    }


def test_inspect_command_outputs_summary(tmp_path):
    runner = CliRunner()
    manifest = ProjectManifest(
        version="v1",
        manifest_id="demo_v1_0002",
        video=VideoSource(
            path="demo.mp4",
            fps=24.0,
            width=1920,
            height=1080,
            total_frames=240,
            duration_sec=10.0,
        ),
        config={},
        coarse_boundaries=[],
        suspicious_windows=[],
        refined_boundaries=[],
        final_boundaries=[],
        review_actions=[],
        summary=ManifestSummary(
            counts=ManifestSummaryCounts(
                coarse_boundaries=0,
                suspicious_windows=0,
                refined_boundaries=0,
                final_boundaries=0,
                accepted=0,
                adjusted=0,
                merged=0,
                inserted=0,
                rejected=0,
            )
        ),
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(app, ["inspect", str(manifest_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["manifest_id"] == "demo_v1_0002"
    assert payload["evaluation"]["final_boundaries"] == 0
