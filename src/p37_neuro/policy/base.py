"""Policy interfaces independent of model framework and robot vendor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec


@dataclass(frozen=True, slots=True)
class TaskContext:
    """Task information supplied to a high-level policy."""

    task_id: str
    instruction: str | None = None
    demonstration_refs: tuple[str, ...] = ()
    goal_refs: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HighLevelCommand:
    """Embodiment-light command connecting high-level and motor policies."""

    kind: str
    values: tuple[float, ...]
    frame: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


class HighLevelPolicy(Protocol):
    """Produces task-level physical intent."""

    def reset(self, embodiment: EmbodimentSpec, task: TaskContext) -> None:
        """Reset state for a new task episode."""

    def act(
        self,
        observation: Observation,
        history: Sequence[Observation],
    ) -> HighLevelCommand:
        """Produce the next high-level physical command."""
        ...


class LowLevelPolicy(Protocol):
    """Transforms physical intent into body-specific commands."""

    def reset(self, embodiment: EmbodimentSpec) -> None:
        """Reset state for a new embodiment/episode."""

    def act(
        self,
        command: HighLevelCommand,
        observation: Observation,
    ) -> Action:
        """Produce the next actuator-facing command."""
        ...
