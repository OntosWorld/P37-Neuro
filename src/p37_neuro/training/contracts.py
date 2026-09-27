"""Framework-neutral training contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from p37_neuro.data.schema import Episode
from p37_neuro.embodiment.schema import EmbodimentSpec


@dataclass(frozen=True, slots=True)
class TrainMetrics:
    steps: int
    loss: float
    reward_mean: float
    success_rate: float


class Trainer(Protocol):
    """Minimal interface for supervised/RL training backends."""

    def train(
        self,
        episodes: tuple[Episode, ...],
        embodiments: tuple[EmbodimentSpec, ...],
    ) -> TrainMetrics: ...
