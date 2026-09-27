"""Canonical learning episode contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping, Sequence

from p37_neuro.core.types import Seconds


@dataclass(frozen=True, slots=True)
class Observation:
    """Normalized state presented to a policy at one instant."""

    timestamp_s: Seconds
    joint_position: Mapping[str, float]
    joint_velocity: Mapping[str, float]
    sensor_refs: Mapping[str, str] = field(default_factory=dict)
    state: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isfinite(self.timestamp_s) or self.timestamp_s < 0:
            raise ValueError("timestamp_s must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class Action:
    """Normalized action emitted by a policy."""

    timestamp_s: Seconds
    joint_commands: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isfinite(self.timestamp_s) or self.timestamp_s < 0:
            raise ValueError("timestamp_s must be finite and non-negative")
        if any(not isfinite(value) for value in self.joint_commands.values()):
            raise ValueError("joint commands must be finite")


@dataclass(frozen=True, slots=True)
class EpisodeStep:
    """One observation/action transition."""

    observation: Observation
    action: Action
    reward: float | None = None
    terminal: bool = False
    failure_code: str | None = None
    intervention: bool = False


@dataclass(frozen=True, slots=True)
class Episode:
    """A complete learning trajectory with provenance."""

    episode_id: str
    embodiment_id: str
    task_id: str
    steps: Sequence[EpisodeStep]
    source: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.episode_id.strip():
            raise ValueError("episode_id cannot be empty")
        if not self.embodiment_id.strip():
            raise ValueError("embodiment_id cannot be empty")
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        if not self.source.strip():
            raise ValueError("episode source cannot be empty")
        if not self.steps:
            raise ValueError("episode must contain at least one step")
