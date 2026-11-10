"""Reproducible external-force test on actual Unitree MuJoCo Menagerie models.

Measures a physical force (N), impulse (N*s), and base displacement.
This is *not* a learned recovery or locomotion benchmark.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np


def rollout(
    model: mujoco.MjModel,
    *,
    force_n: float,
    duration_s: float = 0.8,
    push_start_s: float = 0.15,
    push_end_s: float = 0.30,
) -> dict:
    if force_n < 0 or not 0 < push_start_s < push_end_s < duration_s:
        raise ValueError("invalid force or push timing")
    free_roots = [
        j for j in range(model.njnt)
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE
    ]
    if len(free_roots) != 1:
        raise ValueError("experiment requires exactly one floating base")
    base_body = int(model.jnt_bodyid[free_roots[0]])
    data = mujoco.MjData(model)
    key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    if model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, key if key >= 0 else 0)
    else:
        mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)
    start_xyz = data.xpos[base_body].copy()
    steps = int(np.ceil(duration_s / float(model.opt.timestep)))
    for _ in range(steps):
        data.xfrc_applied[base_body] = 0
        if push_start_s <= data.time < push_end_s:
            data.xfrc_applied[base_body, 0] = force_n
        mujoco.mj_step(model, data)
    end_xyz = data.xpos[base_body].copy()
    return {
        "start_xyz_m": start_xyz.tolist(),
        "end_xyz_m": end_xyz.tolist(),
        "delta_xyz_m": (end_xyz - start_xyz).tolist(),
        "simulated_seconds": float(data.time),
    }


def measure(model_path: Path, force_n: float) -> dict:
    model = mujoco.MjModel.from_xml_path(str(model_path.resolve()))
    base = rollout(model, force_n=0.0)
    push = rollout(model, force_n=force_n)
    push_repeat = rollout(model, force_n=force_n)
    delta = np.asarray(push["end_xyz_m"]) - np.asarray(base["end_xyz_m"])
    difference = float(np.linalg.norm(delta))
    if difference <= 1e-4:
        raise AssertionError("physical disturbance did not move the robot relative to baseline")
    if not np.allclose(push["end_xyz_m"], push_repeat["end_xyz_m"], atol=1e-9, rtol=0):
        raise AssertionError("identical physical trial did not reproduce its trajectory")
    return {
        "model": model_path.as_posix(),
        "physics": "MuJoCo",
        "force_newtons": force_n,
        "push_start_s": 0.15,
        "push_end_s": 0.30,
        "nominal_impulse_Ns": round(force_n * 0.15, 6),
        "displacement_vs_control_m": difference,
        "baseline": base,
        "pushed": push,
        "repeat_deterministic": True,
        "controller": "none",
        "p37_recovery_claimed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    runs = {
        "unitree_g1": measure(args.menagerie / "unitree_g1/scene.xml", 90.0),
        "unitree_go2": measure(args.menagerie / "unitree_go2/scene.xml", 40.0),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        robot: {
            "displacement_vs_control_m": trial["displacement_vs_control_m"],
            "repeat_deterministic": trial["repeat_deterministic"],
        }
        for robot, trial in runs.items()
    }, indent=2))


if __name__ == "__main__":
    main()
