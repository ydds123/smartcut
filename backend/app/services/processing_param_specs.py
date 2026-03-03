"""Single source of truth for processing parameter defaults and constraints."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

PROCESSING_META_VERSION = "2026-02-23"

# UI section definitions (order-sensitive).
PROCESSING_FIELD_GROUPS: list[dict[str, str]] = [
    {
        "id": "sensitivity",
        "label": "切多 vs 切少",
        "description": "控制触发切点的核心灵敏度，直接决定切出多少镜头",
    },
    {
        "id": "min-scene",
        "label": "防碎片 / 最短镜头",
        "description": "合并过短的镜头，减少碎片化切分",
    },
    {
        "id": "stability",
        "label": "检测稳定性",
        "description": "降低噪点和闪烁对检测的干扰，同时影响速度",
    },
    {
        "id": "transnet",
        "label": "TransNet 精度复核",
        "description": "仅 Precision 模式下生效，二阶段精度提升",
    },
    {
        "id": "misc",
        "label": "其他",
        "description": "预览图和淡入淡出相关，不影响主要切分结果",
    },
]


# Each entry is keyed by backend snake_case config key.
# Required keys:
# - type: "enum" | "bool" | "int" | "float"
# - default
# - provenance: "pyscenedetect" | "smartcut"
# For numeric fields, optional min/max/step/precision and UI metadata are supported.
PROCESSING_PARAM_SPECS: dict[str, dict[str, Any]] = {
    "detector": {
        "type": "enum",
        "default": "content",
        "options": ["content", "adaptive"],
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect CLI detectors (detect-content/detect-adaptive)",
        "ui_visible": True,
    },
    "detection_mode": {
        "type": "enum",
        "default": "fast",
        "options": ["fast", "precision"],
        "provenance": "smartcut",
        "source_ref": "SmartCut precision pipeline switch (PySceneDetect + TransNet)",
        "ui_visible": True,
    },
    "use_transnet": {
        "type": "bool",
        "default": False,
        "provenance": "smartcut",
        "source_ref": "SmartCut TransNet stage toggle",
        "ui_visible": True,
    },
    "scene_threshold": {
        "type": "float",
        "default": 27.0,
        "min": 0.0,
        "max": 255.0,
        "step": 0.5,
        "precision": 2,
        "group": "sensitivity",
        "label": "切换灵敏度",
        "description": "数值越小切得越多，越大切得越少。大多数视频用默认值 27 即可。",
        "recommended_range": "24 - 32（叙事片常用 27 - 30）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['detect-content']['threshold']",
    },
    "min_scene_len_frames": {
        "type": "int",
        "default": 15,
        "min": 0,
        "step": 1,
        "group": "min-scene",
        "label": "最短镜头帧数",
        "description": "短于这个帧数的镜头会被合并掉。调大可减少碎片化切分，调小可保留快速切换。",
        "recommended_range": "10 - 30（当前默认 15）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect detect-* --min-scene-len (TimecodeValue, non-negative)",
    },
    "min_scene_duration_ms_floor": {
        "type": "int",
        "default": 1000,
        "min": 0,
        "max": 10000,
        "step": 50,
        "group": "min-scene",
        "label": "最短镜头时长(ms)",
        "description": "短于这个时长（毫秒）的镜头会被合并。1000 = 1 秒，调大可减少碎片镜头。",
        "recommended_range": "600 - 1200（默认 1000）",
        "provenance": "smartcut",
        "source_ref": "SmartCut post-merge duration floor",
    },
    "downscale": {
        "type": "int",
        "default": 0,
        "min": 0,
        "step": 1,
        "group": "stability",
        "label": "降采样倍数",
        "description": "0 为 Auto；1 为不降采样；2 以上会缩小画面后再检测。",
        "recommended_range": "0（Auto）或 1 - 2",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect global.downscale (0=auto, explicit value must be >=1)",
    },
    "frame_skip": {
        "type": "int",
        "default": 0,
        "min": 0,
        "step": 1,
        "group": "stability",
        "label": "跳帧数",
        "description": "每隔几帧检测一次。0 = 逐帧最精准；更大值更快但会提高漏切风险。",
        "recommended_range": "0 - 1（质量优先建议 0）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['global']['frame-skip']",
    },
    "adaptive_threshold": {
        "type": "float",
        "default": 3.0,
        "min": 0.0,
        "max": 255.0,
        "step": 0.1,
        "precision": 2,
        "group": "sensitivity",
        "label": "自适应判定阈值",
        "description": "Adaptive 检测器的核心灵敏度。越小越容易触发切点，越大越保守。",
        "recommended_range": "2.2 - 3.8（默认 3.0）",
        "detector_scope": "adaptive",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['detect-adaptive']['threshold']",
    },
    "adaptive_min_content_val": {
        "type": "float",
        "default": 15.0,
        "min": 0.0,
        "max": 255.0,
        "step": 0.5,
        "precision": 2,
        "group": "sensitivity",
        "label": "自适应最小变化量",
        "description": "忽略小于此值的变化，可减少闪烁和噪点造成的误切。",
        "recommended_range": "12 - 20（默认 15）",
        "detector_scope": "adaptive",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['detect-adaptive']['min-content-val']",
    },
    "adaptive_frame_window": {
        "type": "int",
        "default": 2,
        "min": 1,
        "step": 1,
        "group": "stability",
        "label": "自适应平滑窗口",
        "description": "平滑计算的帧范围。越大边界越稳定，越小对瞬时变化越灵敏。",
        "recommended_range": "2 - 4（默认 2）",
        "detector_scope": "adaptive",
        "provenance": "pyscenedetect",
        "source_ref": "AdaptiveDetector.window_width >= 1 (detectors/adaptive_detector.py)",
    },
    "thumbnail_retry": {
        "type": "int",
        "default": 1,
        "min": 0,
        "max": 5,
        "step": 1,
        "group": "misc",
        "label": "缩略图重试次数",
        "description": "缩略图生成失败时的重试次数，不影响切分边界，仅影响预览完整性。",
        "recommended_range": "0 - 1（若不依赖缩略图可设 0）",
        "provenance": "smartcut",
        "source_ref": "SmartCut thumbnail generation retry budget",
    },
    "weight_hue": {
        "type": "float",
        "default": 1.0,
        "step": 0.1,
        "precision": 3,
        "group": "sensitivity",
        "label": "色相权重(H)",
        "description": "Content 检测中色相变化的权重。值越大越重视色相变化。",
        "recommended_range": "0.5 - 2.0（默认 1.0）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect detect-content --weights (delta_hue)",
        "detector_scope": "content",
        "ui_visible": True,
    },
    "weight_sat": {
        "type": "float",
        "default": 1.0,
        "step": 0.1,
        "precision": 3,
        "group": "sensitivity",
        "label": "饱和度权重(S)",
        "description": "Content 检测中饱和度变化的权重。值越大越重视颜色饱和度变化。",
        "recommended_range": "0.5 - 2.0（默认 1.0）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect detect-content --weights (delta_sat)",
        "detector_scope": "content",
        "ui_visible": True,
    },
    "weight_lum": {
        "type": "float",
        "default": 1.0,
        "step": 0.1,
        "precision": 3,
        "group": "sensitivity",
        "label": "亮度权重(L)",
        "description": "Content 检测中亮度变化的权重。值越大越重视明暗变化。",
        "recommended_range": "0.5 - 2.5（默认 1.0）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect detect-content --weights (delta_lum)",
        "detector_scope": "content",
        "ui_visible": True,
    },
    "weight_edges": {
        "type": "float",
        "default": 0.0,
        "step": 0.1,
        "precision": 3,
        "group": "sensitivity",
        "label": "边缘权重(E)",
        "description": "Content 检测中边缘变化的权重。常用于强化镜头结构变化。",
        "recommended_range": "0.0 - 1.0（默认 0.0）",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect detect-content --weights (delta_edges)",
        "detector_scope": "content",
        "ui_visible": True,
    },
    "transnet_threshold": {
        "type": "float",
        "default": 0.3,
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "precision": 2,
        "group": "transnet",
        "label": "TransNet 确认阈值",
        "description": "TransNetV2 确认切点的最低置信度。越小保留越多边界，越大越严格。",
        "recommended_range": "0.30 - 0.45（默认 0.30）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "SmartCut TransNet post-filter threshold",
    },
    "transnet_soft_candidate_multiplier": {
        "type": "float",
        "default": 0.75,
        "min": 0.5,
        "max": 1.0,
        "step": 0.01,
        "precision": 2,
        "group": "transnet",
        "label": "TransNet 软保留倍率",
        "description": "候选切点软保留倍率。越小保留越多候选，越大越严格。",
        "recommended_range": "0.65 - 0.85（默认 0.75）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "SmartCut candidate soft-retain multiplier",
    },
    "transnet_tolerance_frames": {
        "type": "int",
        "default": 12,
        "min": 1,
        "max": 300,
        "step": 1,
        "group": "transnet",
        "label": "TransNet 匹配容差(帧)",
        "description": "候选切点与 TransNet 峰值匹配容差。越大越宽松，越小越严格。",
        "recommended_range": "8 - 16（默认 12）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "SmartCut TransNet boundary matching tolerance",
    },
    "transnet_window_size": {
        "type": "int",
        "default": 100,
        "min": 20,
        "max": 400,
        "step": 2,
        "group": "transnet",
        "label": "TransNet 滑动窗口(帧)",
        "description": "TransNetV2 每次分析窗口大小。越大上下文越充分，越小越灵敏。",
        "recommended_range": "80 - 140（默认 100）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "TransNetV2Detector.window_size (>=20, normalized to even)",
    },
    "transnet_additional_boundary_threshold": {
        "type": "float",
        "default": 0.55,
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "precision": 2,
        "group": "transnet",
        "label": "TransNet 补边阈值",
        "description": "新增补充切点所需最低置信度。越小补得越多，越大越保守。",
        "recommended_range": "0.50 - 0.70（默认 0.55）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "SmartCut additional boundary threshold",
    },
    "transnet_only_min_gap_frames": {
        "type": "int",
        "default": 12,
        "min": 1,
        "max": 300,
        "step": 1,
        "group": "transnet",
        "label": "TransNet 最小间隔(帧)",
        "description": "补充切点与已有切点最小间隔，避免切点过密。",
        "recommended_range": "10 - 20（默认 12）",
        "mode_scope": "precision",
        "bool_scope": "use_transnet",
        "provenance": "smartcut",
        "source_ref": "SmartCut additional boundary min-gap filter",
    },
    "use_threshold_detector": {
        "type": "bool",
        "default": False,
        "provenance": "smartcut",
        "source_ref": "SmartCut optional detect-threshold stage",
        "ui_visible": True,
    },
    "threshold_detector_threshold": {
        "type": "float",
        "default": 12.0,
        "min": 0.0,
        "max": 255.0,
        "step": 1.0,
        "precision": 2,
        "group": "misc",
        "label": "淡出亮度阈值",
        "description": "判定淡入淡出的亮度门槛。越小越容易触发，越大只捕捉明显淡变。",
        "recommended_range": "8 - 20（默认 12）",
        "bool_scope": "use_threshold_detector",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['detect-threshold']['threshold']",
    },
    "threshold_detector_fade_bias": {
        "type": "float",
        "default": 0.0,
        "min": -100.0,
        "max": 100.0,
        "step": 1.0,
        "precision": 2,
        "group": "misc",
        "label": "淡入淡出位置偏移(%)",
        "description": "切点在过渡区间中的偏移百分比。-100 更靠前，+100 更靠后。",
        "recommended_range": "-20 - 20（默认 0）",
        "bool_scope": "use_threshold_detector",
        "provenance": "pyscenedetect",
        "source_ref": "scenedetect/_cli/config.py CONFIG_MAP['detect-threshold']['fade-bias']",
    },
    "merge_gap_frames": {
        "type": "int",
        "default": 0,
        "min": 0,
        "max": 600,
        "step": 1,
        "group": "min-scene",
        "label": "合并碎镜头间隔(帧)",
        "description": "相邻切点间隔小于该帧数时自动合并。0 表示不启用。",
        "recommended_range": "0（不启用）或 3 - 8",
        "provenance": "smartcut",
        "source_ref": "SmartCut post-processing gap merge",
    },
    "split_copy_mode": {
        "type": "bool",
        "default": False,
        "provenance": "smartcut",
        "source_ref": "SmartCut split strategy (copy vs re-encode)",
        "ui_visible": True,
    },
    "scenedetect_timeout_sec": {
        "type": "int",
        "default": 600,
        "min": 30,
        "max": 3600,
        "step": 30,
        "group": "misc",
        "label": "检测超时(秒)",
        "description": "PySceneDetect 命令最长执行时长，超时后会回退并保障任务可完成。",
        "recommended_range": "300 - 900（默认 600）",
        "provenance": "smartcut",
        "source_ref": "SmartCut subprocess timeout guard",
    },
}

_TRUE_STRINGS = {"1", "true", "t", "yes", "y", "on"}
_FALSE_STRINGS = {"0", "false", "f", "no", "n", "off"}


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
    return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _clamp_numeric(value: float, lower: float | int | None, upper: float | int | None) -> float:
    if lower is not None:
        value = max(float(lower), value)
    if upper is not None:
        value = min(float(upper), value)
    return value


def _normalize_enum(value: Any, default: str, options: list[str]) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in options:
            return candidate
    return default


def _normalize_numeric(raw_value: Any, spec: dict[str, Any]) -> int | float:
    kind = spec["type"]
    default = spec["default"]
    value = _coerce_float(raw_value, float(default))
    value = _clamp_numeric(value, spec.get("min"), spec.get("max"))
    if kind == "int":
        return int(value)
    precision = spec.get("precision")
    if isinstance(precision, int):
        return round(float(value), precision)
    return float(value)


def build_default_quality_config() -> dict[str, Any]:
    """Build defaults from the spec map."""
    return {key: deepcopy(spec["default"]) for key, spec in PROCESSING_PARAM_SPECS.items()}


def normalize_processing_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize arbitrary config payload using central parameter specs."""
    normalized: dict[str, Any] = {}
    for key, spec in PROCESSING_PARAM_SPECS.items():
        raw_value = config.get(key, spec["default"])
        kind = spec["type"]
        if kind == "bool":
            normalized[key] = _coerce_bool(raw_value, bool(spec["default"]))
        elif kind == "enum":
            normalized[key] = _normalize_enum(raw_value, str(spec["default"]), list(spec["options"]))
        else:
            normalized[key] = _normalize_numeric(raw_value, spec)

    # Preserve existing behavior:
    # - Fast mode always disables TransNet.
    # - Precision mode enables TransNet by default unless explicitly provided.
    if normalized["detection_mode"] != "precision":
        normalized["use_transnet"] = False
    elif "use_transnet" not in config or config.get("use_transnet") is None:
        normalized["use_transnet"] = True

    return normalized


