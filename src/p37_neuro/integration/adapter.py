"""Stable robot-adapter boundary for enterprise integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec


@dataclass(frozen=True, slots=True)
class AdapterHealth:
    """Health returned by a robot adapter without coupling P37 to a vendor SDK."""

    connected: bool
    state_fresh: bool
    controller_ready: bool
    estop_available: bool
    watchdog_available: bool
    detail: str = ""

    @property
    def ready(self) -> bool:
        return (
            self.connected
            and self.state_fresh
            and self.controller_ready
            and self.estop_available
            and self.watchdog_available
        )


@runtime_checkable
class RobotAdapter(Protocol):
    """Vendor-neutral interface between P37 and a concrete robot/controller."""

    @property
    def embodiment(self) -> EmbodimentSpec:
        """Return the canonical P37 embodiment controlled by this adapter."""

    def read_observation(self) -> Observation:
        """Return the latest normalized observation."""

    def write_action(self, action: Action) -> None:
        """Write one already-qualified action to the downstream controller."""

    def request_stop(self, reason: str) -> None:
        """Request the adapter/controller enter its configured safe-stop path."""

    def health(self) -> AdapterHealth:
        """Return adapter and controller readiness without causing actuation."""


def validate_adapter(adapter: RobotAdapter) -> AdapterHealth:
    """Validate static adapter invariants and return its current health."""
    if not isinstance(adapter, RobotAdapter):
        raise TypeError("adapter does not satisfy the P37 RobotAdapter protocol")
    if adapter.embodiment.action_dimension <= 0:
        raise ValueError("adapter embodiment has no controllable joints")
    health = adapter.health()
    if not health.connected:
        raise RuntimeError("robot adapter is not connected")
    return health
