from __future__ import annotations

from pathlib import Path

import pytest

from scene_workbench.config import CoarseDetectionConfig
from scene_workbench.detectors.pyscenedetect_runner import (
    DetectorHit,
    PySceneDetectRunnerError,
    run_pyscenedetect,
)
from scene_workbench.ingest import media
from scene_workbench.models import VideoSource


class FakeCapture:
    def __init__(self, *, opened: bool = True, fps: float = 24.0) -> None:
        self._opened = opened
        self._values = {
            "fps": fps,
            "width": 1920,
            "height": 1080,
            "frames": 240,
        }

    def isOpened(self) -> bool:
        return self._opened

    def get(self, prop: int) -> float:
        prop_map = {
            1: self._values["fps"],
            2: self._values["width"],
            3: self._values["height"],
            4: self._values["frames"],
        }
        return prop_map[prop]

    def release(self) -> None:
        return None


class FakeCv2:
    CAP_PROP_FPS = 1
    CAP_PROP_FRAME_WIDTH = 2
    CAP_PROP_FRAME_HEIGHT = 3
    CAP_PROP_FRAME_COUNT = 4

    def __init__(self, capture: FakeCapture) -> None:
        self._capture = capture

    def VideoCapture(self, _: str) -> FakeCapture:
        return self._capture


def test_read_video_source_returns_normalized_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    video_path = tmp_path / "demo.mp4"
    video_path.write_bytes(b"demo")

    monkeypatch.setattr(media, "_load_cv2", lambda: FakeCv2(FakeCapture()))

    source = media.load_video_source(video_path)

    assert source.path == str(video_path)
    assert source.fps == 24.0
    assert source.total_frames == 240
    assert source.duration_sec == 10.0


def test_read_video_source_raises_clear_error_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.mp4"

    with pytest.raises(media.MediaIngestError, match="Video file not found"):
        media.load_video_source(missing_path)


def test_run_pyscenedetect_merges_detector_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=300,
        duration_sec=12.5,
    )

    fake_hits = {
        "content": [DetectorHit(frame=100), DetectorHit(frame=250)],
        "adaptive": [DetectorHit(frame=100)],
        "threshold": [DetectorHit(frame=400)],
    }

    monkeypatch.setattr(
        "scene_workbench.detectors.pyscenedetect_runner._collect_detector_hits",
        lambda *_args, **_kwargs: fake_hits,
    )

    boundaries = run_pyscenedetect(video, CoarseDetectionConfig())

    assert [boundary.id for boundary in boundaries] == ["c_0001", "c_0002", "c_0003"]
    assert boundaries[0].recommended_cut_frame == 100
    assert boundaries[0].boundary_type == "hard_cut"
    assert boundaries[0].detector_evidence.pyscenedetect is not None
    assert boundaries[0].detector_evidence.pyscenedetect.content.triggered is True
    assert boundaries[0].detector_evidence.pyscenedetect.adaptive.triggered is True
    assert boundaries[2].boundary_type == "unknown"
    assert boundaries[2].confidence == 0.65


def test_run_pyscenedetect_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(PySceneDetectRunnerError, match="Video file not found"):
        run_pyscenedetect(tmp_path / "missing.mp4")
