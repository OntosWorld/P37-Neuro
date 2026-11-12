"""Build per-robot, model-compatible motion datasets and ONNX playback controls.

Clips are synthesized from official MuJoCo Menagerie joint limits and keyframes.
They are *not* human demonstrations, licensed external trajectories, or learned
P37 policies. Playback drives the real physics model's actuators at 50 Hz.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np
import onnx
from onnx import TensorProto, helper

RATE = 50
FRAMES = 200
MODES = ("articulation", "motion_cycle", "hold")
CONTROL_DT = 1.0 / RATE


def _transmissions(model: mujoco.MjModel) -> tuple[list[str], list[int]]:
    names: list[str] = []
    joints: list[int] = []
    for index in range(model.nu):
        if int(model.actuator_trntype[index]) != int(mujoco.mjtTrn.mjTRN_JOINT):
            # Some official bodies have site/tendon actuators alongside
            # ordinary joint motors. Animate supported joints without
            # inventing a joint mapping for those other transmissions.
            continue
        joint = int(model.actuator_trnid[index, 0])
        if int(model.jnt_type[joint]) not in (
            int(mujoco.mjtJoint.mjJNT_HINGE),
            int(mujoco.mjtJoint.mjJNT_SLIDE),
        ):
            continue
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint)
        if not name or name in names:
            continue
        names.append(name)
        joints.append(joint)
    return names, joints


def _reference(model: mujoco.MjModel, joints: list[int]) -> np.ndarray:
    data = mujoco.MjData(model)
    if model.nkey:
        mujoco.mj_resetDataKeyframe(model, data, 0)
    else:
        mujoco.mj_resetData(model, data)
    return np.array(
        [float(data.qpos[int(model.jnt_qposadr[j])]) for j in joints],
        dtype=np.float64,
    )


def _amplitude(model: mujoco.MjModel, joints: list[int], rest: np.ndarray) -> np.ndarray:
    values = []
    for joint, centre in zip(joints, rest, strict=True):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, joint).lower()
        scale = (
            0.21
            if any(
                token in name
                for token in ("hip", "thigh", "shoulder", "upper", "elbow", "knee", "arm")
            )
            else 0.13
        )
        if "finger" in name or "gripper" in name:
            scale = 0.012
        if int(model.jnt_type[joint]) == int(mujoco.mjtJoint.mjJNT_SLIDE):
            scale = 0.035
        if bool(model.jnt_limited[joint]):
            low, high = [float(v) for v in model.jnt_range[joint]]
            scale = min(scale, max(0.0, (centre - low) * 0.75), max(0.0, (high - centre) * 0.75))
        values.append(scale)
    return np.asarray(values, dtype=np.float64)


def _joint_clip(model: mujoco.MjModel, mode: str) -> tuple[np.ndarray, list[str], np.ndarray]:
    names, joints = _transmissions(model)
    if not names:
        raise ValueError("no supported driven joints")
    rest = _reference(model, joints)
    amplitudes = _amplitude(model, joints, rest)
    t = np.arange(FRAMES, dtype=np.float64) / RATE
    cycle = 2 * np.pi * t / (FRAMES / RATE)
    phase = np.array([(i % 5) * 0.43 for i in range(len(joints))])
    if mode == "hold":
        wave = np.zeros((FRAMES, len(joints)), dtype=np.float64)
    elif mode == "articulation":
        wave = np.sin(cycle[:, None] + phase[None, :]) * np.sin(cycle[:, None] / 2)
    else:
        wave = np.sin(2 * cycle[:, None] + phase[None, :]) * 0.72
        wave += np.sin(cycle[:, None] + 0.67 * phase[None, :]) * 0.28
    targets = rest[None, :] + amplitudes[None, :] * wave
    # Normalized residual actions. The runtime's actual MuJoCo joint PD
    # controller applies these targets around the model keyframe pose.
    actions = (targets - rest[None, :]) / 0.35
    if not np.isfinite(actions).all() or np.max(np.abs(actions)) > 1.01:
        raise ValueError("joint motion dataset exceeded normalized action limits")
    return actions.astype(np.float32), names, rest


def _drone_clip(model: mujoco.MjModel, mode: str) -> tuple[np.ndarray, list[str], np.ndarray]:
    if model.nu != 4:
        raise ValueError("Crazyflie expected four site-thrust/moment actuators")
    names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)]
    if names != ["body_thrust", "x_moment", "y_moment", "z_moment"]:
        raise ValueError("Crazyflie motor order does not match official model")
    # This is sourced from the official 'hover' keyframe; recorded as real
    # thrust in Newtons, not a guaranteed tracking/flight capability.
    hover = np.asarray(model.key_ctrl[0], dtype=np.float64)
    if not (0.24 < hover[0] < 0.29):
        raise ValueError("Unexpected Crazyflie hover keyframe")
    t = np.arange(FRAMES, dtype=np.float64) / RATE
    cycle = 2 * np.pi * t / (FRAMES / RATE)
    output = np.tile(hover, (FRAMES, 1))
    if mode == "hold":
        return output.astype(np.float32), names, hover
    output[:, 0] += 0.025 * np.sin(cycle)
    output[:, 1] += 0.12 * np.sin(cycle * (1 if mode == "articulation" else 2))
    output[:, 2] += 0.10 * np.cos(cycle)
    output[:, 3] += 0.045 * np.sin(cycle * 2)
    for i in range(model.nu):
        if model.actuator_ctrllimited[i]:
            low, high = model.actuator_ctrlrange[i]
            output[:, i] = np.clip(output[:, i], low, high)
    return output.astype(np.float32), names, hover


def _other_motor_clip(model: mujoco.MjModel, mode: str) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Fallback for free-body motor-only models without hinge transmissions."""
    if model.nu < 1:
        raise ValueError("robot has no actuators for physical motion")
    names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        for i in range(model.nu)
    ]
    if not all(names):
        raise ValueError("non-joint actuator is unnamed")
    reference = (
        np.asarray(model.key_ctrl[0], dtype=np.float64)
        if model.nkey else np.zeros(model.nu, dtype=np.float64)
    )
    t = np.arange(FRAMES, dtype=np.float64) / RATE
    cycle = 2 * np.pi * t / (FRAMES / RATE)
    output = np.tile(reference, (FRAMES, 1))
    if mode != "hold":
        for i in range(model.nu):
            wave = np.sin(cycle * (1 if mode == "articulation" else 2) + i * 0.7)
            scale = 0.06 if model.actuator_ctrllimited[i] else 0.02
            if model.actuator_ctrllimited[i]:
                low, high = model.actuator_ctrlrange[i]
                scale = min(scale, 0.1 * (high - low))
            output[:, i] += scale * wave
    for i in range(model.nu):
        if model.actuator_ctrllimited[i]:
            low, high = model.actuator_ctrlrange[i]
            output[:, i] = np.clip(output[:, i], low, high)
    return output.astype(np.float32), names, reference


