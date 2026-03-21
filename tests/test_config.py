from scene_workbench.config import WorkbenchConfig, coerce_config, default_config


def test_default_config_matches_spec_defaults():
    config = default_config()

    assert config.coarse_detection.detectors == ["content", "adaptive", "threshold"]
    assert config.coarse_detection.content_threshold == 27.0
    assert config.coarse_detection.adaptive_threshold == 3.0
    assert config.coarse_detection.min_scene_len == 12
    assert config.refinement.window_padding_frames == 12
    assert config.refinement.long_scene_threshold_frames == 240
    assert config.refinement.max_window_frames == 96
    assert config.fusion.merge_gap_frames == 6


def test_coerce_config_accepts_mapping():
    config = coerce_config({"review": {"autosave": False}})

    assert isinstance(config, WorkbenchConfig)
    assert config.review.autosave is False
