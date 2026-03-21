from scene_workbench.config import default_config
from scene_workbench.fusion.decision import fuse_boundaries
from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
    TransNetV2Evidence,
)


def make_coarse(boundary_id: str, frame: int, confidence: float = 0.6) -> BoundaryCandidate:
    return BoundaryCandidate(
        id=boundary_id,
        start_frame=frame,
        end_frame=frame,
        recommended_cut_frame=frame,
        boundary_type="hard_cut",
        confidence=confidence,
        review_state="unreviewed",
        detector_evidence=DetectorEvidence(
            pyscenedetect=PySceneDetectGroupEvidence(
                content=PySceneDetectEvidence(triggered=True)
            )
        ),
    )


def make_refined(
    boundary_id: str,
    start_frame: int,
    end_frame: int,
    boundary_type: str,
    confidence: float,
) -> BoundaryCandidate:
    return BoundaryCandidate(
        id=boundary_id,
        start_frame=start_frame,
        end_frame=end_frame,
        recommended_cut_frame=(start_frame + end_frame) // 2,
        boundary_type=boundary_type,  # type: ignore[arg-type]
        confidence=confidence,
        review_state="unreviewed",
        detector_evidence=DetectorEvidence(
            transnetv2=TransNetV2Evidence(
                triggered=True,
                score=confidence,
                window_id="w_0001",
            )
        ),
    )


def test_fuse_boundaries_prefers_refined_gradual_transition():
    coarse = [make_coarse("c_0001", 100, 0.55), make_coarse("c_0002", 104, 0.60)]
    refined = [make_refined("r_0001", 98, 110, "dissolve", 0.91)]

    finals = fuse_boundaries(coarse, refined, default_config())

    assert len(finals) == 1
    assert finals[0].boundary_type == "dissolve"
    assert finals[0].source_boundary_ids == ["c_0001", "c_0002", "r_0001"]
    assert finals[0].detector_evidence.transnetv2.score == 0.91


def test_fuse_boundaries_keeps_coarse_when_refinement_missing():
    coarse = [make_coarse("c_0001", 50, 0.60)]

    finals = fuse_boundaries(coarse, [], default_config())

    assert len(finals) == 1
    assert finals[0].boundary_type == "hard_cut"
    assert finals[0].source_boundary_ids == ["c_0001"]
