from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from scene_workbench.models import VideoSource


class MediaIngestError(RuntimeError):
    """Raised when a local video cannot be normalized into a VideoSource."""


MediaInputError = MediaIngestError


def _load_cv2():
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:
        raise MediaIngestError(
            "opencv-python-headless is required to read local video metadata."
        ) from exc
    return cv2


_import_cv2 = _load_cv2


def _is_probable_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def load_video_source(video_path: str | Path) -> VideoSource:
    raw_path = str(video_path)
    if _is_probable_url(raw_path):
        raise MediaIngestError("Only local video files are supported in V1.")

    path = Path(video_path).expanduser()
    if not path.exists():
        raise MediaIngestError(f"Video file not found: {path}")
    if not path.is_file():
        raise MediaIngestError(f"Video path is not a file: {path}")

    cv2 = _load_cv2()
    capture = cv2.VideoCapture(str(path))
    if capture is None or not capture.isOpened():
        raise MediaIngestError(f"Failed to open video file: {path}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        total_frames = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
    finally:
        capture.release()

    if fps <= 0:
        raise MediaIngestError(f"Invalid FPS read from video metadata: {path}")
    if width <= 0 or height <= 0:
        raise MediaIngestError(f"Invalid frame size read from video metadata: {path}")
    if total_frames <= 0:
        raise MediaIngestError(f"Invalid frame count read from video metadata: {path}")

    return VideoSource(
        path=str(path),
        fps=fps,
        width=width,
        height=height,
        total_frames=total_frames,
        duration_sec=total_frames / fps,
    )


read_video_source = load_video_source
