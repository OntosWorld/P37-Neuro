"""Run one frozen recurrent P37 checkpoint on two genuine Menagerie bodies.

Demonstrates the variable-joint input/output contract in closed-loop MuJoCo,
not cross-robot skill transfer, walking, or physical robot qualification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from p37_neuro_ml.checkpoint import load_checkpoint

from p37_neuro_sim.g1_p37_train import P37G1Env


def evaluate_body(
    brain: torch.nn.Module,
    model_path: Path,
    *,
    robot_id: str,
    seed: int = 1407,
    steps: int = 30,
) -> dict:
    env = P37G1Env(model_path, reset_on_done=False)
    if robot_id == "unitree_go2":
        # The G1-specific root-height condition must not classify a healthy
        # quadruped as fallen merely because it is shorter than a humanoid.
        env.sim.fall_height_m = 0.16
    try:
        state = env.reset(seed)
        memory = None
        max_action = 0.0
        executed = 0
        fall_detected = False
        for _ in range(steps):
            with torch.no_grad():
                prediction = brain(
                    joint_features=state.joint_features,
                    joint_state=state.joint_state[:, None, :, :],
                    joint_mask=state.joint_mask,
                    time_mask=torch.ones(1, 1, dtype=torch.bool),
                    task_features=state.task_features,
                    memory=memory,
                )
                memory = prediction.memory
                action = prediction.action_mean[:, 0, :]
            if action.shape != (1, env.joints):
                raise AssertionError("Shared P37 model produced the wrong action shape")
            if not np.isfinite(action.detach().numpy()).all():
                raise AssertionError("Shared P37 model generated nonfinite commands")
            max_action = max(max_action, float(action.abs().max()))
            state, _, done = env.step(action)
            executed += 1
            if bool(done[0]):
                fall_detected = bool(env.last_info.get("fallen", False))
                break
        return {
            "robot_id": robot_id,
            "joints": env.joints,
            "output_actions": env.joints,
            "requested_steps": steps,
            "executed_steps": executed,
            "simulated_seconds": float(env.last_info.get("elapsed_s", 0.0)),
            "final_base_height_m": float(env.last_info.get("base_height_m", 0.0)),
            "fall_detected": fall_detected,
            "max_absolute_action": max_action,
            "controller": "same_frozen_p37_checkpoint",
            "qualified": False,
        }
    finally:
        env.close()


def run(menagerie: Path, checkpoint: Path, output: Path) -> dict:
    torch.set_num_threads(2)
    brain, manifest = load_checkpoint(checkpoint)
    brain.eval()
    meta = manifest.get("metadata", {})
    if meta.get("capability_evidence") != "false":
        raise ValueError("Expected experimental P37 checkpoint only")
    results = [
        evaluate_body(
            brain,
            menagerie / name / "scene.xml",
            robot_id=name,
        )
        for name in ("unitree_g1", "unitree_go2")
    ]
    if results[0]["joints"] == results[1]["joints"]:
        raise AssertionError("Bodies must have materially different action dimensions")
    report = {
        "schema_version": 1,
        "kind": "p37_same_checkpoint_two_real_bodies",
        "model": "P37Neuro recurrent",
        "checkpoint_sha256": manifest["sha256"],
        "shared_weights": True,
        "additional_finetuning": False,
        "actual_model_inference": True,
        "actual_mujoco_physics": True,
        "task": "Short forward-command control smoke",
        "performance_qualified": False,
        "robot_results": results,
        "interpretation": (
            "The same trained G1 checkpoint can produce joint commands of "
            "different lengths and drive short MuJoCo rollouts on G1 and Go2. "
            "This demonstrates architectural compatibility, not successful "
            "cross-embodiment locomotion or transfer learning."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.menagerie, args.checkpoint, args.output), indent=2))


if __name__ == "__main__":
    main()
