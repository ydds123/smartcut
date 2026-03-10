"""PySceneDetect integration resilience tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from app.core.config import settings
from app.services.quality_tuning import DEFAULT_QUALITY_CONFIG, _normalize_quality_config
from app.services.video_processor import VideoProcessor


def _make_processor(tmp_path: Path, monkeypatch) -> VideoProcessor:
    task_root = tmp_path / "tasks"
    monkeypatch.setattr(settings, "TASK_DIR", str(task_root), raising=False)
    video_path = str(tmp_path / "input.mp4")
    return VideoProcessor("test-task", video_path, processing_config={})


def test_detect_with_pyscene_degrades_to_single_scene_when_all_commands_fail(tmp_path, monkeypatch):
    processor = _make_processor(tmp_path, monkeypatch)
    monkeypatch.setattr(processor, "_get_video_duration_ms", lambda: 4321)

    attempted_commands: list[list[str]] = []

    def _raise_missing(cmd, **kwargs):
        attempted_commands.append(cmd)
        raise FileNotFoundError("scenedetect not found")

    with patch("app.services.video_processor.subprocess.run", side_effect=_raise_missing):
        scenes = processor._detect_with_pyscene()

    assert scenes == [(0, 4321)]
    assert len(attempted_commands) == 2
    assert attempted_commands[0][0:4] == [sys.executable, "-m", "scenedetect", "-i"]
    assert attempted_commands[1][0:3] == [sys.executable, "-m", "scenedetect"]
    assert attempted_commands[1].count("--stats") == 1
    assert processor.video_path in attempted_commands[1]


def test_detect_with_pyscene_falls_back_to_default_content_detector(tmp_path, monkeypatch):
    processor = _make_processor(tmp_path, monkeypatch)

    fallback_cmd: list[str] = []
    result = subprocess.CompletedProcess(args=[sys.executable, "-m", "scenedetect"], returncode=0, stdout="", stderr="")
    calls = {"count": 0}

    def _primary_then_fallback(cmd, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise subprocess.CalledProcessError(returncode=2, cmd=cmd, stderr="invalid flag")
        fallback_cmd.extend(cmd)
        return result

    with (
        patch("app.services.video_processor.subprocess.run", side_effect=_primary_then_fallback),
        patch.object(processor, "_parse_scene_list", return_value=[(0, 1000), (1000, 2000)]),
    ):
        scenes = processor._detect_with_pyscene()

    assert scenes == [(0, 1000), (1000, 2000)]
    assert calls["count"] == 2
    assert fallback_cmd[0:3] == [sys.executable, "-m", "scenedetect"]
    assert "detect-content" in fallback_cmd
    assert "list-scenes" in fallback_cmd


def test_read_stats_summary_prefers_adaptive_ratio_column(tmp_path, monkeypatch):
    processor = _make_processor(tmp_path, monkeypatch)
    stats_path = processor.task_dir / "scenes.stats.csv"
    stats_path.write_text(
        "\n".join(
            [
                "Frame Number,Timecode,adaptive_ratio (w=2),content_val",
                "2,00:00:00.040,2.5,20.0",
                "3,00:00:00.080,2.9,50.0",
            ]
        ),
        encoding="utf-8",
    )

    summary = processor._read_stats_summary(3.0, detector_type="adaptive")
    assert summary["stats_score_column"].lower().startswith("adaptive_ratio")
    assert summary["stats_score_max"] == 2.9
    assert summary["stats_near_miss_count"] == 2

    content_summary = processor._read_stats_summary(27.0, detector_type="content")
    assert content_summary["stats_score_column"] == "content_val"
    assert content_summary["stats_score_max"] == 50.0


def test_normalize_quality_config_clamps_threshold_and_merge_options():
    config = dict(DEFAULT_QUALITY_CONFIG)
    config.update(
        {
            "use_threshold_detector": True,
            "threshold_detector_threshold": 999.0,
            "threshold_detector_fade_bias": -150.0,
            "merge_gap_frames": -8,
            "split_copy_mode": "yes",
            "scenedetect_timeout_sec": 5,
        }
    )

    normalized = _normalize_quality_config(config)

    assert normalized["use_threshold_detector"] is True
    assert normalized["threshold_detector_threshold"] == 255.0
    assert normalized["threshold_detector_fade_bias"] == -100.0
    assert normalized["merge_gap_frames"] == 0
    assert normalized["split_copy_mode"] is True
    assert normalized["scenedetect_timeout_sec"] == 30
