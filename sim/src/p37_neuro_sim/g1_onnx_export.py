"""Export a trained experimental P37 G1 policy to ONNX and verify native parity.

This is an inference-format and observation-contract check, not proof of walking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from p37_neuro_ml.checkpoint import load_checkpoint
from torch import nn

from p37_neuro_sim.g1_p37_train import P37G1Env


class BrowserP37Policy(nn.Module):
    """Fixed-G1 P37 recurrent adapter using native training-time observations."""

    def __init__(self, brain: nn.Module, example: P37G1Env) -> None:
        super().__init__()
        self.brain = brain.eval()
        self.register_buffer("joint_features", example.features)
        self.register_buffer("joint_mask", example.mask)

    def forward(
        self, joint_state: torch.Tensor, task_context: torch.Tensor, memory: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        output = self.brain(
            joint_features=self.joint_features,
            joint_state=joint_state[:, None, :, :],
            joint_mask=self.joint_mask,
            time_mask=torch.ones(1, 1, dtype=torch.bool, device=joint_state.device),
            task_features=task_context,
            memory=memory,
        )
        return output.action_mean[:, 0, :], output.memory


def export(model_path: Path, checkpoint: Path, output: Path, *, parity_steps: int = 16) -> dict:
    if parity_steps < 1:
        raise ValueError("parity_steps must be positive")
    brain, manifest = load_checkpoint(checkpoint)
    brain.eval()
    env = P37G1Env(model_path, reset_on_done=False)
    output.mkdir(parents=True, exist_ok=True)
    policy = BrowserP37Policy(brain, env).eval()
    state = env.reset(seed=123456)
    memory = torch.zeros(
        brain.config.temporal_layers, 1, brain.config.model_dim, dtype=torch.float32
    )
    file = output / "p37-g1-experimental.onnx"
    try:
        torch.onnx.export(
            policy,
            (state.joint_state, state.task_features, memory),
            str(file),
            input_names=["joint_state", "task_context", "memory"],
            output_names=["action", "next_memory"],
            opset_version=18,
            dynamo=False,
        )
        onnx.checker.check_model(str(file))
        runtime = ort.InferenceSession(str(file), providers=["CPUExecutionProvider"])
        max_action_error = 0.0
        max_memory_error = 0.0
        for _ in range(parity_steps):
            with torch.no_grad():
                expected_action, expected_memory = policy(
                    state.joint_state, state.task_features, memory
                )
            output_action, output_memory = runtime.run(
                ["action", "next_memory"],
                {
                    "joint_state": state.joint_state.detach().cpu().numpy(),
                    "task_context": state.task_features.detach().cpu().numpy(),
                    "memory": memory.detach().cpu().numpy(),
                },
            )
            action_error = float(
                np.max(np.abs(output_action - expected_action.detach().cpu().numpy()))
            )
            memory_error = float(
                np.max(np.abs(output_memory - expected_memory.detach().cpu().numpy()))
            )
            max_action_error = max(max_action_error, action_error)
            max_memory_error = max(max_memory_error, memory_error)
            if action_error > 2e-3 or memory_error > 2e-3:
                raise AssertionError("ONNX/native inference diverged beyond tolerance")
            state, _, done = env.step(expected_action)
            memory = expected_memory.detach()
            if bool(done[0]):
                state = env.reset(seed=123456)
                memory.zero_()
        names = []
        model = env.sim.model
        for actuator in range(model.nu):
            joint = int(model.actuator_trnid[actuator, 0])
            names.append(mujoco_name(model, joint))
        result = {
            "status": "experimental_unqualified",
            "qualified_for_walking": False,
            "p37_checkpoint_sha256": manifest["sha256"],
            "onnx_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "robot": "unitree_g1",
            "policy_joint_names": names,
            "observation": "joint_position_residual_joint_velocity_base_vel_gravity_goal",
            "input_order": ["joint_state", "task_context", "memory"],
            "output_order": ["action", "next_memory"],
            "control_dt_s": env.sim._control_dt,
            "action_scale_rad": env.sim.action_scale_rad,
            "default_joint_pos_rad": env.sim._reference[env.sim._joint_q].tolist(),
            "parity_steps": parity_steps,
            "max_action_difference": max_action_error,
            "max_memory_difference": max_memory_error,
            "warning": "ONNX parity only. No P37 walking or recovery qualification.",
        }
        (output / "policy-contract.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        return result
    finally:
        env.close()


def mujoco_name(model, joint: int) -> str:
    import mujoco

    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint)
    if not name:
        raise ValueError(f"unnamed actuator joint {joint}")
    return name


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--parity-steps", type=int, default=16)
    a = p.parse_args()
    print(
        json.dumps(
            export(a.model, a.checkpoint, a.output, parity_steps=a.parity_steps),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
