"""Train the actual P37Neuro recurrent model against G1 MuJoCo physics.

Experimental P37 RL research pipeline. A saved checkpoint is not proof of walking.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from p37_neuro_ml.checkpoint import load_checkpoint, save_checkpoint
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.on_policy import OnPolicyCollector, PolicyState, RolloutConfig
from p37_neuro_ml.ppo import PPOTrainer

from p37_neuro_sim.g1_locomotion_env import G1LocomotionEnv


class P37G1Env:
    """Single-physics-environment vector adapter for P37's PPO collector."""

    def __init__(self, model_path: Path) -> None:
        self.sim = G1LocomotionEnv(model_path)
        self.joints = len(self.sim._actuators)
        self.features = torch.zeros(1, self.joints, 10, dtype=torch.float32)
        self.features[..., 0] = -1.0
        self.features[..., 1] = 1.0
        self.features[..., 4] = 1.0
        self.features[..., 7] = 1.0
        self.mask = torch.ones(1, self.joints, dtype=torch.bool)
        self._obs: np.ndarray | None = None
        self._seed = 0

    def _state(self) -> PolicyState:
        assert self._obs is not None
        n = self.joints
        state = np.stack((self._obs[:n], self._obs[n : 2 * n]), axis=-1)
        task = np.zeros((1, 1, 8), dtype=np.float32)
        # Four base values are made available through task context; for this
        # baseline, proprioception remains the only policy state input.
        task[0, 0, :3] = self._obs[2 * n : 2 * n + 3]
        task[0, 0, 3:6] = self._obs[2 * n + 3 : 2 * n + 6]
        task[0, 0, 6] = self._obs[-2]
        task[0, 0, 7] = self._obs[-1]
        return PolicyState(
            joint_features=self.features,
            joint_state=torch.tensor(state[None], dtype=torch.float32),
            joint_mask=self.mask,
            task_features=torch.tensor(task),
        )

    def reset(self, seed: int) -> PolicyState:
        self._seed = seed
        self._obs, _ = self.sim.reset(seed=seed)
        return self._state()

    def step(self, actions: torch.Tensor):
        if actions.shape != (1, self.joints):
            raise ValueError("P37 G1 output shape mismatch")
        action = actions[0].detach().cpu().numpy()
        self._obs, reward, done, truncated, _ = self.sim.step(action)
        terminal = bool(done or truncated)
        if terminal:
            self._seed += 1
            self._obs, _ = self.sim.reset(seed=self._seed)
        return (
            self._state(),
            torch.tensor([reward], dtype=torch.float32),
            torch.tensor([terminal], dtype=torch.bool),
        )

    def close(self) -> None:
        self.sim.close()


def train(model_path: Path, output: Path, *, updates: int, seed: int) -> None:
    if updates <= 0:
        raise ValueError("updates must be positive")
    torch.manual_seed(seed)
    np.random.seed(seed)
    env = P37G1Env(model_path)
    brain = P37Neuro(
        NeuroConfig(
            model_dim=32,
            task_feature_dim=8,
            high_level_dim=8,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=8,
            dropout=0.0,
        )
    )
    collector = OnPolicyCollector(brain, env, RolloutConfig(horizon=64, gamma=0.99))
    trainer = PPOTrainer(brain, learning_rate=2e-4, max_gradient_norm=1.0)
    history = []
    try:
        for update in range(updates):
            batch = collector.collect(seed + update * 1000)
            standard = batch.advantages.std(unbiased=False).clamp_min(1e-6)
            batch.advantages = (batch.advantages - batch.advantages.mean()) / standard
            metrics = trainer.step(batch)
            history.append({
                "update": update + 1,
                "loss": metrics.loss,
                "policy_loss": metrics.policy_loss,
                "value_loss": metrics.value_loss,
            })
    finally:
        env.close()
    output.mkdir(parents=True, exist_ok=True)
    save_checkpoint(
        output / "checkpoint",
        brain,
        metadata={
            "experiment": "g1-native-mujoco-ppo",
            "seed": seed,
            "updates": updates,
            "capability_evidence": "false",
        },
    )
    (output / "history.json").write_text(json.dumps(history, indent=2) + "\n")

def evaluate(model_path: Path, checkpoint: Path, output: Path) -> None:
    brain, manifest = load_checkpoint(checkpoint)
    brain.eval()
    env = P37G1Env(model_path)
    trials = []
    try:
        for seed in range(1000, 1100):
            state = env.reset(seed)
            memory = None
            reward_total = 0.0
            for step in range(500):
                with torch.no_grad():
                    result = brain(
                        joint_features=state.joint_features,
                        joint_state=state.joint_state[:, None, :, :],
                        joint_mask=state.joint_mask,
                        time_mask=torch.ones(1, 1, dtype=torch.bool),
                        task_features=state.task_features,
                        memory=memory,
                    )
                    memory = result.memory
                    actions = result.action_mean[:, 0, :]
                state, reward, done = env.step(actions)
                reward_total += float(reward[0])
                if bool(done[0]):
                    break
            trials.append({
                "seed": seed,
                "total_reward": reward_total,
                "steps": step + 1,
                "episode_ended": bool(done[0]),
            })
    finally:
        env.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "kind": "P37Neuro_unqualified_g1_simulation",
        "checkpoint_sha256": manifest["sha256"],
        "trials": trials,
        "warning": (
            "Evaluation does not yet distinguish timeout from falls or "
            "measure walking recovery."
        ),
    }, indent=2) + "\n")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("artifacts/g1-p37"))
    p.add_argument("--updates", type=int, default=1000)
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--evaluate", type=Path, help="P37 checkpoint directory")
    args = p.parse_args()
    if args.evaluate is None:
        train(args.model, args.output, updates=args.updates, seed=args.seed)
    else:
        evaluate(args.model, args.evaluate, args.output / "heldout.json")


if __name__ == "__main__":
    main()
