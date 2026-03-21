import warnings

import numpy as np

from scene_workbench.config import default_config
from scene_workbench.detectors.transnetv2_runner import (
    TransNetPrediction,
    _extract_transnet_predictions,
    run_transnetv2,
)
from scene_workbench.models import SuspiciousWindow, VideoSource


def test_run_transnetv2_returns_predictions_from_predictor():
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=300,
        duration_sec=12.5,
    )
    windows = [
        SuspiciousWindow(
            id="w_0001",
            start_frame=90,
            end_frame=110,
            reason="gradual_suspect",
            source_boundary_ids=["c_0001"],
        )
    ]

    def predictor(_video, _window, _config):
        return [
            TransNetPrediction(
                start_frame=94,
                end_frame=108,
                boundary_type="dissolve",
                score=0.92,
            )
        ]

    refined = run_transnetv2(video, windows, default_config(), predictor=predictor)

    assert len(refined) == 1
    assert refined[0].id == "r_0001_01"
    assert refined[0].boundary_type == "dissolve"
    assert refined[0].source_boundary_ids == ["c_0001"]


def test_run_transnetv2_warns_and_degrades_without_backend(monkeypatch):
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=300,
        duration_sec=12.5,
    )
    windows = [
        SuspiciousWindow(
            id="w_0001",
            start_frame=90,
            end_frame=110,
            reason="candidate_padding",
            source_boundary_ids=[],
        )
    ]

    monkeypatch.setattr(
        "scene_workbench.detectors.transnetv2_runner._build_transnet_predictor",
        lambda _config: (_ for _ in ()).throw(RuntimeError("backend unavailable")),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        refined = run_transnetv2(video, windows, default_config())

    assert refined == []
    assert caught


def test_extract_transnet_predictions_maps_gradual_and_hard_cut():
    config = default_config()
    window = SuspiciousWindow(
        id="w_0001",
        start_frame=100,
        end_frame=110,
        reason="gradual_suspect",
        source_boundary_ids=["c_0001"],
    )
    single = np.array([0.01, 0.02, 0.92, 0.01, 0.02, 0.01, 0.75, 0.01, 0.01, 0.01, 0.01])
    many = np.array([0.01, 0.05, 0.10, 0.35, 0.62, 0.71, 0.66, 0.21, 0.01, 0.01, 0.01])

    predictions = _extract_transnet_predictions(window, single, many, config)

    assert len(predictions) == 2
    assert predictions[0].boundary_type == "hard_cut"
    assert predictions[0].start_frame == 102
    assert predictions[1].boundary_type == "dissolve"
    assert predictions[1].start_frame == 103
    assert predictions[1].end_frame == 106
