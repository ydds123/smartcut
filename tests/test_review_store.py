from __future__ import annotations

from pathlib import Path

import pytest

from scene_workbench.review.store import ManifestStore, ManifestStoreError, load_manifest, save_manifest


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_load_manifest_reads_example() -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    assert manifest.manifest_id == "demo_shortfilm_v1_001"


def test_save_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = load_manifest(FIXTURES_DIR / "manifest.v1.example.json")
    output = tmp_path / "roundtrip.json"

    saved_path = save_manifest(output, manifest)
    reloaded = load_manifest(saved_path)

    assert reloaded == manifest


def test_manifest_store_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ManifestStoreError):
        ManifestStore(tmp_path / "missing.json").load()
