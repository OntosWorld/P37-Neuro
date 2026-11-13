"""Native MuJoCo Panda tabletop pick-and-place reference and replay qualification.

This is a deterministic controller, not a learned P37 policy. Cube motion must
result from gripper contact and collisions; no object teleports or welds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np

from panda_physical_stack import (
    RATE, CONTROL_DT, initial_data, panda_coords, solve_ik, tool_pose,
)
from physical_task_scenes import add_physical_task_scene

SOURCE = np.array([0.45, -0.16, 0.57])
TARGET = np.array([0.53, 0.12, 0.57])
CUBE = "p37_pick_cube"
BENCH = "p37_pick_bench"


def load_model(menagerie: Path) -> mujoco.MjModel:
    spec = mujoco.MjSpec.from_file(str(menagerie / "franka_emika_panda" / "scene.xml"))
    add_physical_task_scene(spec, "franka_pick_place")
    return spec.compile()


def _touching(model: mujoco.MjModel, data: mujoco.MjData, a: int, b: int) -> bool:
    for index in range(data.ncon):
        contact = data.contact[index]
        bodies = {int(model.geom_bodyid[contact.geom1]), int(model.geom_bodyid[contact.geom2])}
        if bodies == {a, b}:
            return True
    return False


def waypoints():
    s, t = SOURCE, TARGET
    return [
        ("settle", s + [0, 0, 0.20], 255.0, 0.6),
        ("approach", s + [0, 0, 0.19], 255.0, 2.4),
        ("descend", s.copy(), 255.0, 2.0),
        ("grasp", s.copy(), 0.0, 1.5),
        ("lift", s + [0, 0, 0.22], 0.0, 2.4),
        ("carry", t + [0, 0, 0.18], 0.0, 2.6),
        ("place", t.copy(), 0.0, 1.9),
        ("release", t.copy(), 255.0, 1.6),
        ("retreat", t + [0, 0, 0.20], 255.0, 1.7),
        ("verify", t + [0, 0, 0.20], 255.0, 1.5),
    ]


def simulate(model: mujoco.MjModel, reference_controls: np.ndarray | None = None):
    data = initial_data(model)
    q_addresses, _, hand = panda_coords(model)
    finger_address = int(model.joint("finger_joint1").qposadr[0])
    cube_body = model.body(CUBE).id
    bench_body = int(model.geom_bodyid[model.geom(BENCH).id])
    left_body = model.body("left_finger").id
    right_body = model.body("right_finger").id
    if reference_controls is not None:
        if (reference_controls.ndim != 2 or reference_controls.shape[1] != model.nu or
                not np.isfinite(reference_controls).all()):
            raise ValueError("Expected finite Panda actuator controls in native order")
    targets = []
    if reference_controls is None:
        scratch = initial_data(model)
        seed = data.qpos[q_addresses].copy()
        for phase, xyz, grip, duration in waypoints():
            if phase not in {"settle", "grasp", "release", "verify"}:
                seed, position_error, rotation_error = solve_ik(model, scratch, seed, xyz)
                if position_error > 0.025 or rotation_error > 0.22:
                    raise RuntimeError(f"Unsafe IK target in {phase}: {position_error}, {rotation_error}")
            targets.append((phase, seed.copy(), grip, duration))
    else:
        targets = [("replay", None, None, len(reference_controls) * CONTROL_DT)]

    substeps = max(1, round(CONTROL_DT / model.opt.timestep))
    controls = []
    left_frames = right_frames = two_finger_frames = 0
    recent_left = recent_right = 0
    lifted = transported = released = False
    stable_frames = 0
    q_origin = data.qpos[q_addresses].copy()
    grip_origin = float(data.ctrl[7])
    frame_id = 0
    last_event = {}
    for phase, q_goal, grip_goal, duration in targets:
        frames = max(1, round(duration * RATE))
        for frame in range(frames):
            if reference_controls is None:
                p = (frame + 1) / frames
                alpha = p * p * (3 - 2 * p)
                command = np.concatenate([
                    q_origin + alpha * (q_goal - q_origin),
                    [grip_origin + alpha * (grip_goal - grip_origin)],
                ])
            else:
                command = reference_controls[frame_id]
            data.ctrl[:] = command
            for _ in range(substeps):
                mujoco.mj_step(model, data)
            if not np.isfinite(data.qpos).all() or not np.isfinite(data.qvel).all():
                raise RuntimeError("Nonfinite physics state")
            cube = np.array(data.xpos[cube_body])
            left = _touching(model, data, left_body, cube_body)
            right = _touching(model, data, right_body, cube_body)
            on_bench = _touching(model, data, bench_body, cube_body)
            left_frames += int(left)
            right_frames += int(right)
            recent_left = min(12, recent_left + 1) if left else max(0, recent_left - 1)
            recent_right = min(12, recent_right + 1) if right else max(0, recent_right - 1)
            grasp = (recent_left >= 2 and recent_right >= 2 and
                     float(data.qpos[finger_address]) < 0.034)
            two_finger_frames += int(grasp)
            if two_finger_frames >= 5 and cube[2] > 0.66:
                lifted = True
            if lifted and cube[1] > 0.045 and cube[2] > 0.64 and grasp:
                transported = True
            open_jaw = float(data.qpos[finger_address]) > 0.033
            if transported and open_jaw and not left and not right:
                released = True
            distance = float(np.linalg.norm(cube[:2] - TARGET[:2]))
            free_joint = next(
                j for j in range(model.njnt)
                if int(model.jnt_bodyid[j]) == cube_body and
                model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE
            )
            dof = int(model.jnt_dofadr[free_joint])
            qvel = data.qvel[dof:dof + 6]
            settled = (released and on_bench and distance <= 0.055 and
                       0.565 <= cube[2] <= 0.605 and
                       float(np.linalg.norm(qvel)) < 0.12)
            stable_frames = stable_frames + 1 if settled else 0
            controls.append(np.asarray(command, dtype=np.float32).copy())
            last_event = {
                "time": round(float(data.time), 3),
                "phase": phase,
                "cube_xyz": [round(float(x), 5) for x in cube],
                "target_distance_m": round(distance, 5),
                "left_contact": left, "right_contact": right,
                "bench_contact": on_bench,
                "lifted": lifted, "transported": transported,
                "released": released, "stable_frames": stable_frames,
            }
            frame_id += 1
        q_origin = data.qpos[q_addresses].copy()
        grip_origin = float(data.ctrl[7])
    result = {
        "task": "panda-pick-place",
        "physics": "MuJoCo",
        "controller": "deterministic_cartesian_ik_reference",
        "learned_policy": False,
        "frames": len(controls),
        "control_hz": RATE,
        "contact_grasp_observed": two_finger_frames >= 5,
        "left_contact_frames": left_frames,
        "right_contact_frames": right_frames,
        "lift_observed": lifted,
        "transport_observed": transported,
        "release_observed": released,
        "stable_target_observed": stable_frames >= 12,
        "success": two_finger_frames >= 5 and lifted and transported and released and stable_frames >= 12,
        "end_state": last_event,
    }
    return np.asarray(controls, dtype=np.float32), result


def run(menagerie: Path, output: Path, *, require_success: bool = True):
    model = load_model(menagerie)
    if model.nu != 8 or [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i)
        for i in range(model.nu)
    ] != [f"actuator{i}" for i in range(1, 9)]:
        raise RuntimeError("Franka actuator ordering changed")
    actions, report = simulate(model)
    if not report["success"]:
        if require_success:
            raise RuntimeError("Pick/place failed native physical checks: " + json.dumps(report))
        return report
    replay_actions, replay = simulate(load_model(menagerie), reference_controls=actions)
    if not np.array_equal(actions, replay_actions) or not replay["success"]:
        raise RuntimeError("Recorded Panda controls failed independent replay")
    no_grasp_actions = actions.copy()
    no_grasp_actions[:, 7] = 255.0
    _, no_grasp = simulate(load_model(menagerie), reference_controls=no_grasp_actions)
    if no_grasp["contact_grasp_observed"] or no_grasp["success"]:
        raise RuntimeError("Open-jaw negative control incorrectly passed")
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(actions.tobytes()).hexdigest()
    np.savez_compressed(output / "panda-pick-place.npz", actions=actions)
    result = {
        **report,
        "sha256": digest,
        "native_physics_verified": True,
        "replay_verified": True,
        "open_jaw_negative_control_failed": True,
        "source": "google-deepmind/mujoco_menagerie/franka_emika_panda",
    }
    (output / "panda-pick-place.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-success", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.menagerie, args.output, require_success=args.require_success), indent=2))
