"""Quality-first manual tuning for scene segmentation."""

from __future__ import annotations

import json
import logging
import subprocess
from copy import deepcopy
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_QUALITY_CONFIG: dict[str, Any] = {
    "detector": "content",
    "scene_threshold": 27.0,
    "min_scene_len_frames": 15,
    "downscale": 1,
    "frame_skip": 0,
    "adaptive_threshold": 3.0,
    "adaptive_min_content_val": 15.0,
    "adaptive_frame_window": 2,
    "thumbnail_retry": 1,
    "weight_hue": 1.0,
    "weight_sat": 1.0,
    "weight_lum": 1.0,
    "weight_edges": 0.0,
    # TransNetV2 深度学习配置（当前默认关闭，优先稳定性）
    "detection_mode": "fast",
    "use_transnet": False,
    "transnet_threshold": 0.3,                # 概率阈值（0-1）
    "transnet_tolerance_frames": 12,          # 边界匹配容差（帧数）
    "transnet_window_size": 100,              # 分析窗口大小（帧数）
    "transnet_timeout_sec": 30,               # 模型加载超时
    "transnet_additional_boundary_threshold": 0.55,  # 补边阈值（0-1）
    "transnet_only_min_gap_frames": 12,       # 补边最小间隔（帧）
}


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _parse_ratio(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return 0.0

    left, right = value.split("/", 1)
    try:
        left_num = float(left)
        right_num = float(right)
    except ValueError:
        return 0.0

    if right_num == 0:
        return 0.0

    return left_num / right_num


def get_video_features(video_path: str) -> dict[str, Any]:
    """Read lightweight video metadata used for quality-focused tuning."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-print_format",
        "json",
        video_path,
    ]

    features = {
        "duration_sec": 0.0,
        "fps": 0.0,
        "width": 0,
        "height": 0,
        "bitrate": 0,
        "file_size_mb": 0.0,
        "pixel_rate": 0.0,
        "high_motion_proxy": False,
    }

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=12)
        payload = json.loads(result.stdout)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("ffprobe failed for quality tuning: %s", exc)
        return features

    streams = payload.get("streams") or []
    format_info = payload.get("format") or {}

    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video_stream:
        return features

    duration = float(format_info.get("duration") or video_stream.get("duration") or 0.0)
    fps = _parse_ratio(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    bitrate = int(format_info.get("bit_rate") or video_stream.get("bit_rate") or 0)
    file_size = int(format_info.get("size") or 0)

    pixel_rate = float(width * height) * fps if width and height and fps else 0.0
    bits_per_pixel_frame = 0.0
    if pixel_rate > 0:
        bits_per_pixel_frame = bitrate / pixel_rate

    # Heuristic: high fps + high bits-per-pixel tends to indicate frequent motion/content changes.
    high_motion_proxy = (fps >= 50.0 and bits_per_pixel_frame >= 0.08) or bits_per_pixel_frame >= 0.13

    features.update(
        {
            "duration_sec": round(duration, 3),
            "fps": round(fps, 3),
            "width": width,
            "height": height,
            "bitrate": bitrate,
            "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size else 0.0,
            "pixel_rate": round(pixel_rate, 3),
            "high_motion_proxy": high_motion_proxy,
        }
    )
    return features


def _sanitize_override(override_config: dict[str, Any] | None) -> dict[str, Any]:
    if not override_config:
        return {}

    allowed_keys = set(DEFAULT_QUALITY_CONFIG.keys())
    sanitized = {key: value for key, value in override_config.items() if key in allowed_keys and value is not None}
    return sanitized


def _normalize_quality_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(config)
    normalized["scene_threshold"] = round(_clamp(float(normalized.get("scene_threshold", 27.0)), 8.0, 60.0), 2)
    normalized["adaptive_threshold"] = round(
        _clamp(float(normalized.get("adaptive_threshold", 3.0)), 0.8, 8.0), 2
    )
    normalized["adaptive_min_content_val"] = round(
        _clamp(float(normalized.get("adaptive_min_content_val", 15.0)), 5.0, 60.0), 2
    )
    normalized["adaptive_frame_window"] = int(
        _clamp(float(normalized.get("adaptive_frame_window", 2)), 1.0, 8.0)
    )
    normalized["min_scene_len_frames"] = int(
        _clamp(float(normalized.get("min_scene_len_frames", 15)), 4.0, 300.0)
    )
    normalized["downscale"] = int(_clamp(float(normalized.get("downscale", 1)), 1.0, 8.0))
    normalized["frame_skip"] = int(_clamp(float(normalized.get("frame_skip", 0)), 0.0, 10.0))
    normalized["thumbnail_retry"] = int(_clamp(float(normalized.get("thumbnail_retry", 1)), 0.0, 3.0))
    normalized["weight_hue"] = round(_clamp(float(normalized.get("weight_hue", 1.0)), 0.0, 10.0), 3)
    normalized["weight_sat"] = round(_clamp(float(normalized.get("weight_sat", 1.0)), 0.0, 10.0), 3)
    normalized["weight_lum"] = round(_clamp(float(normalized.get("weight_lum", 1.0)), 0.0, 10.0), 3)
    normalized["weight_edges"] = round(_clamp(float(normalized.get("weight_edges", 0.0)), 0.0, 10.0), 3)
    normalized["detector"] = "adaptive" if normalized.get("detector") == "adaptive" else "content"
    normalized["detection_mode"] = "precision" if normalized.get("detection_mode") == "precision" else "fast"
    use_transnet = normalized.get("use_transnet")
    if normalized["detection_mode"] != "precision":
        normalized["use_transnet"] = False
    elif use_transnet is None:
        normalized["use_transnet"] = True
    else:
        normalized["use_transnet"] = bool(use_transnet)
    normalized["transnet_threshold"] = round(_clamp(float(normalized.get("transnet_threshold", 0.3)), 0.0, 1.0), 2)
    normalized["transnet_tolerance_frames"] = int(
        _clamp(float(normalized.get("transnet_tolerance_frames", 12)), 1, 100)
    )
    normalized["transnet_window_size"] = int(
        _clamp(float(normalized.get("transnet_window_size", 100)), 50, 400)
    )
    normalized["transnet_timeout_sec"] = int(
        _clamp(float(normalized.get("transnet_timeout_sec", 30)), 5, 300)
    )
    normalized["transnet_additional_boundary_threshold"] = round(
        _clamp(float(normalized.get("transnet_additional_boundary_threshold", 0.55)), 0.0, 1.0), 2
    )
    normalized["transnet_only_min_gap_frames"] = int(
        _clamp(float(normalized.get("transnet_only_min_gap_frames", 12)), 1, 300)
    )
    return normalized


def resolve_quality_config(
    *,
    video_path: str,
    mode: str = "manual",
    profile: str = "quality",
    override_config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build resolved processing config for a task."""
    features = get_video_features(video_path)
    base = deepcopy(DEFAULT_QUALITY_CONFIG)
    reasons: list[str] = ["manual mode selected"]
    if mode != "manual":
        raise ValueError("only manual mode is supported")

    override_payload = _sanitize_override(override_config)
    if override_payload:
        base.update(override_payload)
        reasons.append("override_config applied")

    base = _normalize_quality_config(base)
    if base.get("detection_mode") == "precision" and base.get("use_transnet"):
        reasons.append("precision mode enabled")
    else:
        reasons.append("fast mode enabled")
    reasons.append("quality auto-retry disabled")

    metadata = {
        "mode": mode,
        "profile": profile,
        "features": features,
        "reasons": reasons,
    }
    return base, metadata


def analyze_scene_quality(scenes: list[tuple[int, int]], duration_ms: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Analyze scene durations and mark suspicious segments for manual review."""
    scene_count = len(scenes)
    duration_ms = max(duration_ms, 1)
    duration_min = duration_ms / 60000.0

    if scene_count == 0:
        flags = {
            "over_segmented": False,
            "under_segmented": True,
            "unstable_boundary": False,
            "flash_false_cut": False,
            "shots_per_minute": 0.0,
            "short_shot_ratio": 0.0,
            "very_short_ratio": 0.0,
            "long_shot_ratio": 0.0,
        }
        return flags, []

    scene_durations = [max(1, end_ms - start_ms) for start_ms, end_ms in scenes]

    very_short_threshold_ms = 350
    short_threshold_ms = 800
    long_threshold_ms = 20000

    very_short_count = sum(1 for value in scene_durations if value <= very_short_threshold_ms)
    short_count = sum(1 for value in scene_durations if value <= short_threshold_ms)
    long_count = sum(1 for value in scene_durations if value >= long_threshold_ms)

    short_ratio = short_count / scene_count
    very_short_ratio = very_short_count / scene_count
    long_ratio = long_count / scene_count
    shots_per_minute = scene_count / max(duration_min, 0.01)

    over_segmented = short_ratio >= 0.35 or shots_per_minute >= 48
    under_segmented = (shots_per_minute <= 2.2 and duration_min >= 3.0) or long_ratio >= 0.55
    unstable_boundary = short_ratio >= 0.22 and scene_count >= 15
    flash_false_cut = very_short_ratio >= 0.12

    flags = {
        "over_segmented": over_segmented,
        "under_segmented": under_segmented,
        "unstable_boundary": unstable_boundary,
        "flash_false_cut": flash_false_cut,
        "shots_per_minute": round(shots_per_minute, 3),
        "short_shot_ratio": round(short_ratio, 4),
        "very_short_ratio": round(very_short_ratio, 4),
        "long_shot_ratio": round(long_ratio, 4),
        "scene_count": scene_count,
    }

    suspects: list[dict[str, Any]] = []
    for index, (start_ms, end_ms) in enumerate(scenes):
        length = max(1, end_ms - start_ms)

        if length <= very_short_threshold_ms:
            suspects.append(
                {
                    "sequence_index": index,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reason": "very_short_segment",
                    "confidence": 0.92,
                    "review_hint": "疑似闪白/噪声触发误切，建议与前后镜头对比。",
                }
            )
            continue

        if length <= short_threshold_ms:
            suspects.append(
                {
                    "sequence_index": index,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reason": "short_segment",
                    "confidence": 0.72,
                    "review_hint": "片段较短，建议确认是否应与前后镜头合并。",
                }
            )
        elif length >= long_threshold_ms:
            suspects.append(
                {
                    "sequence_index": index,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "reason": "long_segment",
                    "confidence": 0.68,
                    "review_hint": "片段较长，建议确认中间是否存在漏切边界。",
                }
            )

    return flags, suspects[:120]


def should_retry_quality(flags: dict[str, Any], attempt_index: int, max_retries: int = 2) -> bool:
    """Decide if quality loop should run another detection attempt."""
    if attempt_index >= max_retries:
        return False

    return bool(
        flags.get("over_segmented")
        or flags.get("under_segmented")
        or flags.get("flash_false_cut")
    )


def tune_config_for_next_attempt(config: dict[str, Any], flags: dict[str, Any]) -> dict[str, Any]:
    """Adjust config based on quality flags for next detection attempt."""
    next_config = deepcopy(config)

    if flags.get("over_segmented"):
        next_config["scene_threshold"] = round(
            _clamp(float(next_config.get("scene_threshold", 27.0)) + 2.0, 8.0, 60.0), 2
        )
        next_config["min_scene_len_frames"] = int(
            _clamp(float(next_config.get("min_scene_len_frames", 15)) + 6, 4.0, 300.0)
        )

    if flags.get("under_segmented"):
        next_config["scene_threshold"] = round(
            _clamp(float(next_config.get("scene_threshold", 27.0)) - 1.5, 8.0, 60.0), 2
        )
        next_config["detector"] = "adaptive"
        next_config["adaptive_threshold"] = round(
            _clamp(float(next_config.get("adaptive_threshold", 3.0)) - 0.4, 0.8, 8.0), 2
        )

    if flags.get("flash_false_cut"):
        next_config["detector"] = "adaptive"
        next_config["adaptive_min_content_val"] = round(
            _clamp(float(next_config.get("adaptive_min_content_val", 15.0)) + 2.5, 5.0, 60.0), 2
        )

    return next_config
