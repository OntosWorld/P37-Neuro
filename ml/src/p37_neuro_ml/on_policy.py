"""On-policy rollout collection for PPO post-training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import torch
from torch import Tensor

from p37_neuro_ml.model import P37Neuro
from p37_neuro_ml.ppo import PPOBatch, sample_actions


@dataclass(slots=True)
class PolicyState:
    """Vectorized observation already normalized for the P37 model."""

    joint_features: Tensor
    joint_state: Tensor
    joint_mask: Tensor
    scene_images: Tensor | None = None
    demonstration_images: Tensor | None = None
    task_features: Tensor | None = None

    def __post_init__(self) -> None:
        if self.joint_features.ndim != 3:
            raise ValueError("joint_features must be [B, J, F]")
        if self.joint_state.ndim != 3:
            raise ValueError("joint_state must be [B, J, S]")
        if self.joint_mask.ndim != 2:
            raise ValueError("joint_mask must be [B, J]")
        if self.joint_features.shape[:2] != self.joint_state.shape[:2]:
            raise ValueError("joint state/features must share batch and joint dimensions")
        if self.joint_mask.shape != self.joint_state.shape[:2]:
            raise ValueError("joint mask shape mismatch")


class VectorPolicyEnv(Protocol):
    """Minimal vector environment needed by the P37 on-policy collector."""

    def reset(self, seed: int) -> PolicyState: ...

    def step(self, actions: Tensor) -> tuple[PolicyState, Tensor, Tensor]:
        """Return next_state, reward[B], done[B]."""
        ...


@dataclass(frozen=True, slots=True)
class RolloutConfig:
    horizon: int = 128
    gamma: float = 0.99
    deterministic_actions: bool = False

    def __post_init__(self) -> None:
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        if not 0.0 <= self.gamma <= 1.0:
            raise ValueError("gamma must be in [0, 1]")


class OnPolicyCollector:
    """Collect recurrent multi-embodiment trajectories into PPO batches."""

    def __init__(
        self,
        model: P37Neuro,
        environment: VectorPolicyEnv,
        config: RolloutConfig | None = None,
    ) -> None:
        self.model = model
        self.environment = environment
        self.config = config or RolloutConfig()

    @staticmethod
    def _zero_done_memory(memory: Tensor, done: Tensor) -> Tensor:
        if done.ndim != 1 or memory.shape[1] != done.shape[0]:
            raise ValueError("done mask does not match recurrent memory batch")
        result = memory.clone()
        result[:, done.bool(), :] = 0.0
        return result

    def collect(self, seed: int) -> PPOBatch:
        self.model.eval()
        state = self.environment.reset(seed)
        batch = state.joint_state.shape[0]
        joints = state.joint_state.shape[1]
        device = state.joint_state.device
        memory: Tensor | None = None

        states: list[Tensor] = []
        actions: list[Tensor] = []
        log_probs: list[Tensor] = []
        values: list[Tensor] = []
        rewards: list[Tensor] = []
        dones: list[Tensor] = []

        joint_features = state.joint_features
        joint_mask = state.joint_mask
        demonstration_images = state.demonstration_images
        task_features = state.task_features

        for _ in range(self.config.horizon):
            model_state = state.joint_state[:, None, :, :]
            time_mask = torch.ones(batch, 1, dtype=torch.bool, device=device)
            with torch.no_grad():
                output = self.model(
                    joint_features=state.joint_features,
                    joint_state=model_state,
                    joint_mask=state.joint_mask,
                    time_mask=time_mask,
                    scene_images=(
                        state.scene_images[:, None, ...] if state.scene_images is not None else None
                    ),
                    demonstration_images=state.demonstration_images,
                    task_features=state.task_features,
                    memory=memory,
                )
                sampled, log_prob = sample_actions(
                    output.action_mean,
                    output.action_log_std,
                    joint_mask=state.joint_mask,
                    deterministic=self.config.deterministic_actions,
                )

            step_actions = sampled[:, 0, :]
            next_state, reward, done = self.environment.step(step_actions)
            if reward.shape != (batch,) or done.shape != (batch,):
                raise ValueError("environment reward/done must be [B]")
            if next_state.joint_state.shape[:2] != (batch, joints):
                raise ValueError("environment changed vector batch or joint shape during rollout")

            states.append(state.joint_state)
            actions.append(step_actions)
            log_probs.append(log_prob[:, 0])
            values.append(output.value[:, 0])
            rewards.append(reward)
            dones.append(done.bool())

            memory = self._zero_done_memory(output.memory, done)
            state = next_state

        rewards_tensor = torch.stack(rewards, dim=1)
        dones_tensor = torch.stack(dones, dim=1)
        values_tensor = torch.stack(values, dim=1)

        returns = torch.zeros_like(rewards_tensor)
        running = torch.zeros(batch, device=device, dtype=rewards_tensor.dtype)
        for step in range(self.config.horizon - 1, -1, -1):
            running = rewards_tensor[:, step] + (
                self.config.gamma * running * (~dones_tensor[:, step]).to(running.dtype)
            )
            returns[:, step] = running
        advantages = returns - values_tensor

        return PPOBatch(
            joint_features=joint_features,
            joint_state=torch.stack(states, dim=1),
            joint_mask=joint_mask,
            time_mask=torch.ones(
                batch,
                self.config.horizon,
                dtype=torch.bool,
                device=device,
            ),
            actions=torch.stack(actions, dim=1),
            old_log_prob=torch.stack(log_probs, dim=1),
            advantages=advantages,
            returns=returns,
            demonstration_images=demonstration_images,
            task_features=task_features,
        )
