"""Conversion from canonical P37 episodes into variable-morphology tensors."""

from __future__ import annotations

from dataclasses import dataclass
from math import log1p, pi

import torch

from p37_neuro.core.types import ControlMode, JointType
from p37_neuro.data.schema import Episode
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec
from p37_neuro_ml.trainer import BrainBatch

JOINT_FEATURE_DIM = 10


@dataclass(frozen=True, slots=True)
class EpisodeExample:
    episode: Episode
    embodiment: EmbodimentSpec

    def __post_init__(self) -> None:
        if self.episode.embodiment_id != self.embodiment.embodiment_id:
            raise ValueError("episode and embodiment identifiers do not match")


def _limit(value: float | None, scale: float) -> float:
    if value is None:
        return 0.0
    return min(1.0, log1p(abs(value)) / scale)


def joint_features(joint: JointSpec) -> tuple[float, ...]:
    """Encode one joint into stable, dimensionless morphology features."""
    lower = joint.position.minimum / pi if joint.position is not None else 0.0
    upper = joint.position.maximum / pi if joint.position is not None else 0.0
    return (
        max(-1.0, min(1.0, lower)),
        max(-1.0, min(1.0, upper)),
        _limit(joint.velocity_limit, 3.0),
        _limit(joint.effort_limit, 6.0),
        float(joint.joint_type is JointType.REVOLUTE),
        float(joint.joint_type is JointType.PRISMATIC),
        float(joint.joint_type is JointType.CONTINUOUS),
        float(joint.control_mode is ControlMode.POSITION),
        float(joint.control_mode is ControlMode.VELOCITY),
        float(joint.control_mode is ControlMode.EFFORT),
    )


def normalize_action(joint: JointSpec, value: float) -> float:
    """Normalize a physical joint command into the model's [-1, 1] action space."""
    if joint.control_mode is ControlMode.POSITION:
        if joint.position is None:
            raise ValueError(f"position joint {joint.name!r} has no bounded range")
        midpoint = (joint.position.minimum + joint.position.maximum) / 2.0
        half_range = (joint.position.maximum - joint.position.minimum) / 2.0
        if half_range <= 0:
            raise ValueError(f"position joint {joint.name!r} has zero range")
        return max(-1.0, min(1.0, (value - midpoint) / half_range))
    if joint.control_mode is ControlMode.VELOCITY:
        if joint.velocity_limit is None:
            raise ValueError(f"velocity joint {joint.name!r} has no limit")
        return max(-1.0, min(1.0, value / joint.velocity_limit))
    if joint.control_mode is ControlMode.EFFORT:
        if joint.effort_limit is None:
            raise ValueError(f"effort joint {joint.name!r} has no limit")
        return max(-1.0, min(1.0, value / joint.effort_limit))
    raise ValueError(f"unsupported control mode: {joint.control_mode}")


def collate_episodes(
    examples: tuple[EpisodeExample, ...],
    *,
    discount: float = 0.99,
    device: torch.device | str = "cpu",
) -> BrainBatch:
    """Pad heterogeneous episodes into one model batch."""
    if not examples:
        raise ValueError("at least one episode is required")
    if not 0.0 <= discount <= 1.0:
        raise ValueError("discount must be in [0, 1]")

    batch = len(examples)
    max_joints = max(len(example.embodiment.joints) for example in examples)
    max_steps = max(len(example.episode.steps) for example in examples)

    features = torch.zeros(batch, max_joints, JOINT_FEATURE_DIM, device=device)
    states = torch.zeros(batch, max_steps, max_joints, 2, device=device)
    actions = torch.zeros(batch, max_steps, max_joints, device=device)
    values = torch.zeros(batch, max_steps, device=device)
    joint_mask = torch.zeros(batch, max_joints, dtype=torch.bool, device=device)
    time_mask = torch.zeros(batch, max_steps, dtype=torch.bool, device=device)

    for batch_index, example in enumerate(examples):
        joints = example.embodiment.joints
        index = {joint.name: joint_index for joint_index, joint in enumerate(joints)}
        joint_mask[batch_index, : len(joints)] = True
        time_mask[batch_index, : len(example.episode.steps)] = True
        for joint_index, joint in enumerate(joints):
            features[batch_index, joint_index] = torch.tensor(
                joint_features(joint), device=device
            )

        discounted_return = 0.0
        return_values = [0.0] * len(example.episode.steps)
        for step_index in range(len(example.episode.steps) - 1, -1, -1):
            reward = example.episode.steps[step_index].reward or 0.0
            discounted_return = reward + discount * discounted_return
            return_values[step_index] = discounted_return

        for step_index, step in enumerate(example.episode.steps):
            for name, joint_index in index.items():
                states[batch_index, step_index, joint_index, 0] = (
                    step.observation.joint_position.get(name, 0.0)
                )
                states[batch_index, step_index, joint_index, 1] = (
                    step.observation.joint_velocity.get(name, 0.0)
                )
            for name, value in step.action.joint_commands.items():
                if name not in index:
                    raise ValueError(f"episode contains unknown joint action: {name}")
                joint_index = index[name]
                actions[batch_index, step_index, joint_index] = normalize_action(
                    joints[joint_index], value
                )
            values[batch_index, step_index] = return_values[step_index]

    return BrainBatch(
        joint_features=features,
        joint_state=states,
        joint_mask=joint_mask,
        time_mask=time_mask,
        target_actions=actions,
        target_values=values,
    )
