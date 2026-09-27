"""Filesystem-backed experiment and model registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """Immutable model/checkpoint registration record."""

    artifact_id: str
    stage: str
    path: str
    sha256: str
    config_id: str
    dataset_id: str
    metrics: dict[str, float]


class ArtifactRegistry:
    """Append-only registry suitable for local research and CI."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / "registry.jsonl"

    def register(self, record: ArtifactRecord) -> None:
        existing = {item.artifact_id for item in self.list()}
        if record.artifact_id in existing:
            raise ValueError(f"artifact already registered: {record.artifact_id}")
        with self.index.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def list(self) -> tuple[ArtifactRecord, ...]:
        if not self.index.exists():
            return ()
        return tuple(
            ArtifactRecord(**json.loads(line))
            for line in self.index.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
