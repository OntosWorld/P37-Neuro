"""Reference behavior-cloning trainer for the P37 robot brain."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from p37_neuro_ml.losses import imitation_loss
from p37_neuro_ml.model import P37Neuro


@dataclass(slots=True)
class BrainBatch:
    joint_features: Tensor
    joint_state: Tensor
    joint_mask: Tensor
    target_actions: Tensor
    scene_images: Tensor | None = None
    demonstration_images: Tensor | None = None
    task_features: Tensor | None = None
    target_high_level: Tensor | None = None
    target_values: Tensor | None = None


@dataclass(frozen=True, slots=True)
class TrainStepMetrics:
    loss: float
    action_loss: float
    high_level_loss: float
    value_loss: float
    gradient_norm: float


class BehaviorCloningTrainer:
    """Minimal reproducible BC optimizer used before RL post-training."""

    def __init__(
        self,
        model: P37Neuro,
        *,
        learning_rate: float = 3e-4,
        weight_decay: float = 1e-4,
        max_gradient_norm: float = 1.0,
    ) -> None:
        if learning_rate <= 0 or max_gradient_norm <= 0:
            raise ValueError("learning rate and max gradient norm must be positive")
        self.model = model
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=learning_rate, weight_decay=weight_decay
        )
        self.max_gradient_norm = max_gradient_norm

    def step(self, batch: BrainBatch) -> TrainStepMetrics:
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        output = self.model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state,
            joint_mask=batch.joint_mask,
            scene_images=batch.scene_images,
            demonstration_images=batch.demonstration_images,
            task_features=batch.task_features,
        )
        losses = imitation_loss(
            output,
            target_actions=batch.target_actions,
            joint_mask=batch.joint_mask,
            target_high_level=batch.target_high_level,
            target_values=batch.target_values,
        )
        losses.total.backward()
        norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.max_gradient_norm)
        self.optimizer.step()
        return TrainStepMetrics(
            loss=float(losses.total.detach()),
            action_loss=float(losses.action.detach()),
            high_level_loss=float(losses.high_level.detach()),
            value_loss=float(losses.value.detach()),
            gradient_norm=float(norm.detach()),
        )
