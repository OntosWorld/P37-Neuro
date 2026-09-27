"""Simulator adapter protocol."""

from __future__ import annotations

from typing import Protocol

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec


class SimulatorAdapter(Protocol):
    """Minimal contract implemented by Isaac Lab, MuJoCo and future backends."""

    @property
    def embodiment(self) -> EmbodimentSpec:
        """Return the embodiment currently loaded by the simulator."""
        ...

    def reset(self, seed: int) -> Observation:
        """Reset deterministically and return the first observation."""
        ...

    def step(self, action: Action) -> Observation:
        """Advance simulation by one control step."""
        ...

    def close(self) -> None:
        """Release simulator resources."""
        ...
