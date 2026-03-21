"""TransNetV2 refinement 集成。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import warnings
from typing import Callable

import numpy as np

from scene_workbench.config import WorkbenchConfig, coerce_config
from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    SuspiciousWindow,
    TransNetV2Evidence,
    VideoSource,
)


@dataclass(slots=True)
class TransNetPrediction:
    start_frame: int
    end_frame: int
    boundary_type: str
    score: float
    recommended_cut_frame: int | None = None
    notes: list[str] | None = None


TransNetPredictor = Callable[
    [VideoSource, SuspiciousWindow, WorkbenchConfig],
    list[TransNetPrediction],
]


def _load_cv2():
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
        raise ModuleNotFoundError(
            "opencv-python is required for TransNetV2 window decoding."
        ) from exc
    return cv2


@lru_cache(maxsize=2)
def _load_transnet_model(device: str):
    try:
        from transnetv2_pytorch import TransNetV2
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency
        raise ModuleNotFoundError(
            "transnetv2-pytorch is required for refinement."
        ) from exc
    return TransNetV2(device=device)


def _decode_window_frames(
    video_source: VideoSource,
    window: SuspiciousWindow,
) -> np.ndarray:
    cv2 = _load_cv2()
    capture = cv2.VideoCapture(video_source.path)
    if capture is None or not capture.isOpened():
        raise RuntimeError(f"Failed to open video for refinement: {video_source.path}")

    capture.set(cv2.CAP_PROP_POS_FRAMES, window.start_frame)
    frames: list[np.ndarray] = []
    try:
        for _ in range(window.start_frame, window.end_frame + 1):
            ok, frame = capture.read()
            if not ok:
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (48, 27), interpolation=cv2.INTER_AREA)
            frames.append(frame)
    finally:
        capture.release()

    return np.asarray(frames, dtype=np.uint8)


def _find_segments(values: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    active = values >= threshold
    segments: list[tuple[int, int]] = []
    start: int | None = None
    for index, is_active in enumerate(active):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            segments.append((start, index - 1))
            start = None
    if start is not None:
        segments.append((start, len(values) - 1))
    return segments


def _extract_transnet_predictions(
    window: SuspiciousWindow,
    single_frame_predictions: np.ndarray,
    many_hot_predictions: np.ndarray,
    config: WorkbenchConfig,
) -> list[TransNetPrediction]:
    predictions: list[TransNetPrediction] = []
    used_indices: set[int] = set()
    gradual_segments = _find_segments(
        many_hot_predictions,
        config.refinement.gradual_threshold,
    )

    for local_start, local_end in gradual_segments:
        segment_len = local_end - local_start + 1
        if segment_len < config.refinement.gradual_min_frames:
            continue

        segment_scores = many_hot_predictions[local_start : local_end + 1]
        peak_local_index = int(np.argmax(segment_scores)) + local_start
        predictions.append(
            TransNetPrediction(
                start_frame=window.start_frame + local_start,
                end_frame=window.start_frame + local_end,
                boundary_type="dissolve",
                score=float(np.max(segment_scores)),
                recommended_cut_frame=window.start_frame + peak_local_index,
                notes=[f"transnetv2 gradual segment from window {window.id}"],
            )
        )
        used_indices.update(range(local_start, local_end + 1))

    hard_cut_indices = np.where(single_frame_predictions >= config.refinement.threshold)[0]
    for local_index in hard_cut_indices.tolist():
        if local_index in used_indices:
            continue
        predictions.append(
            TransNetPrediction(
                start_frame=window.start_frame + local_index,
                end_frame=window.start_frame + local_index,
                boundary_type="hard_cut",
                score=float(single_frame_predictions[local_index]),
                recommended_cut_frame=window.start_frame + local_index,
                notes=[f"transnetv2 hard cut peak from window {window.id}"],
            )
        )

    return sorted(
        predictions,
        key=lambda item: (item.start_frame, item.end_frame, item.recommended_cut_frame or item.start_frame),
    )


def _build_transnet_predictor(config: WorkbenchConfig) -> TransNetPredictor:
    model = _load_transnet_model(config.refinement.device)

    def _predict(
        video_source: VideoSource,
        window: SuspiciousWindow,
        _config: WorkbenchConfig,
    ) -> list[TransNetPrediction]:
        frames = _decode_window_frames(video_source, window)
        if len(frames) == 0:
            return []

        import torch

        with torch.no_grad():
            single, many = model.predict_frames(
                torch.from_numpy(frames),
                quiet=True,
            )

        return _extract_transnet_predictions(
            window,
            single.cpu().numpy(),
            many.cpu().numpy(),
            config,
        )

    return _predict


def run_transnetv2(
    video_source: VideoSource,
    suspicious_windows: list[SuspiciousWindow],
    config: WorkbenchConfig | dict | None = None,
    predictor: TransNetPredictor | None = None,
) -> list[BoundaryCandidate]:
    """运行 refinement；默认在后端缺失时优雅降级。"""
    workbench_config = coerce_config(config)
    if not workbench_config.refinement.enabled or not suspicious_windows:
        return []

    if predictor is None:
        try:
            effective_predictor = _build_transnet_predictor(workbench_config)
        except Exception as exc:
            warnings.warn(
                f"TransNetV2 backend 尚未接入或初始化失败，当前跳过 refinement，保留 coarse 输出。原因: {exc}",
                stacklevel=2,
            )
            return []
    else:
        effective_predictor = predictor

    if predictor is None:
        warnings.warn(
            "TransNetV2 backend 已接入，当前使用真实模型进行 refinement。",
            stacklevel=2,
        )

    refined_boundaries: list[BoundaryCandidate] = []
    for window_index, window in enumerate(suspicious_windows, start=1):
        predictions = effective_predictor(video_source, window, workbench_config)
        for prediction_index, prediction in enumerate(predictions, start=1):
            recommended_cut_frame = prediction.recommended_cut_frame
            if recommended_cut_frame is None:
                recommended_cut_frame = (
                    prediction.start_frame + prediction.end_frame
                ) // 2

            refined_boundaries.append(
                BoundaryCandidate(
                    id=f"r_{window_index:04d}_{prediction_index:02d}",
                    start_frame=prediction.start_frame,
                    end_frame=prediction.end_frame,
                    recommended_cut_frame=recommended_cut_frame,
                    boundary_type=prediction.boundary_type,  # type: ignore[arg-type]
                    confidence=prediction.score,
                    review_state="unreviewed",
                    detector_evidence=DetectorEvidence(
                        transnetv2=TransNetV2Evidence(
                            triggered=True,
                            score=prediction.score,
                            window_id=window.id,
                        )
                    ),
                    notes=prediction.notes or [],
                    source_boundary_ids=list(window.source_boundary_ids),
                )
            )

    return refined_boundaries
