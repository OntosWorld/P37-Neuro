"""RL/self-improvement run manifests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PostTrainPlan:
    base_artifact_id: str
    environment: str
    algorithm: str
    steps: int
    seed: int
    checkpoint_interval: int

    def __post_init__(self) -> None:
        if not self.base_artifact_id.strip():
            raise ValueError("base_artifact_id cannot be empty")
        if self.steps <= 0 or self.checkpoint_interval <= 0:
            raise ValueError("training steps and checkpoint interval must be positive")
