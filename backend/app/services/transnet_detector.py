"""TransNetV2 boundary detector with robust model validation and graceful degradation."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from app.services.transnet_architecture import (
    TransNetV2,
    checkpoint_metadata,
    normalize_state_dict_keys,
)

logger = logging.getLogger(__name__)


class TransNetV2Detector:
    """Thread-safe TransNetV2 wrapper used by VideoProcessor precision mode."""

    MODEL_URLS = {
        # Legacy URL is kept for compatibility; it can currently return 404.
        "legacy": "https://github.com/soCzech/TransNetV2/raw/master/pytorchweights/transnetv2-pytorch-weights.pth",
        "mirror_cn": "https://ghproxy.com/https://github.com/soCzech/TransNetV2/raw/master/pytorchweights/transnetv2-pytorch-weights.pth",
    }

    DEFAULT_MODEL_DIR = Path.home() / ".smartcut" / "models"
    DEFAULT_MODEL_NAME = "transnetv2-pytorch-weights.pth"

    MIN_MODEL_SIZE_BYTES = 5 * 1024 * 1024
    # Official converted TransNetV2 checkpoint has 90 keys.
    MIN_EXPECTED_STATE_KEYS = 80
    REQUIRED_STATE_KEYS = {
        "SDDCNN.0.DDCNN.0.Conv3D_1.layers.0.weight",
        "SDDCNN.0.DDCNN.0.Conv3D_1.layers.1.weight",
        "fc1.weight",
        "cls_layer1.weight",
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        mode: str = "precision",
        threshold: float = 0.3,
        tolerance_frames: int = 12,
        window_size: int = 100,
        device: Optional[str] = None,
    ):
        self.model_path = model_path or str(self.DEFAULT_MODEL_DIR / self.DEFAULT_MODEL_NAME)
        self.mode = mode
        self.threshold = max(0.0, min(1.0, threshold))
        self.tolerance_frames = max(1, int(tolerance_frames))

        normalized_window = max(20, int(window_size))
        if normalized_window % 2 == 1:
            normalized_window += 1
        self.window_size = normalized_window

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self._model: Optional[TransNetV2] = None
        self._load_lock = threading.Lock()
        self._load_attempted = False
        self._load_failed = False

        logger.info(
            "TransNetV2Detector initialized: mode=%s threshold=%.3f tolerance=%s window=%s device=%s model=%s",
            self.mode,
            self.threshold,
            self.tolerance_frames,
            self.window_size,
            self.device,
            self.model_path,
        )

    def is_available(self) -> bool:
        if self._load_failed:
            return False
        return self._ensure_loaded()

    def get_mode_info(self) -> Dict[str, Any]:
        mode_info = {
            "fast": {
                "name": "快速模式",
                "time": "约 30 秒",
                "accuracy": "F1: ~77%",
                "description": "适合预览，快速生成场景切分",
                "model_type": "TransNetV2Lite",
            },
            "precision": {
                "name": "精准模式",
                "time": "约 1 分钟",
                "accuracy": "F1: ~88%",
                "description": "适合最终剪辑，深度学习验证",
                "model_type": "TransNetV2",
            },
        }
        info = mode_info.get(self.mode, mode_info["precision"]).copy()
        info["current_mode"] = self.mode
        info["device"] = str(self.device)
        info["threshold"] = self.threshold
        return info

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True

        if self._load_failed:
            return False

        with self._load_lock:
            if self._model is not None:
                return True
            if self._load_attempted:
                return self._model is not None

            self._load_attempted = True

            model_path = Path(self.model_path)
            if not model_path.exists():
                logger.warning("TransNetV2 model file not found: %s", model_path)
                self._load_failed = True
                return False

            metadata = checkpoint_metadata(str(model_path))
            size_bytes = int(metadata.get("size_bytes") or 0)
            num_keys = int(metadata.get("num_keys") or 0)

            if size_bytes < self.MIN_MODEL_SIZE_BYTES:
                logger.error(
                    "TransNetV2 model rejected: file too small (%s bytes < %s). "
                    "Likely invalid/incomplete checkpoint.",
                    size_bytes,
                    self.MIN_MODEL_SIZE_BYTES,
                )
                self._load_failed = True
                return False

            if num_keys < self.MIN_EXPECTED_STATE_KEYS:
                logger.error(
                    "TransNetV2 model rejected: too few state keys (%s < %s).",
                    num_keys,
                    self.MIN_EXPECTED_STATE_KEYS,
                )
                self._load_failed = True
                return False

            try:
                model = TransNetV2()
                payload = torch.load(model_path, map_location="cpu", weights_only=False)
                if isinstance(payload, dict) and "model_state_dict" in payload and isinstance(payload["model_state_dict"], dict):
                    state_dict = payload["model_state_dict"]
                elif isinstance(payload, dict) and "state_dict" in payload and isinstance(payload["state_dict"], dict):
                    state_dict = payload["state_dict"]
                elif isinstance(payload, dict):
                    state_dict = payload
                else:
                    raise ValueError("Unsupported checkpoint payload format")

                state_dict = normalize_state_dict_keys(state_dict)

                missing_required = [key for key in self.REQUIRED_STATE_KEYS if key not in state_dict]
                if missing_required:
                    logger.error("TransNetV2 model rejected: missing required keys: %s", missing_required)
                    self._load_failed = True
                    return False

                incompatible = model.load_state_dict(state_dict, strict=False)

                missing_count = len(incompatible.missing_keys)
                model_key_count = len(model.state_dict())
                matched_count = model_key_count - missing_count
                coverage = matched_count / max(1, model_key_count)

                if coverage < 0.95:
                    logger.error(
                        "TransNetV2 model rejected: low key coverage %.2f%% (matched=%s, total=%s).",
                        coverage * 100,
                        matched_count,
                        model_key_count,
                    )
                    self._load_failed = True
                    return False

                if incompatible.unexpected_keys:
                    logger.warning("TransNetV2 unexpected keys: %s", incompatible.unexpected_keys[:12])
                if incompatible.missing_keys:
                    logger.warning("TransNetV2 missing keys: %s", incompatible.missing_keys[:12])

                model.to(self.device)
                model.eval()
                self._model = model

                logger.info(
                    "TransNetV2 model loaded: coverage=%.2f%% size=%sMB keys=%s device=%s",
                    coverage * 100,
                    round(size_bytes / (1024 * 1024), 2),
                    num_keys,
                    self.device,
                )
                return True

            except Exception as exc:
                logger.error("TransNetV2 model loading failed: %s", exc)
                self._load_failed = True
                return False

    def detect_boundaries(
        self,
        video_path: str,
        candidate_frames: Optional[List[int]] = None,
    ) -> Dict[int, float]:
        if not self._ensure_loaded():
            logger.warning("TransNetV2 model unavailable, returning empty boundaries")
            return {}

        try:
            if candidate_frames:
                return self._detect_candidates_only(video_path, candidate_frames)
            return self._detect_full_video(video_path)
        except Exception as exc:
            logger.error("TransNetV2 detection failed: %s", exc)
            return {}

    def score_candidates(
        self,
        video_path: str,
        candidate_frames: List[int],
    ) -> Dict[int, float]:
        """
        Score candidate boundaries without threshold filtering.

        Returns:
            {frame_idx: probability}
        """
        if not self._ensure_loaded():
            return {}
        try:
            return self._score_candidates(video_path, candidate_frames)
        except Exception as exc:
            logger.error("TransNetV2 candidate scoring failed: %s", exc)
            return {}

    def _detect_candidates_only(self, video_path: str, candidate_frames: List[int]) -> Dict[int, float]:
        raw_scores = self._score_candidates(video_path, candidate_frames)
        return {frame_idx: prob for frame_idx, prob in raw_scores.items() if prob >= self.threshold}

    def _score_candidates(self, video_path: str, candidate_frames: List[int]) -> Dict[int, float]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video: %s", video_path)
            return {}

        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                return {}

            scores: Dict[int, float] = {}
            seen = set()

            for frame_idx in sorted(int(x) for x in candidate_frames if x is not None):
                if frame_idx < 0 or frame_idx >= total_frames or frame_idx in seen:
                    continue
                seen.add(frame_idx)

                start_frame = frame_idx - self.window_size // 2
                end_frame = start_frame + self.window_size
                frames = self._extract_window_frames(cap, start_frame, end_frame, total_frames)
                if frames is None or len(frames) == 0:
                    continue

                scores[frame_idx] = float(self._predict_single_window(frames))

            return scores

        finally:
            cap.release()

    def _detect_full_video(self, video_path: str) -> Dict[int, float]:
        frames = self._read_video_frames(video_path)
        if frames is None or len(frames) == 0:
            return {}

        single_probs, many_probs = self._predict_probabilities(frames)
        if single_probs.size == 0:
            return {}

        combined = np.maximum(single_probs, many_probs)
        return self._extract_peak_boundaries(combined)

    def _read_video_frames(self, video_path: str) -> Optional[np.ndarray]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video for TransNet full pass: %s", video_path)
            return None

        try:
            frames: list[np.ndarray] = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (48, 27), interpolation=cv2.INTER_AREA)
                frames.append(frame)

            if not frames:
                return None

            return np.ascontiguousarray(np.stack(frames, axis=0).astype(np.uint8))

        finally:
            cap.release()

    def _extract_window_frames(
        self,
        cap: cv2.VideoCapture,
        start_frame: int,
        end_frame: int,
        total_frames: int,
    ) -> Optional[np.ndarray]:
        required = max(0, end_frame - start_frame)
        if required == 0 or total_frames <= 0:
            return None

        clamped_start = max(0, start_frame)
        clamped_end = min(total_frames, end_frame)
        if clamped_start >= clamped_end:
            return None

        cap.set(cv2.CAP_PROP_POS_FRAMES, clamped_start)

        frames: list[np.ndarray] = []
        for _ in range(clamped_end - clamped_start):
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = cv2.resize(frame, (48, 27), interpolation=cv2.INTER_AREA)
            frames.append(frame)

        if not frames:
            return None

        pad_front = max(0, -start_frame)
        pad_back = max(0, end_frame - total_frames)

        if pad_front > 0:
            frames = [frames[0]] * pad_front + frames
        if pad_back > 0:
            frames = frames + [frames[-1]] * pad_back

        if len(frames) < required:
            frames = frames + [frames[-1]] * (required - len(frames))

        if len(frames) > required:
            frames = frames[:required]

        return np.ascontiguousarray(np.stack(frames, axis=0).astype(np.uint8))

    def _predict_probabilities(self, frames: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if self._model is None:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

        frame_count = len(frames)
        if frame_count == 0:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

        window_size = self.window_size
        stride = max(1, window_size // 2)
        context = (window_size - stride) // 2

        remainder = frame_count % stride
        pad_end = context + (stride - remainder if remainder != 0 else 0)

        start_pad = np.repeat(frames[:1], context, axis=0)
        end_pad = np.repeat(frames[-1:], pad_end, axis=0)
        padded_frames = np.concatenate([start_pad, frames, end_pad], axis=0)

        single_parts: list[np.ndarray] = []
        many_parts: list[np.ndarray] = []

        with torch.no_grad():
            ptr = 0
            while ptr + window_size <= len(padded_frames):
                window = padded_frames[ptr:ptr + window_size]
                ptr += stride

                inp = torch.from_numpy(window[np.newaxis]).to(device=self.device, dtype=torch.uint8)
                output = self._model(inp)

                if isinstance(output, tuple):
                    single_logits, many_logits_dict = output
                    many_logits = many_logits_dict["many_hot"]
                else:
                    single_logits = output
                    many_logits = output

                single_prob = torch.sigmoid(single_logits)[0, context:context + stride, 0].cpu().numpy()
                many_prob = torch.sigmoid(many_logits)[0, context:context + stride, 0].cpu().numpy()
                single_parts.append(single_prob)
                many_parts.append(many_prob)

        if not single_parts:
            return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)

        single = np.concatenate(single_parts, axis=0)[:frame_count].astype(np.float32, copy=False)
        many = np.concatenate(many_parts, axis=0)[:frame_count].astype(np.float32, copy=False)
        return single, many

    def _predict_single_window(self, frames: np.ndarray) -> float:
        if self._model is None or len(frames) == 0:
            return 0.0

        single_probs, many_probs = self._predict_probabilities(frames)
        if single_probs.size == 0:
            return 0.0

        combined = np.maximum(single_probs, many_probs)
        center_idx = len(combined) // 2
        return float(combined[center_idx])

    def _extract_peak_boundaries(self, probabilities: np.ndarray) -> Dict[int, float]:
        if probabilities.size == 0:
            return {}

        above = probabilities >= self.threshold
        boundaries: Dict[int, float] = {}
        idx = 0

        while idx < len(probabilities):
            if not above[idx]:
                idx += 1
                continue

            run_start = idx
            while idx + 1 < len(probabilities) and above[idx + 1]:
                idx += 1
            run_end = idx

            run = probabilities[run_start:run_end + 1]
            rel_peak = int(np.argmax(run))
            peak_idx = run_start + rel_peak
            peak_prob = float(probabilities[peak_idx])

            if boundaries:
                prev_idx = max(boundaries.keys())
                if peak_idx - prev_idx < self.tolerance_frames:
                    prev_prob = boundaries[prev_idx]
                    if peak_prob > prev_prob:
                        del boundaries[prev_idx]
                        boundaries[peak_idx] = peak_prob
                else:
                    boundaries[peak_idx] = peak_prob
            else:
                boundaries[peak_idx] = peak_prob

            idx += 1

        return boundaries

    def merge_with_pyscene(
        self,
        pyscene_scenes: List[Tuple[int, int]],
        video_path: str,
    ) -> List[Tuple[int, int]]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning("Cannot open video for merge: %s", video_path)
            return pyscene_scenes

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        cap.release()

        if fps <= 0:
            logger.warning("Invalid FPS %.3f, keep PySceneDetect results", fps)
            return pyscene_scenes

        # PyScene scenes: first scene starts at 0. Cut boundaries start from second scene start time.
        candidate_frames = [int(round(start_ms * fps / 1000.0)) for start_ms, _ in pyscene_scenes[1:]]
        boundaries = self.detect_boundaries(video_path, candidate_frames)
        if not boundaries:
            return pyscene_scenes

        confirmed = [pyscene_scenes[0]] if pyscene_scenes else []
        for scene in pyscene_scenes[1:]:
            start_ms, end_ms = scene
            start_frame = int(round(start_ms * fps / 1000.0))
            if self._is_boundary_confirmed(start_frame, boundaries):
                confirmed.append((start_ms, end_ms))

        logger.info("TransNetV2 merge done: kept %s/%s scenes", len(confirmed), len(pyscene_scenes))
        return confirmed or pyscene_scenes

    def _is_boundary_confirmed(self, target_frame: int, boundaries: Dict[int, float]) -> bool:
        for frame_idx in boundaries:
            if abs(frame_idx - target_frame) <= self.tolerance_frames:
                return True
        return False


def _download_to_path(url: str, output_path: Path, timeout: int = 60) -> bool:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "SmartCut/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()

    output_path.write_bytes(payload)
    return True


def download_model(output_dir: Optional[Path] = None, force: bool = False) -> Path:
    """Download TransNetV2 checkpoint if available from known URLs."""
    if output_dir is None:
        output_dir = TransNetV2Detector.DEFAULT_MODEL_DIR

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / TransNetV2Detector.DEFAULT_MODEL_NAME

    if model_path.exists() and not force:
        meta = checkpoint_metadata(str(model_path))
        size_bytes = int(meta.get("size_bytes") or 0)
        num_keys = int(meta.get("num_keys") or 0)
        if size_bytes >= TransNetV2Detector.MIN_MODEL_SIZE_BYTES and num_keys >= TransNetV2Detector.MIN_EXPECTED_STATE_KEYS:
            logger.info("Reusing existing TransNetV2 model: %s", model_path)
            return model_path
        logger.warning("Existing model appears invalid, re-downloading: %s", model_path)

    download_errors = []

    for name, url in TransNetV2Detector.MODEL_URLS.items():
        try:
            logger.info("Downloading TransNetV2 model from %s: %s", name, url)
            _download_to_path(url, model_path)
            meta = checkpoint_metadata(str(model_path))
            size_bytes = int(meta.get("size_bytes") or 0)
            num_keys = int(meta.get("num_keys") or 0)

            if size_bytes < TransNetV2Detector.MIN_MODEL_SIZE_BYTES or num_keys < TransNetV2Detector.MIN_EXPECTED_STATE_KEYS:
                model_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Downloaded file invalid (size={size_bytes}, keys={num_keys}). "
                    "Source may not host checkpoints anymore."
                )

            logger.info("Model downloaded successfully: %s", model_path)
            return model_path
        except Exception as exc:
            download_errors.append(f"{name}: {exc}")
            logger.warning("TransNetV2 model download failed from %s: %s", name, exc)

    raise RuntimeError(
        "TransNetV2 model download failed. "
        "Please place a valid converted checkpoint at "
        f"{model_path}. Details: {'; '.join(download_errors)}"
    )
