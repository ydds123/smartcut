from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DetectorName = Literal["content", "adaptive", "threshold"]
ExportFormat = Literal["json", "cutlist", "edl", "ffmpeg"]


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoarseDetectionConfig(ConfigModel):
    detectors: list[DetectorName] = Field(
        default_factory=lambda: ["content", "adaptive", "threshold"]
    )
    content_threshold: float = 27.0
    adaptive_threshold: float = 3.0
    min_scene_len: int = 12


class RefinementConfig(ConfigModel):
    enabled: bool = True
    model: str = "transnetv2"
    window_padding_frames: int = 12
    long_scene_threshold_frames: int = 240
    max_window_frames: int = 96
    only_suspicious_windows: bool = True
    threshold: float = 0.5
    gradual_threshold: float = 0.3
    gradual_min_frames: int = 3
    device: str = "auto"


class FusionConfig(ConfigModel):
    merge_gap_frames: int = 6
    gradual_min_len_frames: int = 4
    hard_cut_max_len_frames: int = 1


class ReviewConfig(ConfigModel):
    autosave: bool = True


class ExportConfig(ConfigModel):
    accepted_only: bool = True
    default_formats: list[ExportFormat] = Field(
        default_factory=lambda: ["json", "edl", "ffmpeg"]
    )


class WorkbenchConfig(ConfigModel):
    coarse_detection: CoarseDetectionConfig = Field(
        default_factory=CoarseDetectionConfig
    )
    refinement: RefinementConfig = Field(default_factory=RefinementConfig)
    fusion: FusionConfig = Field(default_factory=FusionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

    def to_manifest_config(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


SceneWorkbenchConfig = WorkbenchConfig


def default_config() -> WorkbenchConfig:
    return WorkbenchConfig()


def coerce_config(
    config: WorkbenchConfig | Mapping[str, Any] | None,
) -> WorkbenchConfig:
    if config is None:
        return default_config()
    if isinstance(config, WorkbenchConfig):
        return config
    if isinstance(config, Mapping):
        return WorkbenchConfig.model_validate(dict(config))
    raise TypeError(f"Unsupported config type: {type(config)!r}")


def config_to_manifest_dict(
    config: WorkbenchConfig | Mapping[str, Any] | None,
) -> dict[str, Any]:
    return coerce_config(config).to_manifest_config()
