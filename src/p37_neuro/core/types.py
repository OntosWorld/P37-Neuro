"""Shared immutable types used across P37 Neuro boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

type Seconds = float
type Radians = float
type RadiansPerSecond = float
type NewtonMeters = float


class ControlMode(StrEnum):
    """Actuator command interpretation at a robot boundary."""

    POSITION = "position"
    VELOCITY = "velocity"
    EFFORT = "effort"


class JointType(StrEnum):
    """Supported joint topology categories."""

    REVOLUTE = "revolute"
    PRISMATIC = "prismatic"
    CONTINUOUS = "continuous"
    FIXED = "fixed"


@dataclass(frozen=True, slots=True)
class NumericRange:
    """Closed numeric interval with explicit validation."""

    minimum: float
    maximum: float

    def __post_init__(self) -> None:
        if not isfinite(self.minimum) or not isfinite(self.maximum):
            raise ValueError("range bounds must be finite")
        if self.minimum > self.maximum:
            raise ValueError("range minimum cannot exceed maximum")

    def contains(self, value: float) -> bool:
        """Return whether value lies inside the closed interval."""
        return isfinite(value) and self.minimum <= value <= self.maximum

    def clamp(self, value: float) -> float:
        """Clamp a finite value into the interval."""
        if not isfinite(value):
            raise ValueError("cannot clamp a non-finite value")
        return min(self.maximum, max(self.minimum, value))
