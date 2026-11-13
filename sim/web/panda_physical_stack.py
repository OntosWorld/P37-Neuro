"""Deterministic Panda pick/lift/place task using native MuJoCo contact dynamics.

All cube motion is caused by the Menagerie Panda's motor-driven fingers and
collisions. The generator never edits cube qpos after reset, welds cubes to the
gripper, or substitutes a visual animation. A trace may be advertised as a
completed physical task ONLY after both simulation and independent playback
pass the contact, lift, release, and settled placement checks.

This is a scripted reference controller, not a P37 learned policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import mujoco
import numpy as np
from physical_task_scenes import add_physical_task_scene
from scipy.spatial.transform import Rotation

RATE = 50
CONTROL_DT = 1.0 / RATE
TIP_LOCAL = np.array([0.0, 0.0, 0.103])
HAND_TARGET_ROT = Rotation.from_euler("xyz", [math.pi, 0.0, 0.0])
SOURCE = np.array([0.45, -0.16, 0.57])
DESTINATION = np.array([0.53, 0.12, 0.63])


def load_model(menagerie: Path) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(menagerie / "franka_emika_panda" / "scene.xml"))
    add_physical_task_scene(spec, "franka_panda")
    return spec.compile()


def initial_data(model: mujoco.MjModel) -> mujoco.MjData:
    data = mujoco.MjData(model)
    mujoco.mj_resetData(model, data)
    if model.nkey:
        # Preserve newly added cube free-joint initial poses from qpos0.
        for i in range(1, 8):
            addr = int(model.joint(f"joint{i}").qposadr[0])
            data.qpos[addr] = model.key_qpos[0, addr]
        for name in ("finger_joint1", "finger_joint2"):
            adr = int(model.joint(name).qposadr[0])
            data.qpos[adr] = 0.04
    data.ctrl[:7] = np.array([data.qpos[model.joint(f"joint{i}").qposadr[0]]
                              for i in range(1, 8)])
    data.ctrl[7] = 255.0
    mujoco.mj_forward(model, data)
    return data


def panda_coords(model: mujoco.MjModel) -> tuple[np.ndarray, np.ndarray, int]:
    q = np.array([model.joint(f"joint{i}").qposadr[0] for i in range(1, 8)], dtype=int)
    dof = np.array([model.joint(f"joint{i}").dofadr[0] for i in range(1, 8)], dtype=int)
    return q, dof, model.body("hand").id


def tool_pose(data: mujoco.MjData, body_id: int) -> tuple[np.ndarray, Rotation]:
    matrix = data.xmat[body_id].reshape(3, 3)
    return data.xpos[body_id] + matrix @ TIP_LOCAL, Rotation.from_matrix(matrix)


def solve_ik(
    model: mujoco.MjModel,
    working: mujoco.MjData,
    q_seed: np.ndarray,
    position: np.ndarray,
    *,
    iterations: int = 450,
) -> tuple[np.ndarray, float, float]:
    qs, dofs, hand = panda_coords(model)
    working.qpos[qs] = q_seed
    low = np.array([model.jnt_range[model.joint(f"joint{i}").id, 0]
                    for i in range(1, 8)]) + 0.025
    high = np.array([model.jnt_range[model.joint(f"joint{i}").id, 1]
                     for i in range(1, 8)]) - 0.025
    jpos = np.zeros((3, model.nv))
    jrot = np.zeros((3, model.nv))
    err_p = float("inf")
    err_r = float("inf")
    for _ in range(iterations):
        mujoco.mj_forward(model, working)
        tip, orientation = tool_pose(working, hand)
        delta = position - tip
        # Enforce tool pointing downward while allowing free wrist yaw.
        # The z-axis constraint avoids singularity at far lateral targets.
        tool_z = orientation.apply([0.0, 0.0, 1.0])
        angular = np.cross(tool_z, [0.0, 0.0, -1.0])
        err_p, err_r = np.linalg.norm(delta), np.linalg.norm(angular)
        if err_p < 0.004 and err_r < 0.07:
            break
        mujoco.mj_jac(model, working, jpos, jrot, tip, hand)
        jacobian = np.vstack((jpos[:, dofs], jrot[:, dofs]))
        residual = np.concatenate((delta, angular * 0.46))
        weighted = jacobian.copy()
        weighted[3:] *= 0.46
        lhs = weighted @ weighted.T + np.diag([0.003] * 3 + [0.015] * 3)
        step = weighted.T @ np.linalg.solve(lhs, residual)
        step = np.clip(step * 0.65, -0.075, 0.075)
        working.qpos[qs] = np.clip(working.qpos[qs] + step, low, high)
    return working.qpos[qs].copy(), float(err_p), float(err_r)


def contact_flags(model: mujoco.MjModel, data: mujoco.MjData) -> tuple[bool, bool, bool]:
    blue = model.body("p37_stack_blue").id
    amber = model.body("p37_stack_amber").id
    left = model.body("left_finger").id
    right = model.body("right_finger").id
    hits_left = hits_right = stack_contact = False
    for i in range(data.ncon):
        c = data.contact[i]
        b1 = int(model.geom_bodyid[c.geom1])
        b2 = int(model.geom_bodyid[c.geom2])
        pair = {b1, b2}
        hits_left |= pair == {left, blue}
        hits_right |= pair == {right, blue}
        stack_contact |= pair == {blue, amber}
    return hits_left, hits_right, stack_contact


def _cube_state(model: mujoco.MjModel, data: mujoco.MjData, name: str) -> np.ndarray:
    return np.asarray(data.xpos[model.body(name).id]).copy()


def _waypoints() -> list[tuple[str, np.ndarray, float, float]]:
    src, dst = SOURCE, DESTINATION
    return [
        ("settle", src + np.array([0, 0, 0.20]), 255.0, 0.6),
        ("approach", src + np.array([0, 0, 0.19]), 255.0, 2.4),
        ("descend", src.copy(), 255.0, 2.0),
        ("grasp", src.copy(), 0.0, 1.5),
        ("lift", src + np.array([0, 0, 0.22]), 0.0, 2.4),
        ("carry", dst + np.array([0, 0, 0.18]), 0.0, 2.6),
        ("place", dst.copy(), 0.0, 1.9),
        ("release", dst.copy(), 255.0, 1.6),
        ("retreat", dst + np.array([0, 0, 0.20]), 255.0, 1.7),
        ("verify", dst + np.array([0, 0, 0.20]), 255.0, 1.5),
    ]


def simulate(
    model: mujoco.MjModel,
    *,
    reference_controls: np.ndarray | None = None,
) -> tuple[np.ndarray, dict]:
    data = initial_data(model)
    qs, _dofs, hand = panda_coords(model)
    finger = model.joint("finger_joint1").qposadr[0]
    targets: list[tuple[str, np.ndarray, float, float]] = []
    ik_diagnostics = []
    if reference_controls is None:
        scratch = initial_data(model)
        seed = data.qpos[qs].copy()
        for name, position, gripper, duration in _waypoints():
            if name not in {"settle", "grasp", "release", "verify"}:
                seed, err_p, err_r = solve_ik(model, scratch, seed, position)
            else:
                err_p = err_r = 0.0
            targets.append((name, seed.copy(), gripper, duration))
            ik_diagnostics.append({
                "phase": name, "position_error": round(err_p, 4),
                "rotation_error": round(err_r, 4)
            })
        print("IK", json.dumps(ik_diagnostics), flush=True)
    else:
        if reference_controls.ndim != 2 or reference_controls.shape[1] != 8:
            raise ValueError("expected eight real Panda motor controls")
        if not np.isfinite(reference_controls).all():
            raise ValueError("nonfinite source motor commands")

    substeps = max(1, round(CONTROL_DT / model.opt.timestep))
    controls: list[np.ndarray] = []
    events: list[dict] = []
    stage_results = []
    grasp_contact = 0
    left_frames = right_frames = 0
    recent_left = recent_right = 0
    lifted = False
    released = False
    settled = 0
    arm_origin = data.qpos[qs].copy()
    jaw_origin = float(data.ctrl[7])
    frame_id = 0
    segments = targets if reference_controls is None else [
        ("replay", np.zeros(7), 0.0, len(reference_controls) * CONTROL_DT)
    ]
    for phase, q_goal, grip_goal, duration in segments:
        frames = max(1, round(duration * RATE))
        for frame in range(frames):
            p = (frame + 1) / frames
            alpha = p * p * (3 - 2 * p)
            if reference_controls is None:
                cmd = np.concatenate([
                    arm_origin + alpha * (q_goal - arm_origin),
                    [jaw_origin + alpha * (grip_goal - jaw_origin)]
                ])
            else:
                cmd = reference_controls[frame_id]
            data.ctrl[:] = cmd
            for _ in range(substeps):
                mujoco.mj_step(model, data)
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise RuntimeError(f"nonfinite physics state in {phase} frame {frame_id}")
            blue = _cube_state(model, data, "p37_stack_blue")
            amber = _cube_state(model, data, "p37_stack_amber")
            left, right, on_stack = contact_flags(model, data)
            left_frames += int(left)
            right_frames += int(right)
            recent_left = min(12, recent_left + 1) if left else max(0, recent_left - 1)
            recent_right = min(12, recent_right + 1) if right else max(0, recent_right - 1)
            closed_contact = (recent_left >= 2 and recent_right >= 2
                              and float(data.qpos[finger]) < 0.034)
            if closed_contact:
                grasp_contact += 1
            if (grasp_contact >= 5 and blue[2] > 0.66
                and phase in ("lift", "carry", "place", "release", "replay")):
                lifted = True
            if (grasp_contact >= 5 and lifted and float(data.qpos[finger]) > 0.033
                and not left and not right):
                released = True
            offset = float(np.linalg.norm(blue[:2] - amber[:2]))
            dz = float(blue[2] - amber[2])
            stable = (
                on_stack and released and 0.052 <= dz <= 0.085
                and offset <= 0.051
                and float(np.linalg.norm(data.qvel[-6:])) < 0.12
            )
            settled = settled + 1 if stable else 0
            controls.append(np.asarray(cmd, dtype=np.float32).copy())
            events.append({
                "time": round(float(data.time), 3),
                "phase": phase,
                "blue_xyz": [round(float(v), 4) for v in blue],
                "amber_xyz": [round(float(v), 4) for v in amber],
                "finger_qpos": round(float(data.qpos[finger]), 4),
                "finger_contacts": [left, right],
                "cube_contact": on_stack,
                "lift_observed": lifted,
                "release_observed": released,
                "settled": settled >= 12,
            })
            frame_id += 1
        arm_origin = data.qpos[qs].copy()
        jaw_origin = float(data.ctrl[7])
        stage_results.append({
            "phase": phase,
            "blue": events[-1]["blue_xyz"],
            "tool": [round(float(v), 3) for v in tool_pose(data, hand)[0]],
            "grip": events[-1]["finger_qpos"],
            "two_finger_frames": grasp_contact,
            "left_contact_frames": left_frames,
            "right_contact_frames": right_frames,
            "lifted": lifted,
            "released": released,
            "settled_frames": settled,
        })
    result = {
        "engine": "mujoco",
        "source_robot": "google-deepmind/mujoco_menagerie/franka_emika_panda",
        "controller": "deterministic_cartesian_ik_joint_position_reference",
        "is_learned_p37_policy": False,
        "frames": len(controls),
        "control_hz": RATE,
        "contact_grasp_observed": grasp_contact >= 5,
        "left_contact_frames": left_frames,
        "right_contact_frames": right_frames,
        "lift_observed": lifted,
        "release_observed": released,
        "stable_stack_observed": settled >= 12,
        "success": grasp_contact >= 5 and lifted and released and settled >= 12,
        "phases": stage_results,
        "end_state": events[-1],
    }
    return np.asarray(controls, dtype=np.float32), {"report": result, "events": events}


def run(menagerie: Path, output: Path, *, require_success: bool) -> dict:
    model = load_model(menagerie)
    actions, record = simulate(model)
    output.mkdir(parents=True, exist_ok=True)
    (output / "panda-physical-task-diagnostics.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print("RESULT", json.dumps(record["report"], indent=2), flush=True)
    if record["report"]["success"]:
        replay_actions, replay = simulate(load_model(menagerie), reference_controls=actions)
        if not np.array_equal(actions, replay_actions) or not replay["report"]["success"]:
            raise RuntimeError("Physical task rollout did not reproduce under exact controls")
        digest = hashlib.sha256(actions.tobytes()).hexdigest()
        np.savez_compressed(output / "panda-physical-stack.npz", actions=actions)
        info = {
            "task": "panda-physical-cube-stack",
            "controller": record["report"]["controller"],
            "frames": len(actions),
            "control_hz": RATE,
            "sha256": digest,
            "source": record["report"]["source_robot"],
            "learned_policy": False,
            "native_physics_verified": True,
            "contact_grasp_observed": True,
            "lift_observed": True,
            "release_observed": True,
            "stable_stack_observed": True,
            "replay_verified": True,
        }
        (output / "panda-physical-stack.json").write_text(
            json.dumps(info, indent=2) + "\n", encoding="utf-8"
        )
        return info
    if require_success:
        raise RuntimeError("Panda controller failed physical grasp/lift/release/stack checks")
    return record["report"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-success", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.menagerie, args.output, require_success=args.require_success),
                     indent=2))


if __name__ == "__main__":
    main()