def _onnx_table(actions: np.ndarray) -> onnx.ModelProto:
    count, width = actions.shape
    node = [
        helper.make_node("Cast", ["time_step"], ["p37_index_int"], to=TensorProto.INT64),
        helper.make_node("Reshape", ["p37_index_int", "p37_flat_shape"], ["p37_step"]),
        helper.make_node("Mod", ["p37_step", "p37_count"], ["p37_frame"], fmod=0),
        helper.make_node("Gather", ["p37_actions", "p37_frame"], ["action"], axis=0),
    ]
    graph = helper.make_graph(
        node,
        "P37_model_motion_dataset_replay",
        [helper.make_tensor_value_info("time_step", TensorProto.FLOAT, [1, 1])],
        [helper.make_tensor_value_info("action", TensorProto.FLOAT, [1, width])],
        [
            helper.make_tensor("p37_flat_shape", TensorProto.INT64, [1], [1]),
            helper.make_tensor("p37_count", TensorProto.INT64, [1], [count]),
            helper.make_tensor("p37_actions", TensorProto.FLOAT, [count, width], actions.flatten()),
        ],
    )
    model = helper.make_model(
        graph,
        opset_imports=[helper.make_opsetid("", 18)],
        producer_name="Ontos P37 model-derived motion library",
    )
    model.ir_version = 9
    onnx.checker.check_model(model)
    return model


def create_motion(model: mujoco.MjModel, robot_id: str, mode: str, out: Path) -> dict:
    if mode not in MODES:
        raise ValueError("unsupported motion")
    if robot_id == "crazyflie_2":
        actions, names, rest = _drone_clip(model, mode)
        action_kind = "motor_effort"
    elif any(
        int(model.actuator_trntype[i]) != int(mujoco.mjtTrn.mjTRN_JOINT)
        for i in range(model.nu)
    ):
        # Mixed tendon/site/joint bodies need native actuator-level control.
        # Avoid an incomplete joint index, which silently moves the wrong motor.
        actions, names, rest = _other_motor_clip(model, mode)
        action_kind = "motor_effort"
    else:
        actions, names, rest = _joint_clip(model, mode)
        action_kind = "joint_position"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / f"{robot_id}-{mode}.npz",
        actions=actions,
        reference=rest.astype(np.float32),
        actuator_names=np.asarray(names),
        time_s=np.arange(FRAMES, dtype=np.float32) / RATE,
    )
    onnx_path = out / f"{robot_id}-{mode}.onnx"
    onnx.save(_onnx_table(actions), str(onnx_path))
    return {
        "robot_id": robot_id,
        "id": mode,
        "name": {
            "articulation": "Motor articulation",
            "motion_cycle": "Movement cycle",
            "hold": "Hold position",
        }[mode],
        "source": "model-derived sampled actuator trajectory",
        "source_model": "Google DeepMind MuJoCo Menagerie",
        "is_teleoperation_or_recorded_demonstration": False,
        "is_learned_p37_policy": False,
        "is_qualified_locomotion": False,
        "physics_control": action_kind,
        "control_hz": RATE,
        "frames": FRAMES,
        "duration_s": FRAMES / RATE,
        "actuators": len(names),
        "actuator_or_joint_names": names,
        "onnx_sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        "dataset_file": f"{robot_id}-{mode}.npz",
    }


def create_library(menagerie: Path, robots, output: Path) -> dict:
    index = {"schema_version": 1, "kind": "p37_model_derived_motions", "motions": {}}
    for robot in robots:
        print(f"Building model-compatible motion dataset: {robot.id}", flush=True)
        model = mujoco.MjModel.from_xml_path(str(menagerie / robot.model / "scene.xml"))
        index["motions"][robot.id] = [
            create_motion(model, robot.id, mode, output) for mode in MODES
        ]
    (output / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index
