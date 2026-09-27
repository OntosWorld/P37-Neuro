"""Deterministic safety filters for actuator-facing commands."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from p37_neuro.core.types import ControlMode
from p37_neuro.data.schema import Action
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


class UnsafeCommandError(ValueError):
    """Raised when an action cannot be made safe without hiding a fault."""


@dataclass(frozen=True, slots=True)
class SafetyResult:
    """Result of deterministic command validation."""

    action: Action
    clamped_joints: tuple[str, ...]


class JointSafetyEnvelope:
    """Validate and clamp commands against declared embodiment limits.

    Position commands may be clamped to a declared joint range. Velocity and
    effort commands are rejected when they exceed their magnitude limit; silently
    scaling them could hide an unstable controller.
    """

    def apply(self, action: Action, embodiment: EmbodimentSpec) -> SafetyResult:
        """Return a safe action or fail closed for invalid command semantics."""
        expected = {joint.name for joint in embodiment.joints}
        received = set(action.joint_commands)
        unknown = received - expected
        if unknown:
            raise UnsafeCommandError(f"command contains unknown joints: {sorted(unknown)}")

        safe: dict[str, float] = {}
        clamped: list[str] = []

        for name, value in action.joint_commands.items():
            if not isfinite(value):
                raise UnsafeCommandError(f"joint {name!r} command must be finite")
            joint = embodiment.joint(name)
            safe_value, was_clamped = self._validate_joint(joint, value)
            safe[name] = safe_value
            if was_clamped:
                clamped.append(name)

        return SafetyResult(
            action=Action(timestamp_s=action.timestamp_s, joint_commands=safe),
            clamped_joints=tuple(clamped),
        )

    @staticmethod
    def _validate_joint(joint: JointSpec, value: float) -> tuple[float, bool]:
        if joint.control_mode is ControlMode.POSITION:
            if joint.position is None:
                raise UnsafeCommandError(
                    f"position-controlled joint {joint.name!r} has no position limit"
                )
            safe = joint.position.clamp(value)
            return safe, safe != value

        if joint.control_mode is ControlMode.VELOCITY:
            limit = joint.velocity_limit
            if limit is None:
                raise UnsafeCommandError(
                    f"velocity-controlled joint {joint.name!r} has no velocity limit"
                )
            if abs(value) > limit:
                raise UnsafeCommandError(
                    f"joint {joint.name!r} velocity {value} exceeds limit {limit}"
                )
            return value, False

        if joint.control_mode is ControlMode.EFFORT:
            limit = joint.effort_limit
            if limit is None:
                raise UnsafeCommandError(
                    f"effort-controlled joint {joint.name!r} has no effort limit"
                )
            if abs(value) > limit:
                raise UnsafeCommandError(
                    f"joint {joint.name!r} effort {value} exceeds limit {limit}"
                )
            return value, False

        raise UnsafeCommandError(f"unsupported control mode for joint {joint.name!r}")