def build_processing_config_meta() -> dict[str, Any]:
    """Return API payload consumed by the frontend config panel."""
    fields: list[dict[str, Any]] = []
    for key, spec in PROCESSING_PARAM_SPECS.items():
        payload = {
            "key": key,
            "type": spec["type"],
            "default": deepcopy(spec["default"]),
            "provenance": spec["provenance"],
            "source_ref": spec.get("source_ref"),
            "ui_visible": bool(spec.get("ui_visible", True)),
        }
        if "options" in spec:
            payload["options"] = list(spec["options"])
        if spec["type"] in {"int", "float"}:
            payload["min"] = spec.get("min")
            payload["max"] = spec.get("max")
            payload["step"] = spec.get("step")
            payload["group"] = spec.get("group")
            payload["label"] = spec.get("label")
            payload["description"] = spec.get("description")
            payload["detector_scope"] = spec.get("detector_scope")
            payload["mode_scope"] = spec.get("mode_scope")
            payload["bool_scope"] = spec.get("bool_scope")
        elif spec["type"] in {"bool", "enum"}:
            payload["group"] = spec.get("group")
            payload["label"] = spec.get("label")
            payload["description"] = spec.get("description")
            payload["detector_scope"] = spec.get("detector_scope")
            payload["mode_scope"] = spec.get("mode_scope")
            payload["bool_scope"] = spec.get("bool_scope")
        fields.append(payload)

    return {
        "version": PROCESSING_META_VERSION,
        "groups": deepcopy(PROCESSING_FIELD_GROUPS),
        "defaults": build_default_quality_config(),
        "fields": fields,
    }
