from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from scene_workbench.config import (
    CoarseDetectionConfig,
    DetectorName,
    WorkbenchConfig,
    coerce_config,
    default_config,
)
from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
    VideoSource,
)


class PySceneDetectRunnerError(RuntimeError):
    """Raised when PySceneDetect coarse detection fails."""


@dataclass(slots=True, frozen=True)
class DetectorHit:
    frame: int
    score: float | None = None


def _load_scenedetect():
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import (
            AdaptiveDetector,
            ContentDetector,
            ThresholdDetector,
        )
    except ModuleNotFoundError as exc:
        raise PySceneDetectRunnerError(
            "PySceneDetect is required for coarse scene detection."
        ) from exc

    return {
        "SceneManager": SceneManager,
        "open_video": open_video,
        "ContentDetector": ContentDetector,
        "AdaptiveDetector": AdaptiveDetector,
        "ThresholdDetector": ThresholdDetector,
    }


def _make_detector_factory_map(
    config: CoarseDetectionConfig,
) -> dict[DetectorName, Callable[[dict[str, object]], object]]:
    return {
        "content": lambda api: api["ContentDetector"](
            threshold=config.content_threshold,
            min_scene_len=config.min_scene_len,
        ),
        "adaptive": lambda api: api["AdaptiveDetector"](
            adaptive_threshold=config.adaptive_threshold,
            min_scene_len=config.min_scene_len,
        ),
        "threshold": lambda api: api["ThresholdDetector"](
            min_scene_len=config.min_scene_len,
        ),
    }


def _detect_frames_for_detector(
    *,
    video_path: str | Path,
    detector_name: DetectorName,
    config: CoarseDetectionConfig,
) -> list[int]:
    api = _load_scenedetect()
    scene_manager = api["SceneManager"]()
    detector_factory = _make_detector_factory_map(config)[detector_name]
    scene_manager.add_detector(detector_factory(api))

    try:
        video = api["open_video"](str(video_path))
        scene_manager.detect_scenes(video=video)
        scene_list = scene_manager.get_scene_list()
    except Exception as exc:  # pragma: no cover
        raise PySceneDetectRunnerError(
            f"PySceneDetect failed while running `{detector_name}` detector."
        ) from exc

    return [start_time.get_frames() for start_time, _ in scene_list[1:]]


def _coerce_runner_config(
    config: WorkbenchConfig | CoarseDetectionConfig | dict | None,
) -> WorkbenchConfig:
    if config is None:
        return default_config()
    if isinstance(config, CoarseDetectionConfig):
        return WorkbenchConfig(coarse_detection=config)
    return coerce_config(config)


def _collect_detector_hits(
    video_source: VideoSource,
    config: WorkbenchConfig,
) -> dict[DetectorName, list[DetectorHit]]:
    hits: dict[DetectorName, list[DetectorHit]] = {}
    for detector_name in config.coarse_detection.detectors:
        frames = _detect_frames_for_detector(
            video_path=video_source.path,
            detector_name=detector_name,
            config=config.coarse_detection,
        )
        hits[detector_name] = [DetectorHit(frame=frame) for frame in frames]
    return hits


def _build_group_evidence(
    grouped_hits: dict[DetectorName, list[DetectorHit]],
) -> PySceneDetectGroupEvidence:
    def _evidence(detector_name: DetectorName) -> PySceneDetectEvidence:
        hits = grouped_hits.get(detector_name, [])
        scores = [hit.score for hit in hits if hit.score is not None]
        return PySceneDetectEvidence(
            triggered=bool(hits),
            detector=detector_name,
            score=scores[0] if len(scores) == 1 else None,
            scores=scores or None,
        )

    return PySceneDetectGroupEvidence(
        content=_evidence("content"),
        adaptive=_evidence("adaptive"),
        threshold=_evidence("threshold"),
    )


def _infer_boundary_type(triggered_by: set[DetectorName]) -> str:
    if "content" in triggered_by or "adaptive" in triggered_by:
        return "hard_cut"
    return "unknown"


def _infer_confidence(triggered_by: set[DetectorName]) -> float:
    confidence = 0.0
    if "content" in triggered_by:
        confidence = max(confidence, 0.60)
    if "adaptive" in triggered_by:
        confidence = max(confidence, 0.55)
    if "threshold" in triggered_by:
        confidence = max(confidence, 0.65)
    return confidence or 0.50


def _merge_detector_hits(
    detector_hits: dict[DetectorName, Iterable[DetectorHit]],
) -> list[BoundaryCandidate]:
    merged: dict[int, dict[DetectorName, list[DetectorHit]]] = {}
    for detector_name, hits in detector_hits.items():
        for hit in hits:
            per_frame = merged.setdefault(hit.frame, {})
            per_frame.setdefault(detector_name, []).append(hit)

    boundaries: list[BoundaryCandidate] = []
    for index, frame in enumerate(sorted(merged), start=1):
        grouped_hits = merged[frame]
        triggered_by = set(grouped_hits)
        boundaries.append(
            BoundaryCandidate(
                id=f"c_{index:04d}",
                start_frame=frame,
                end_frame=frame,
                recommended_cut_frame=frame,
                boundary_type=_infer_boundary_type(triggered_by),
                confidence=_infer_confidence(triggered_by),
                review_state="unreviewed",
                detector_evidence=DetectorEvidence(
                    pyscenedetect=_build_group_evidence(grouped_hits)
                ),
                notes=[
                    "coarse candidate generated by PySceneDetect detectors: "
                    + ", ".join(sorted(triggered_by))
                ],
                source_boundary_ids=[],
            )
        )
    return boundaries


def run_pyscenedetect(
    video_source: VideoSource | str | Path,
    config: WorkbenchConfig | CoarseDetectionConfig | dict | None = None,
) -> list[BoundaryCandidate]:
    effective_config = _coerce_runner_config(config)

    if isinstance(video_source, VideoSource):
        resolved_video_source = video_source
    else:
        path = Path(video_source).expanduser()
        if not path.exists():
            raise PySceneDetectRunnerError(f"Video file not found: {path}")
        if not path.is_file():
            raise PySceneDetectRunnerError(f"Video path is not a file: {path}")
        resolved_video_source = VideoSource(
            path=str(path),
            fps=0.0,
            width=0,
            height=0,
            total_frames=1,
            duration_sec=0.0,
        )

    detector_hits = _collect_detector_hits(resolved_video_source, effective_config)
    return _merge_detector_hits(detector_hits)
