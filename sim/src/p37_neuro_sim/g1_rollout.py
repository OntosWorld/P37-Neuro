"""Actual MuJoCo physics trial for G1; PD hold is NOT a trained walking policy."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import mujoco
import numpy as np


@dataclass(frozen=True)
class Trial:
    seed: int = 1000
    seconds: float = 8.0
    control_dt: float = 0.02
    push_start: float = 2.0
    push_duration: float = 0.15
    push_newtons: float = 45.0
    fall_drop_m: float = 0.30

    def validate(self):
        if self.seed < 0 or self.seconds <= 0 or self.control_dt <= 0:
            raise ValueError("invalid seed, duration or control period")
        if min(self.push_start, self.push_duration, self.push_newtons) < 0:
            raise ValueError("negative disturbance parameter")
        if self.push_start + self.push_duration > self.seconds:
            raise ValueError("push exceeds trial duration")
        if self.fall_drop_m <= 0:
            raise ValueError("fall threshold must be positive")


def direct_motor_mapping(model):
    mapping = []
    for i in range(model.nu):
        if int(model.actuator_trntype[i]) != int(mujoco.mjtTrn.mjTRN_JOINT):
            raise ValueError(f"unsupported transmission at actuator {i}")
        j = int(model.actuator_trnid[i, 0])
        if int(model.jnt_type[j]) not in (
            int(mujoco.mjtJoint.mjJNT_HINGE),
            int(mujoco.mjtJoint.mjJNT_SLIDE),
        ):
            raise ValueError(f"unsupported joint type at actuator {i}")
        gear = float(model.actuator_gear[i, 0])
        if abs(gear) < 1e-9:
            raise ValueError("zero actuator gear")
        mapping.append((int(model.jnt_qposadr[j]), int(model.jnt_dofadr[j]), gear))
    if not mapping:
        raise ValueError("no direct joint actuators found")
    return mapping


def clamp(model, commands):
    commands = np.asarray(commands, dtype=np.float64)
    if commands.shape != (model.nu,) or not np.all(np.isfinite(commands)):
        raise ValueError("policy must provide finite commands for every actuator")
    result = commands.copy()
    rejected = 0
    for i in range(model.nu):
        if bool(model.actuator_ctrllimited[i]):
            lo, hi = (float(v) for v in model.actuator_ctrlrange[i])
            limited = float(np.clip(result[i], lo, hi))
            rejected += int(limited != result[i])
            result[i] = limited
    return result, rejected


def run(model_path: Path, output: Path, trial: Trial, policy: str | None = None):
    trial.validate()
    model = mujoco.MjModel.from_xml_path(str(model_path.resolve()))
    data = mujoco.MjData(model)
    mapping = direct_motor_mapping(model)
    key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "stand")
    if model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, key if key >= 0 else 0)
    else:
        mujoco.mj_resetData(model, data)
    mujoco.mj_forward(model, data)
    targets = data.qpos.copy()
    free = [
        j for j in range(model.njnt) if int(model.jnt_type[j]) == int(mujoco.mjtJoint.mjJNT_FREE)
    ]
    if not free:
        raise ValueError("expected a free-base humanoid model")
    body = int(model.jnt_bodyid[free[0]])
    start_z = float(data.xpos[body, 2])
    count = round(trial.control_dt / float(model.opt.timestep))
    if count < 1 or abs(count * float(model.opt.timestep) - trial.control_dt) > 1e-9:
        raise ValueError("control period must be a multiple of the physics timestep")
    generator = np.random.default_rng(trial.seed)
    angle = float(generator.uniform(-np.pi, np.pi))
    direction = [float(np.cos(angle)), float(np.sin(angle)), 0.0]
    controller = None
    if policy:
        if ":" not in policy:
            raise ValueError("policy must be trusted module:function")
        module, func = policy.split(":", 1)
        controller = getattr(importlib.import_module(module), func)
    samples, states = [], []
    clamps = 0
    fall_s = None
    for _ in range(int(np.ceil(trial.seconds / trial.control_dt))):
        if controller:
            command = controller(model, data, trial)
        else:
            commands = []
            for index, (q, v, gear) in enumerate(mapping):
                gain = float(model.actuator_gainprm[index, 0])
                bias_position = float(model.actuator_biasprm[index, 1])
                if abs(bias_position) > 1e-8:
                    if abs(bias_position + gain) > 1e-6 * max(1.0, abs(gain)):
                        raise ValueError("unsupported position-servo control")
                    commands.append(float(targets[q] * gear))
                else:
                    if abs(gear * gain) < 1e-8:
                        raise ValueError("invalid motor transmission")
                    torque = 60 * (targets[q] - data.qpos[q]) - 3 * data.qvel[v]
                    commands.append(float(torque / (gear * gain)))
            command = np.asarray(commands, dtype=np.float64)
        limited, rejected = clamp(model, command)
        clamps += rejected
        data.ctrl[:] = limited
        for _ in range(count):
            data.xfrc_applied[body, :] = 0
            if trial.push_start <= float(data.time) < trial.push_start + trial.push_duration:
                data.xfrc_applied[body, :3] = np.asarray(direction) * trial.push_newtons
            mujoco.mj_step(model, data)
        z = float(data.xpos[body, 2])
        fallen = z < start_z - trial.fall_drop_m
        samples.append(
            {
                "time_s": float(data.time),
                "base_height_m": z,
                "fallen": int(fallen),
                "safety_clamps": rejected,
            }
        )
        states.append(
            {"time_s": float(data.time), "qpos": data.qpos.tolist(), "qvel": data.qvel.tolist()}
        )
        if fallen:
            fall_s = float(data.time)
            break
    output.mkdir(parents=True, exist_ok=True)
    with (output / "timeseries.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    (output / "trajectory.json").write_text(json.dumps(states), encoding="utf-8")
    result = {
        "level": "simulation_only",
        "controller": policy or "PD_hold_not_locomotion",
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "mujoco_version": mujoco.__version__,
        "trial": asdict(trial),
        "push_direction": direction,
        "fall_time_s": fall_s,
        "survived_trial": fall_s is None,
        "safety_clamps": clamps,
        "elapsed_s": float(data.time),
        "warning": "No P37 learned walking capability is demonstrated by this harness.",
    }
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("artifacts/g1-physics"))
    p.add_argument("--seed", type=int, default=1000)
    p.add_argument("--duration", type=float, default=8.0)
    p.add_argument("--push-newtons", type=float, default=45.0)
    p.add_argument("--policy", help="Trusted module:function; returns actuator commands")
    a = p.parse_args()
    print(
        json.dumps(
            run(
                a.model,
                a.output,
                Trial(seed=a.seed, seconds=a.duration, push_newtons=a.push_newtons),
                policy=a.policy,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
