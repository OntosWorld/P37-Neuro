"""Content-addressed artifact storage for release candidates."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ArtifactStore(Protocol):
    def put(self, path: str | Path) -> "StoredArtifact": ...

    def resolve(self, sha256: str) -> Path: ...


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    sha256: str
    path: Path
    size_bytes: int


class FilesystemArtifactStore:
    """Immutable local/object-mount store keyed by artifact digest."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, digest: str) -> Path:
        return self.root / digest[:2] / digest[2:4] / digest

    def put(self, path: str | Path) -> StoredArtifact:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = sha256_file(source)
        destination = self._target(digest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(destination) != digest:
                raise RuntimeError("artifact store digest collision")
        else:
            temporary = destination.with_suffix(".tmp")
            shutil.copyfile(source, temporary)
            temporary.replace(destination)
        return StoredArtifact(digest, destination, destination.stat().st_size)

    def resolve(self, sha256: str) -> Path:
        if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
            raise ValueError("sha256 must be a lowercase 64-character hex digest")
        path = self._target(sha256)
        if not path.is_file():
            raise FileNotFoundError(sha256)
        if sha256_file(path) != sha256:
            raise RuntimeError("stored artifact failed integrity verification")
        return path
