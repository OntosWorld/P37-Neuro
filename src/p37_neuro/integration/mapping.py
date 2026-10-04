"""Runtime translation between vendor/controller I/O and canonical P37 contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite

from p37_neuro.core.types import ControlMode
from p37_neuro.data.schema import Action, Observation
from p37_neuro.integration.manifest import (
    JointMapping,
    ObservationMapping,
    RobotIntegrationManifest,
)


class RobotMappingError(ValueError):
    """Raised when runtime robot I/O cannot satisfy the declared manifest contract."""


@dataclass(frozen=True, slots=True)
class RawRobotObservation:
    """Vendor/controller-side observation before normalization."""

    timestamp_s: float
    values: Mapping[str, float]
    sensor_refs: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isfinite(self.timestamp_s) or self.timestamp_s < 0:
            raise RobotMappingError("raw observation timestamp must be finite and non-negative")
        if any(not isfinite(value) for value in self.values.values()):
            raise RobotMappingError("raw observation values must be finite")


@dataclass(frozen=True, slots=True)
class ControllerCommand:
    """Controller-facing command after canonical P37 action mapping."""

    timestamp_s: float
    values: Mapping[str, float]


class RobotIOMapper:
    """Apply one validated robot manifest to runtime observations and actions.

    Joint command conversion uses:
        controller_value = canonical_value * scale + offset

    Joint state conversion uses the inverse:
        canonical_value = (controller_value - offset) / scale

    ObservationMapping conversion uses:
        canonical_value = source_value * scale + offset
    """

    def __init__(self, manifest: RobotIntegrationManifest) -> None:
        if manifest.schema_version != 2:
            raise RobotMappingError("runtime mapping requires robot manifest schema v2")
        self._manifest = manifest
        self._joints = {mapping.joint: mapping for mapping in manifest.joints}

    @property
    def manifest(self) -> RobotIntegrationManifest:
        return self._manifest

    def map_observation(self, raw: RawRobotObservation) -> Observation:
        """Normalize vendor/controller state into the canonical P37 Observation."""
        joint_position: dict[str, float] = {}
        for mapping in self._manifest.joints:
            if mapping.state not in raw.values:
                raise RobotMappingError(
                    f"missing required joint state source {mapping.state!r} "
                    f"for canonical joint {mapping.joint!r}"
                )
            joint_position[mapping.joint] = self._from_controller(
                raw.values[mapping.state],
                mapping,
            )

        joint_velocity: dict[str, float] = {}
        state: dict[str, float] = {}
        sensor_refs: dict[str, str] = {}

        for mapping in self._manifest.observation_mappings:
            self._map_declared_observation(
                mapping,
                raw=raw,
                joint_position=joint_position,
                joint_velocity=joint_velocity,
                state=state,
                sensor_refs=sensor_refs,
            )

        return Observation(
            timestamp_s=raw.timestamp_s,
            joint_position=joint_position,
            joint_velocity=joint_velocity,
            sensor_refs=sensor_refs,
            state=state,
        )

    def map_action(self, action: Action) -> ControllerCommand:
        """Translate a canonical P37 action into controller/vendor command values."""
        unknown = sorted(set(action.joint_commands) - set(self._joints))
        if unknown:
            raise RobotMappingError(
                "action contains unmapped canonical joints: " + ", ".join(unknown)
            )

        values: dict[str, float] = {}
        for joint_name, canonical_value in action.joint_commands.items():
            mapping = self._joints[joint_name]
            self._enforce_manifest_safety(mapping, canonical_value)
            controller_value = canonical_value * mapping.scale + mapping.offset
            if not isfinite(controller_value):
                raise RobotMappingError(
                    f"mapped controller command for joint {joint_name!r} is not finite"
                )
            values[mapping.command] = controller_value

        return ControllerCommand(timestamp_s=action.timestamp_s, values=values)

    @staticmethod
    def _from_controller(value: float, mapping: JointMapping) -> float:
        canonical = (value - mapping.offset) / mapping.scale
        if not isfinite(canonical):
            raise RobotMappingError(f"mapped observation for joint {mapping.joint!r} is not finite")
        return canonical

    @staticmethod
    def _map_declared_observation(
        mapping: ObservationMapping,
        *,
        raw: RawRobotObservation,
        joint_position: dict[str, float],
        joint_velocity: dict[str, float],
        state: dict[str, float],
        sensor_refs: dict[str, str],
    ) -> None:
        if mapping.source in raw.values:
            value = raw.values[mapping.source] * mapping.scale + mapping.offset
            if not isfinite(value):
                raise RobotMappingError(f"mapped observation {mapping.target!r} is not finite")
            if mapping.target.startswith("joint_position."):
                joint_position[mapping.target.removeprefix("joint_position.")] = value
            elif mapping.target.startswith("joint_velocity."):
                joint_velocity[mapping.target.removeprefix("joint_velocity.")] = value
            else:
                state[mapping.target] = value
            return

        if mapping.source in raw.sensor_refs:
            sensor_refs[mapping.target] = raw.sensor_refs[mapping.source]
            return

        if mapping.required:
            raise RobotMappingError(
                f"missing required observation source {mapping.source!r} "
                f"for target {mapping.target!r}"
            )

    @staticmethod
    def _enforce_manifest_safety(mapping: JointMapping, value: float) -> None:
        safety = mapping.safety
        if mapping.control_mode is ControlMode.POSITION:
            if safety.position_min is not None and value < safety.position_min:
                raise RobotMappingError(
                    f"joint {mapping.joint!r} command {value} is below manifest "
                    f"position_min {safety.position_min}"
                )
            if safety.position_max is not None and value > safety.position_max:
                raise RobotMappingError(
                    f"joint {mapping.joint!r} command {value} exceeds manifest "
                    f"position_max {safety.position_max}"
                )
        elif mapping.control_mode is ControlMode.VELOCITY:
            if safety.velocity_limit is not None and abs(value) > safety.velocity_limit:
                raise RobotMappingError(
                    f"joint {mapping.joint!r} velocity {value} exceeds manifest "
                    f"limit {safety.velocity_limit}"
                )
        elif mapping.control_mode is ControlMode.EFFORT:
            if safety.effort_limit is not None and abs(value) > safety.effort_limit:
                raise RobotMappingError(
                    f"joint {mapping.joint!r} effort {value} exceeds manifest "
                    f"limit {safety.effort_limit}"
                )
