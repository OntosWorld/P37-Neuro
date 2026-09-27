"""Embodiment-neutral manipulation commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec


@dataclass(frozen=True, slots=True)
class CartesianCommand:
    """Task-space command suitable for different robot bodies."""

    frame: str
    position_m: tuple[float, float, float]
    orientation_xyzw: tuple[float, float, float, float]
    gripper: float | None = None


class ActionProjector(Protocol):
    """Maps embodiment-neutral commands into robot-specific actions."""

    def project(
        self,
        command: CartesianCommand,
        observation: Observation,
        embodiment: EmbodimentSpec,
    ) -> Action:
        ...
