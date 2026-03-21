from __future__ import annotations

from pathlib import Path

from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
    ReviewActionCommand,
    ReviewActionPayload,
)
from scene_workbench.review.actions import apply_review_action
from scene_workbench.review.store import load_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def _make_boundary(boundary_id: str, frame: int) -> BoundaryCandidate:
    return BoundaryCandidate(
        id=boundary_id,
        start_frame=frame,
        end_frame=frame,
        recommended_cut_frame=frame,
        boundary_type="hard_cut",
        confidence=0.8,
        review_state="unreviewed",
        detector_evidence=DetectorEvidence(
            pyscenedetect=PySceneDetectGroupEvidence(
                content=PySceneDetectEvidence(triggered=True, score=30.0)
            )
        ),
    )


def _load_example_manifest():
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    manifest.review_actions = []
    manifest.final_boundaries = [
        _make_boundary("f_0001", 248),
        _make_boundary("f_0002", 982),
        _make_boundary("f_0003", 1438),
    ]
    return manifest


def test_apply_accept_marks_boundary_reviewed() -> None:
    manifest = _load_example_manifest()

    next_manifest = apply_review_action(
        manifest,
        ReviewActionCommand(
            action="accept",
            target_boundary_ids=["f_0001"],
            created_by="tester",
            payload=ReviewActionPayload(),
        ),
    )

    assert next_manifest.final_boundaries[0].review_state == "accepted"
    assert next_manifest.review_actions[-1].action == "accept"


def test_apply_reject_removes_boundary_and_counts_rejected() -> None:
    manifest = _load_example_manifest()

    next_manifest = apply_review_action(
        manifest,
        {
            "action": "reject",
            "target_boundary_ids": ["f_0001"],
            "created_by": "tester",
            "payload": {"reason": "false positive"},
        },
    )

    assert all(item.id != "f_0001" for item in next_manifest.final_boundaries)
    assert next_manifest.summary is not None
    assert next_manifest.summary.counts.rejected == 1


def test_apply_merge_creates_new_boundary() -> None:
    manifest = _load_example_manifest()
    manifest.final_boundaries = manifest.final_boundaries[:2]

    next_manifest = apply_review_action(
        manifest,
        {
            "action": "merge",
            "target_boundary_ids": ["f_0001", "f_0002"],
            "created_by": "tester",
            "payload": {
                "merged_start_frame": 248,
                "merged_end_frame": 982,
                "merged_recommended_cut_frame": 600,
                "merged_boundary_type": "dissolve",
                "reason": "merge test",
            },
        },
    )

    assert len(next_manifest.final_boundaries) == 1
    assert next_manifest.final_boundaries[0].review_state == "merged"
    assert "f_0001" in next_manifest.final_boundaries[0].source_boundary_ids


def test_apply_insert_appends_boundary() -> None:
    manifest = _load_example_manifest()

    next_manifest = apply_review_action(
        manifest,
        {
            "action": "insert",
            "target_boundary_ids": [],
            "created_by": "tester",
            "payload": {
                "start_frame": 4000,
                "end_frame": 4000,
                "recommended_cut_frame": 4000,
                "boundary_type": "hard_cut",
                "reason": "manual insert",
            },
        },
    )

    assert any(item.start_frame == 4000 for item in next_manifest.final_boundaries)
    assert next_manifest.final_boundaries[-1].review_state == "inserted"
