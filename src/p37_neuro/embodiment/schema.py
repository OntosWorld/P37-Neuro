"""Canonical robot embodiment schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from p37_neuro.core.types import ControlMode, JointType, NumericRange


@dataclass(frozen=True, slots=True)
class JointSpec:
    """Machine-readable contract for one controllable joint."""

    name: str
    joint_type: JointType
    control_mode: ControlMode
    position: NumericRange | None = None
    velocity_limit: float | None = None
    effort_limit: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("joint name cannot be empty")
        if self.joint_type is JointType.FIXED:
            raise ValueError("fixed joints must not appear in the controllable joint set")
        for label, value in (
            ("velocity_limit", self.velocity_limit),
            ("effort_limit", self.effort_limit),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{label} must be positive")
        if self.joint_type is JointType.CONTINUOUS and self.position is not None:
            raise ValueError("continuous joints must not declare a bounded position range")


@dataclass(frozen=True, slots=True)
class EmbodimentSpec:
    """Canonical description of the body controlled by a P37 policy."""

    embodiment_id: str
    family: str
    joints: tuple[JointSpec, ...]
    end_effectors: tuple[str, ...] = ()
    sensors: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.embodiment_id.strip():
            raise ValueError("embodiment_id cannot be empty")
        if not self.family.strip():
            raise ValueError("family cannot be empty")
        names = [joint.name for joint in self.joints]
        if len(names) != len(set(names)):
            raise ValueError("joint names must be unique within an embodiment")

    @property
    def action_dimension(self) -> int:
        """Return the number of independently commanded joints."""
        return len(self.joints)

    def joint(self, name: str) -> JointSpec:
        """Return a joint by name or raise KeyError."""
        for joint in self.joints:
            if joint.name == name:
                return joint
        raise KeyError(name)
