"""Train a G1 MuJoCo locomotion policy and evaluate it on held-out seeds.

This produces an experimental SB3 PPO checkpoint, *not* a qualified P37 shared brain.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from p37_neuro_sim.g1_locomotion_env import G1LocomotionEnv


def train(model: Path, output: Path, *, timesteps: int, seed: int) -> None:
    from stable_baselines3 import PPO

    if timesteps <= 0:
        raise ValueError("timesteps must be positive")
    output.mkdir(parents=True, exist_ok=True)
    env = G1LocomotionEnv(model)
    try:
        agent = PPO(
            "MlpPolicy", env, seed=seed, verbose=1, device="cpu", n_steps=1024, batch_size=256
        )
        agent.learn(total_timesteps=timesteps)
        agent.save(str(output / "g1_ppo.zip"))
        (output / "training.json").write_text(
            json.dumps(
                {
                    "kind": "experimental_g1_locomotion_baseline",
                    "policy_family": "stable_baselines3_PPO",
                    "is_trained_p37_brain": False,
                    "timesteps": timesteps,
                    "seed": seed,
                    "model": str(model.resolve()),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        env.close()


def evaluate(
    model: Path, checkpoint: Path, output: Path, *, seeds: range = range(1000, 1100)
) -> dict:
    from stable_baselines3 import PPO

    env = G1LocomotionEnv(model)
    agent = PPO.load(str(checkpoint), device="cpu")
    trials = []
    try:
        for seed in seeds:
            obs, _ = env.reset(seed=seed)
            total_reward = 0.0
            steps = 0
            while True:
                act, _ = agent.predict(obs, deterministic=True)
                obs, rew, terminated, truncated, info = env.step(np.asarray(act))
                total_reward += rew
                steps += 1
                if terminated or truncated:
                    trials.append(
                        {
                            "seed": seed,
                            "fallen": info["fallen"],
                            "sim_seconds": info["elapsed_s"],
                            "mean_reward": total_reward / steps,
                            "final_forward_velocity_m_s": info["forward_velocity_m_s"],
                        }
                    )
                    break
        result = {
            "checkpoint": str(checkpoint),
            "kind": "experimental_baseline_not_p37",
            "trials": trials,
            "survival_fraction": sum(not t["fallen"] for t in trials) / len(trials),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result
    finally:
        env.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("artifacts/g1-ppo"))
    p.add_argument("--timesteps", type=int, default=100_000)
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--evaluate", type=Path, help="Checkpoint .zip; evaluate instead of train")
    args = p.parse_args()
    if args.evaluate:
        print(json.dumps(evaluate(args.model, args.evaluate, args.output / "heldout.json")))
    else:
        train(args.model, args.output, timesteps=args.timesteps, seed=args.seed)


if __name__ == "__main__":
    main()
