from scene_workbench.api import analyze_video
from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    ManifestSummary,
    ManifestSummaryCounts,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
    SuspiciousWindow,
    VideoSource,
)


def make_boundary(boundary_id: str, frame: int) -> BoundaryCandidate:
    return BoundaryCandidate(
        id=boundary_id,
        start_frame=frame,
        end_frame=frame,
        recommended_cut_frame=frame,
        boundary_type="hard_cut",
        confidence=0.6,
        review_state="unreviewed",
        detector_evidence=DetectorEvidence(
            pyscenedetect=PySceneDetectGroupEvidence(
                content=PySceneDetectEvidence(triggered=True)
            )
        ),
    )


def test_analyze_video_builds_manifest(monkeypatch):
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=240,
        duration_sec=10.0,
    )
    coarse = [make_boundary("c_0001", 24)]
    windows = [
        SuspiciousWindow(
            id="w_0001",
            start_frame=12,
            end_frame=36,
            reason="candidate_padding",
            source_boundary_ids=["c_0001"],
        )
    ]
    finals = [
        BoundaryCandidate(
            id="f_0001",
            start_frame=24,
            end_frame=24,
            recommended_cut_frame=24,
            boundary_type="hard_cut",
            confidence=0.6,
            review_state="unreviewed",
            detector_evidence=DetectorEvidence(
                pyscenedetect=PySceneDetectGroupEvidence(
                    content=PySceneDetectEvidence(triggered=True)
                )
            ),
            source_boundary_ids=["c_0001"],
        )
    ]

    monkeypatch.setattr("scene_workbench.api.load_video_source", lambda _path: video)
    monkeypatch.setattr("scene_workbench.api.run_pyscenedetect", lambda *_args: coarse)
    monkeypatch.setattr(
        "scene_workbench.api.build_suspicious_windows",
        lambda *_args: windows,
    )
    monkeypatch.setattr("scene_workbench.api.run_transnetv2", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("scene_workbench.api.fuse_boundaries", lambda *_args: finals)

    manifest = analyze_video("demo.mp4")

    assert manifest.version == "v1"
    assert manifest.video.path == "demo.mp4"
    assert manifest.coarse_boundaries == coarse
    assert manifest.suspicious_windows == windows
    assert manifest.final_boundaries == finals
    assert manifest.summary == ManifestSummary(
        counts=ManifestSummaryCounts(
            coarse_boundaries=1,
            suspicious_windows=1,
            refined_boundaries=0,
            final_boundaries=1,
            accepted=0,
            adjusted=0,
            merged=0,
            inserted=0,
            rejected=0,
        )
    )
