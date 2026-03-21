from scene_workbench.config import default_config
from scene_workbench.detectors.suspicious_windows import build_suspicious_windows
from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
    VideoSource,
)


def make_candidate(
    boundary_id: str,
    frame: int,
    confidence: float,
    *,
    threshold_triggered: bool = False,
) -> BoundaryCandidate:
    return BoundaryCandidate(
        id=boundary_id,
        start_frame=frame,
        end_frame=frame,
        recommended_cut_frame=frame,
        boundary_type="unknown" if threshold_triggered else "hard_cut",
        confidence=confidence,
        review_state="unreviewed",
        detector_evidence=DetectorEvidence(
            pyscenedetect=PySceneDetectGroupEvidence(
                content=PySceneDetectEvidence(triggered=not threshold_triggered),
                adaptive=PySceneDetectEvidence(triggered=False),
                threshold=PySceneDetectEvidence(triggered=threshold_triggered),
            )
        ),
    )


def test_build_suspicious_windows_merges_related_reasons():
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=500,
        duration_sec=20.8,
    )
    config = default_config()
    coarse = [
        make_candidate("c_0001", 100, 0.60, threshold_triggered=True),
        make_candidate("c_0002", 350, 0.80, threshold_triggered=False),
    ]

    windows = build_suspicious_windows(video, coarse, config)

    assert windows[0].id == "w_0001"
    assert "candidate_padding" in windows[0].reason
    assert "gradual_suspect" in windows[0].reason
    assert "low_confidence" in windows[0].reason
    assert windows[0].source_boundary_ids == ["c_0001"]
    assert any("long_scene" in window.reason for window in windows)
