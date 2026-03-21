from __future__ import annotations

from pathlib import Path

from scene_workbench.models import ProjectManifest


class ManifestStoreError(RuntimeError):
    """Raised when manifest persistence fails."""


def load_manifest(path: str | Path) -> ProjectManifest:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise ManifestStoreError(f"Manifest file not found: {manifest_path}")
    if not manifest_path.is_file():
        raise ManifestStoreError(f"Manifest path is not a file: {manifest_path}")

    try:
        payload = manifest_path.read_text(encoding="utf-8-sig")
        return ProjectManifest.model_validate_json(payload)
    except Exception as exc:  # pragma: no cover - pydantic handles specifics
        raise ManifestStoreError(f"Failed to load manifest: {manifest_path}") from exc


def save_manifest(path: str | Path, manifest: ProjectManifest) -> Path:
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest_path


class ManifestStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> ProjectManifest:
        return load_manifest(self.path)

    def save(self, manifest: ProjectManifest) -> Path:
        return save_manifest(self.path, manifest)
