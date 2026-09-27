"""Executable PPO post-training step for P37 Neuro."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor
from torch.distributions import Normal

from p37_neuro_ml.losses import ppo_loss
from p37_neuro_ml.model import P37Neuro


@dataclass(slots=True)
class PPOBatch:
    joint_features: Tensor
    joint_state: Tensor
    joint_mask: Tensor
    time_mask: Tensor
    actions: Tensor
    old_log_prob: Tensor
    advantages: Tensor
    returns: Tensor
    scene_images: Tensor | None = None
    demonstration_images: Tensor | None = None
    task_features: Tensor | None = None


@dataclass(frozen=True, slots=True)
class PPOUpdateMetrics:
    loss: float
    policy_loss: float
    value_loss: float
    entropy: float
    gradient_norm: float


def sample_actions(
    mean: Tensor,
    log_std: Tensor,
    *,
    joint_mask: Tensor,
    deterministic: bool = False,
) -> tuple[Tensor, Tensor]:
    """Sample normalized joint actions and their summed log probability."""
    distribution = Normal(mean, log_std.exp())
    actions = mean if deterministic else distribution.sample()
    sequence_mask = joint_mask[:, None, :].expand_as(actions)
    actions = actions.clamp(-1.0, 1.0).masked_fill(~sequence_mask, 0.0)
    log_prob = distribution.log_prob(actions).masked_fill(~sequence_mask, 0.0).sum(dim=-1)
    return actions, log_prob


class PPOTrainer:
    def __init__(
        self,
        model: P37Neuro,
        *,
        learning_rate: float = 1e-4,
        max_gradient_norm: float = 1.0,
    ) -> None:
        self.model = model
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
        self.max_gradient_norm = max_gradient_norm

    def step(self, batch: PPOBatch) -> PPOUpdateMetrics:
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        output = self.model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
            scene_images=batch.scene_images,
            demonstration_images=batch.demonstration_images,
            task_features=batch.task_features,
        )
        losses = ppo_loss(
            output,
            actions=batch.actions,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
            old_log_prob=batch.old_log_prob,
            advantages=batch.advantages,
            returns=batch.returns,
        )
        losses.total.backward()
        norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.max_gradient_norm)
        self.optimizer.step()
        return PPOUpdateMetrics(
            loss=float(losses.total.detach()),
            policy_loss=float(losses.policy.detach()),
            value_loss=float(losses.value.detach()),
            entropy=float(losses.entropy.detach()),
            gradient_norm=float(norm.detach()),
        )
