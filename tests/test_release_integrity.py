from dataclasses import replace
from pathlib import Path

import pytest

from p37_neuro.deployment.release import ReleaseManifest, ReleaseSigner, verify_release
from p37_neuro.deployment.store import FilesystemArtifactStore, sha256_file


def test_content_addressed_store_is_immutable(tmp_path: Path) -> None:
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"model-bytes")
    store = FilesystemArtifactStore(tmp_path / "store")
    stored = store.put(artifact)

    assert stored.sha256 == sha256_file(artifact)
    assert store.resolve(stored.sha256).read_bytes() == b"model-bytes"

    same = store.put(artifact)
    assert same.path == stored.path


def test_signed_release_rejects_tampering() -> None:
    signer = ReleaseSigner.generate()
    manifest = ReleaseManifest(
        schema_version=1,
        artifact_id="p37-e1-001",
        artifact_sha256="a" * 64,
        config_id="cfg-1",
        dataset_id="ds-1",
        stage="E1",
        metrics={"heldout_success": 0.72},
    )
    release = signer.sign(manifest)
    verify_release(release, signer.public_key)

    tampered = replace(
        release,
        manifest=replace(release.manifest, dataset_id="ds-evil"),
    )
    with pytest.raises(ValueError, match="signature"):
        verify_release(tampered, signer.public_key)
