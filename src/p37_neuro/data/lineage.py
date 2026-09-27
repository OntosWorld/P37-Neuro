"""Immutable dataset lineage records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    dataset_id: str
    version: str
    sha256: str
    parent: str | None = None
    episode_count: int = 0

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.version.strip() or not self.sha256.strip():
            raise ValueError("dataset_id, version and sha256 are required")
        if self.episode_count < 0:
            raise ValueError("episode_count cannot be negative")
