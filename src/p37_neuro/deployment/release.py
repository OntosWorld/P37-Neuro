"""Cryptographically signed P37 model release manifests."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def public_key_fingerprint(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Immutable facts that bind a model artifact to its training lineage."""

    schema_version: int
    artifact_id: str
    artifact_sha256: str
    config_id: str
    dataset_id: str
    stage: str
    metrics: dict[str, float]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported release manifest schema")
        for label, value in (
            ("artifact_id", self.artifact_id),
            ("artifact_sha256", self.artifact_sha256),
            ("config_id", self.config_id),
            ("dataset_id", self.dataset_id),
            ("stage", self.stage),
        ):
            if not value.strip():
                raise ValueError(f"{label} cannot be empty")
        if len(self.artifact_sha256) != 64:
            raise ValueError("artifact_sha256 must be a SHA-256 hex digest")

    def canonical_bytes(self) -> bytes:
        return _canonical_json(asdict(self))


@dataclass(frozen=True, slots=True)
class SignedRelease:
    manifest: ReleaseManifest
    signature_b64: str
    signer_fingerprint: str

    def to_json(self) -> str:
        return (
            json.dumps(
                {
                    "manifest": asdict(self.manifest),
                    "signature_b64": self.signature_b64,
                    "signer_fingerprint": self.signer_fingerprint,
                },
                indent=2,
                sort_keys=True,
            )
            + "\\n"
        )

    @classmethod
    def from_json(cls, text: str) -> SignedRelease:
        raw = json.loads(text)
        return cls(
            manifest=ReleaseManifest(**raw["manifest"]),
            signature_b64=str(raw["signature_b64"]),
            signer_fingerprint=str(raw["signer_fingerprint"]),
        )


class ReleaseSigner:
    """Ed25519 signer/verifier. Private keys are injected at release time."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self.private_key = private_key

    @classmethod
    def generate(cls) -> ReleaseSigner:
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_private_key_pem(
        cls,
        path: str | Path,
        password: bytes | None = None,
    ) -> ReleaseSigner:
        key = serialization.load_pem_private_key(Path(path).read_bytes(), password=password)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("release key must be Ed25519")
        return cls(key)

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self.private_key.public_key()

    def sign(self, manifest: ReleaseManifest) -> SignedRelease:
        signature = self.private_key.sign(manifest.canonical_bytes())
        return SignedRelease(
            manifest=manifest,
            signature_b64=base64.b64encode(signature).decode("ascii"),
            signer_fingerprint=public_key_fingerprint(self.public_key),
        )


def verify_release(release: SignedRelease, public_key: Ed25519PublicKey) -> None:
    """Verify signer identity and manifest signature or raise ValueError."""
    expected = public_key_fingerprint(public_key)
    if release.signer_fingerprint != expected:
        raise ValueError("release signer fingerprint mismatch")
    try:
        signature = base64.b64decode(release.signature_b64, validate=True)
        public_key.verify(signature, release.manifest.canonical_bytes())
    except Exception as exc:
        raise ValueError("release signature verification failed") from exc


def save_public_key(path: str | Path, key: Ed25519PublicKey) -> None:
    Path(path).write_bytes(
        key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def load_public_key(path: str | Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("release public key must be Ed25519")
    return key
