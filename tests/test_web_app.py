from __future__ import annotations

from pathlib import Path

import pytest

from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    PySceneDetectEvidence,
    PySceneDetectGroupEvidence,
)
from scene_workbench.review.store import load_manifest, save_manifest


fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from scene_workbench.web.app import create_review_app


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
                content=PySceneDetectEvidence(triggered=True, score=31.5)
            )
        ),
    )


def _make_review_manifest():
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    manifest.review_actions = []
    manifest.final_boundaries = [
        _make_boundary("f_0001", 24),
        _make_boundary("f_0002", 48),
        _make_boundary("f_0003", 72),
    ]
    return manifest


def test_review_app_serves_manifest_and_accept_action(tmp_path: Path) -> None:
    manifest = _make_review_manifest()
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)

    client = TestClient(create_review_app(manifest_path))

    manifest_response = client.get("/api/manifest")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["manifest_id"] == manifest.manifest_id
    assert manifest_response.json()["next_boundary_id"] == "f_0001"

    preview_response = client.get("/api/preview/f_0001")
    assert preview_response.status_code == 200
    assert preview_response.json()["boundary_id"] == "f_0001"

    action_response = client.post(
        "/api/actions",
        json={
            "action": "accept",
            "target_boundary_ids": ["f_0001"],
            "created_by": "tester",
            "payload": {},
        },
    )
    assert action_response.status_code == 200
    assert action_response.json()["final_boundaries"][0]["review_state"] == "accepted"
    assert action_response.json()["next_boundary_id"] == "f_0002"


def test_review_app_returns_400_for_invalid_review_action(tmp_path: Path) -> None:
    manifest = _make_review_manifest()
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)

    client = TestClient(create_review_app(manifest_path))

    response = client.post(
        "/api/actions",
        json={
            "action": "merge",
            "target_boundary_ids": ["f_0001"],
            "created_by": "tester",
            "payload": {},
        },
    )

    assert response.status_code == 400
    assert "requires at least 2 target boundaries" in response.json()["detail"]


def test_review_app_returns_422_for_invalid_payload_shape(tmp_path: Path) -> None:
    manifest = _make_review_manifest()
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)

    client = TestClient(create_review_app(manifest_path))

    response = client.post(
        "/api/actions",
        json={
            "action": "accept",
            "target_boundary_ids": ["f_0001"],
            "payload": {},
        },
    )

    assert response.status_code == 422


def test_review_index_exposes_all_minimum_actions(tmp_path: Path) -> None:
    manifest = _make_review_manifest()
    manifest_path = save_manifest(tmp_path / "manifest.json", manifest)

    client = TestClient(create_review_app(manifest_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "accept" in response.text
    assert "reject" in response.text
    assert "adjust" in response.text
    assert "merge" in response.text
    assert "insert" in response.text
    assert "target-boundary-ids" in response.text
