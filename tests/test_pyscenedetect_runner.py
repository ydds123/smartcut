from scene_workbench.config import default_config
from scene_workbench.detectors.pyscenedetect_runner import DetectorHit, run_pyscenedetect
from scene_workbench.models import VideoSource


def test_run_pyscenedetect_merges_detector_hits(monkeypatch):
    video = VideoSource(
        path="demo.mp4",
        fps=24.0,
        width=1920,
        height=1080,
        total_frames=300,
        duration_sec=12.5,
    )

    def fake_collect(_video, _config):
        return {
            "content": [DetectorHit(frame=10), DetectorHit(frame=40)],
            "adaptive": [DetectorHit(frame=10)],
            "threshold": [DetectorHit(frame=80)],
        }

    monkeypatch.setattr(
        "scene_workbench.detectors.pyscenedetect_runner._collect_detector_hits",
        fake_collect,
    )

    boundaries = run_pyscenedetect(video, default_config())

    assert [boundary.id for boundary in boundaries] == ["c_0001", "c_0002", "c_0003"]
    assert boundaries[0].confidence == 0.60
    assert boundaries[0].detector_evidence.pyscenedetect.content.triggered is True
    assert boundaries[0].detector_evidence.pyscenedetect.adaptive.triggered is True
    assert boundaries[2].boundary_type == "unknown"
    assert boundaries[2].confidence == 0.65

