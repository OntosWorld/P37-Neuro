"""Procedural morphology generation for cross-embodiment training."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


@dataclass(frozen=True, slots=True)
class MorphologyRange:
    min_joints: int = 2
    max_joints: int = 12
    position_limit_rad: tuple[float, float] = (1.0, 3.14)
    velocity_limit_rad_s: tuple[float, float] = (1.0, 8.0)
    effort_limit_nm: tuple[float, float] = (10.0, 150.0)

    def __post_init__(self) -> None:
        if self.min_joints <= 0 or self.max_joints < self.min_joints:
            raise ValueError("invalid joint-count range")


def generate_morphology(seed: int, space: MorphologyRange | None = None) -> EmbodimentSpec:
    """Generate one deterministic synthetic articulated body."""
    space = space or MorphologyRange()
    rng = Random(seed)
    count = rng.randint(space.min_joints, space.max_joints)
    joints = []
    for index in range(count):
        limit = rng.uniform(*space.position_limit_rad)
        joints.append(
            JointSpec(
                name=f"joint_{index}",
                joint_type=JointType.REVOLUTE,
                control_mode=ControlMode.POSITION,
                position=NumericRange(-limit, limit),
                velocity_limit=rng.uniform(*space.velocity_limit_rad_s),
                effort_limit=rng.uniform(*space.effort_limit_nm),
            )
        )
    return EmbodimentSpec(
        embodiment_id=f"procedural-{seed}",
        family="procedural",
        joints=tuple(joints),
        metadata={"generator_seed": str(seed)},
    )
