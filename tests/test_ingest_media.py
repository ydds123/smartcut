from pathlib import Path

import pytest

from scene_workbench.ingest.media import MediaIngestError, load_video_source


class FakeCapture:
    def __init__(self, opened: bool = True):
        self._opened = opened

    def isOpened(self) -> bool:
        return self._opened

    def get(self, key: int) -> float:
        values = {
            1: 24.0,
            2: 1920,
            3: 1080,
            4: 240.0,
        }
        return values[key]

    def release(self) -> None:
        return None


class FakeCv2:
    CAP_PROP_FPS = 1
    CAP_PROP_FRAME_WIDTH = 2
    CAP_PROP_FRAME_HEIGHT = 3
    CAP_PROP_FRAME_COUNT = 4

    def VideoCapture(self, _path: str) -> FakeCapture:
        return FakeCapture()


def test_load_video_source_reads_metadata(monkeypatch, tmp_path: Path):
    video_path = tmp_path / "demo.mp4"
    video_path.write_bytes(b"fake")
    monkeypatch.setattr("scene_workbench.ingest.media._load_cv2", lambda: FakeCv2())

    video = load_video_source(video_path)

    assert video.path == str(video_path)
    assert video.fps == 24.0
    assert video.width == 1920
    assert video.height == 1080
    assert video.total_frames == 240
    assert video.duration_sec == 10.0


def test_load_video_source_rejects_url():
    with pytest.raises(MediaIngestError):
        load_video_source("https://example.com/demo.mp4")
