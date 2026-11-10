"""Test *unchanged* experimental P37 weights on two physical robot morphologies.

This verifies variable-joint-count inference and actuator wiring only.
It deliberately does not classify the experiment as walking, recovery,
zero-shot task transfer, or cross-embodiment policy success.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from p37_neuro_ml.checkpoint import load_checkpoint

from p37_neuro_sim.g1_p37_train import P37G1Env


def run(
    checkpoint: Path,
    g1_model: Path,
    go2_model: Path,
    output: Path,
    *,
    seeds: int = 2,
    max_steps: int = 60,
) -> dict:
    if seeds < 1 or max_steps < 1:
        raise ValueError("positive trial counts required")
    brain, manifest = load_checkpoint(checkpoint)
    brain.eval()
    report = {
        "kind": "p37_variable_morphology_inference_smoke",
        "checkpoint_sha256": manifest["sha256"],
        "trained_on": "unitree_g1",
        "same_checkpoint_used_for_all_bodies": True,
        "parameters_retrained_for_go2": False,
        "qualified_for_cross_body_task_transfer": False,
        "qualified_for_walking": False,
        "mode": "native MuJoCo physical actuation (not browser inference)",
        "embodiment_features": (
            "prototype joint feature baseline, not a qualified morphology encoder"
        ),
        "bodies": {},
    }
    for body_id, model_path, threshold in (
        ("unitree_g1", g1_model, 0.45),
        ("unitree_go2", go2_model, 0.16),
    ):
        env = P37G1Env(model_path, reset_on_done=False, fall_height_m=threshold)
        trials = []
        try:
            for seed in range(1000, 1000 + seeds):
                state = env.reset(seed=seed)
                memory = None
                commands_sent = 0
                terminated = False
                for _ in range(max_steps):
                    with torch.no_grad():
                        response = brain(
                            joint_features=state.joint_features,
                            joint_state=state.joint_state[:, None, :, :],
                            joint_mask=state.joint_mask,
                            time_mask=torch.ones(1, 1, dtype=torch.bool),
                            task_features=state.task_features,
                            memory=memory,
                        )
                        memory = response.memory
                        command = response.action_mean[:, 0, :]
                    if command.shape != (1, env.joints):
                        raise AssertionError(
                            f"unexpected action shape for {body_id}: {tuple(command.shape)}"
                        )
                    if not bool(torch.isfinite(command).all()):
                        raise AssertionError("non-finite neural joint command")
                    state, _, done = env.step(command)
                    commands_sent += 1
                    terminated = bool(done[0])
                    if terminated:
                        break
                if commands_sent == 0:
                    raise AssertionError("no physical joint actuation was executed")
                trials.append(
                    {
                        "seed": seed,
                        "commands_sent": commands_sent,
                        "sim_seconds": float(env.last_info.get("elapsed_s", 0.0)),
                        "fell": bool(env.last_info.get("fallen", False)),
                        "terminated": terminated,
                    }
                )
            report["bodies"][body_id] = {
                "actuators": env.joints,
                "joint_state_shape": [1, env.joints, 2],
                "trials": trials,
                "inference_and_physics_executed": True,
            }
        finally:
            env.close()
    counts = {item["actuators"] for item in report["bodies"].values()}
    if len(counts) != 2:
        raise AssertionError("experiment must use physically different actuator counts")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--g1", type=Path, required=True)
    parser.add_argument("--go2", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=60)
    args = parser.parse_args()
    summary = run(
        args.checkpoint,
        args.g1,
        args.go2,
        args.output,
        seeds=args.seeds,
        max_steps=args.max_steps,
    )
    print(
        json.dumps(
            {
                "checkpoint_sha256": summary["checkpoint_sha256"],
                "qualified_for_cross_body_task_transfer": False,
                "bodies": summary["bodies"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
