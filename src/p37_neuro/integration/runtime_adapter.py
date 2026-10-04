"""Composable adapter that applies robot.yaml v2 mappings to a raw robot transport."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec
from p37_neuro.integration.adapter import AdapterHealth
from p37_neuro.integration.kit import validate_robot_integration
from p37_neuro.integration.manifest import load_manifest_embodiment, load_robot_manifest
from p37_neuro.integration.mapping import (
    ControllerCommand,
    RawRobotObservation,
    RobotIOMapper,
)


@runtime_checkable
class RawRobotTransport(Protocol):
    """Minimal vendor-specific transport required by the mapped adapter."""

    def read_observation(self) -> RawRobotObservation:
        """Read one controller/vendor observation without P37 normalization."""
        ...

    def write_command(self, command: ControllerCommand) -> None:
        """Write one controller/vendor command."""
        ...

    def request_stop(self, reason: str) -> None:
        """Request the controller enter its safe-stop path."""
        ...

    def health(self) -> AdapterHealth:
        """Return transport/controller health."""
        ...


class MappedRobotAdapter:
    """Turn a raw vendor transport into the stable P37 RobotAdapter interface."""

    def __init__(
        self,
        manifest_path: str | Path,
        transport: RawRobotTransport,
    ) -> None:
        if not isinstance(transport, RawRobotTransport):
            raise TypeError("transport does not satisfy the P37 RawRobotTransport protocol")

        validate_robot_integration(manifest_path)
        manifest = load_robot_manifest(manifest_path)
        self._embodiment = load_manifest_embodiment(manifest, manifest_path=manifest_path)
        self._mapper = RobotIOMapper(manifest)
        self._transport = transport

    @property
    def embodiment(self) -> EmbodimentSpec:
        """Return the canonical embodiment loaded from the manifest."""
        return self._embodiment

    @property
    def mapper(self) -> RobotIOMapper:
        """Return the manifest-backed runtime mapper."""
        return self._mapper

    def read_observation(self) -> Observation:
        """Read raw vendor state and normalize it into P37 Observation."""
        return self._mapper.map_observation(self._transport.read_observation())

    def write_action(self, action: Action) -> None:
        """Map a canonical P37 action and send it to the vendor transport."""
        self._transport.write_command(self._mapper.map_action(action))

    def request_stop(self, reason: str) -> None:
        """Forward a safe-stop request to the vendor transport."""
        self._transport.request_stop(reason)

    def health(self) -> AdapterHealth:
        """Return underlying transport/controller health."""
        return self._transport.health()
