"""Training objectives for imitation and reinforcement-learning post-training."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor
from torch.distributions import Normal

from p37_neuro_ml.model import P37Output


@dataclass(frozen=True, slots=True)
class LossBreakdown:
    total: Tensor
    action: Tensor
    high_level: Tensor
    value: Tensor
    policy: Tensor
    entropy: Tensor


def _masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    weights = mask.to(values.dtype)
    return (values * weights).sum() / weights.sum().clamp_min(1.0)


def imitation_loss(
    output: P37Output,
    *,
    target_actions: Tensor,
    joint_mask: Tensor,
    target_high_level: Tensor | None = None,
    target_values: Tensor | None = None,
    high_level_weight: float = 0.2,
    value_weight: float = 0.1,
) -> LossBreakdown:
    """Behavior-cloning objective across variable-morphology batches."""
    if target_actions.shape != output.action_mean.shape:
        raise ValueError("target_actions shape mismatch")
    sequence_mask = joint_mask[:, None, :].expand_as(output.action_mean)
    action = _masked_mean((output.action_mean - target_actions).square(), sequence_mask)

    zero = action.new_zeros(())
    high_level = zero
    if target_high_level is not None:
        if target_high_level.shape != output.high_level.shape:
            raise ValueError("target_high_level shape mismatch")
        high_level = (output.high_level - target_high_level).square().mean()

    value = zero
    if target_values is not None:
        if target_values.shape != output.value.shape:
            raise ValueError("target_values shape mismatch")
        value = (output.value - target_values).square().mean()

    total = action + high_level_weight * high_level + value_weight * value
    return LossBreakdown(total, action, high_level, value, zero, zero)


def ppo_loss(
    output: P37Output,
    *,
    actions: Tensor,
    joint_mask: Tensor,
    old_log_prob: Tensor,
    advantages: Tensor,
    returns: Tensor,
    clip_ratio: float = 0.2,
    value_weight: float = 0.5,
    entropy_weight: float = 0.01,
) -> LossBreakdown:
    """Clipped PPO objective over variable-size joint action distributions."""
    if actions.shape != output.action_mean.shape:
        raise ValueError("actions shape mismatch")
    sequence_mask = joint_mask[:, None, :].expand_as(actions)
    distribution = Normal(output.action_mean, output.action_log_std.exp())
    joint_log_prob = distribution.log_prob(actions).masked_fill(~sequence_mask, 0.0)
    log_prob = joint_log_prob.sum(dim=-1)
    entropy = distribution.entropy().masked_fill(~sequence_mask, 0.0).sum(dim=-1).mean()

    ratio = (log_prob - old_log_prob).exp()
    unclipped = ratio * advantages
    clipped = ratio.clamp(1.0 - clip_ratio, 1.0 + clip_ratio) * advantages
    policy = -torch.minimum(unclipped, clipped).mean()
    value = (output.value - returns).square().mean()
    zero = policy.new_zeros(())
    total = policy + value_weight * value - entropy_weight * entropy
    return LossBreakdown(total, zero, zero, value, policy, entropy)
