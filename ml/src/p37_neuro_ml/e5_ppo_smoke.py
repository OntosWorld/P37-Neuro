"""CPU-only E5 PPO self-improvement smoke experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from torch import Tensor

from p37_neuro_ml.checkpoint import save_checkpoint
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.on_policy import OnPolicyCollector, PolicyState, RolloutConfig
from p37_neuro_ml.ppo import PPOTrainer


@dataclass(frozen=True, slots=True)
class E5SmokeResult:
    seed: int
    updates: int
    environments: int
    joints: int
    initial_mean_reward: float
    final_mean_reward: float
    reward_improvement: float
    checkpoint_dir: str


class TargetActionEnv:
    """Stateless vector control task used only to validate PPO plumbing."""

    def __init__(self, *, environments: int = 32, joints: int = 3) -> None:
        if environments <= 0 or joints <= 0:
            raise ValueError("environments and joints must be positive")
        self.environments = environments
        self.joints = joints
        positions = torch.linspace(-0.9, 0.9, environments).unsqueeze(1)
        joint_offsets = torch.linspace(-0.2, 0.2, joints).unsqueeze(0)
        self.positions = (positions + joint_offsets).clamp(-1.0, 1.0)
        self.target = (-0.75 * self.positions).clamp(-1.0, 1.0)

        self.features = torch.zeros(environments, joints, 10)
        self.features[..., 0] = -1.0
        self.features[..., 1] = 1.0
        self.features[..., 4] = 1.0
        self.features[..., 7] = 1.0
        self.mask = torch.ones(environments, joints, dtype=torch.bool)

    def _state(self) -> PolicyState:
        state = torch.zeros(self.environments, self.joints, 2)
        state[..., 0] = self.positions
        return PolicyState(self.features, state, self.mask)

    def reset(self, seed: int) -> PolicyState:
        del seed
        return self._state()

    def step(self, actions: Tensor) -> tuple[PolicyState, Tensor, Tensor]:
        if actions.shape != self.target.shape:
            raise ValueError("action shape mismatch")
        error = (actions - self.target).square().mean(dim=1)
        reward = 1.0 - error
        done = torch.ones(self.environments, dtype=torch.bool)
        return self._state(), reward, done

    def deterministic_reward(self, model: P37Neuro) -> float:
        state = self._state()
        model.eval()
        with torch.no_grad():
            output = model(
                joint_features=state.joint_features,
                joint_state=state.joint_state[:, None, :, :],
                joint_mask=state.joint_mask,
                time_mask=torch.ones(self.environments, 1, dtype=torch.bool),
            )
            actions = output.action_mean[:, 0, :]
            reward = 1.0 - (actions - self.target).square().mean(dim=1)
        return float(reward.mean())


def run_e5_ppo_smoke(
    output_dir: str | Path,
    *,
    seed: int = 211,
    updates: int = 60,
) -> E5SmokeResult:
    """Run real on-policy PPO updates and measure deterministic reward change."""
    if updates <= 0:
        raise ValueError("updates must be positive")
    torch.manual_seed(seed)

    environment = TargetActionEnv()
    model = P37Neuro(
        NeuroConfig(
            model_dim=16,
            task_feature_dim=8,
            high_level_dim=4,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=8,
            dropout=0.0,
        )
    )
    collector = OnPolicyCollector(
        model,
        environment,
        RolloutConfig(horizon=8, gamma=0.0),
    )
    trainer = PPOTrainer(
        model,
        learning_rate=8e-4,
        max_gradient_norm=2.0,
    )

    initial_reward = environment.deterministic_reward(model)
    for update in range(updates):
        batch = collector.collect(seed + update)
        advantage_std = batch.advantages.std().clamp_min(1e-6)
        batch.advantages = (batch.advantages - batch.advantages.mean()) / advantage_std
        trainer.step(batch)

    final_reward = environment.deterministic_reward(model)
    root = Path(output_dir)
    checkpoint_dir = root / "checkpoint"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "e5-ppo-smoke",
            "seed": seed,
            "updates": updates,
            "capability_evidence": "false",
        },
    )
    result = E5SmokeResult(
        seed=seed,
        updates=updates,
        environments=environment.environments,
        joints=environment.joints,
        initial_mean_reward=initial_reward,
        final_mean_reward=final_reward,
        reward_improvement=final_reward - initial_reward,
        checkpoint_dir=str(checkpoint_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "metrics.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e5-ppo-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e5-ppo-smoke"))
    parser.add_argument("--seed", type=int, default=211)
    parser.add_argument("--updates", type=int, default=60)
    args = parser.parse_args()
    result = run_e5_ppo_smoke(args.output, seed=args.seed, updates=args.updates)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
