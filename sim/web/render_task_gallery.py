"""Capture the actual task scenes for the public task-first gallery.

Images are *rendered from the same manufacturer-derived MuJoCo geometries and
physical task environments* used in the browser. Panda frames are captured
after replaying the real qualified contact/grasp motor controls, not a dummy
animation. This script fails the site build if rendering is unavailable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

from build_mjswan import _light_scene, _task_checkpoint
from catalog import ROBOTS
from panda_physical_stack import initial_data
from physical_task_scenes import add_physical_task_scene

WIDTH = 960
HEIGHT = 600

VIEWS = {
    "panda-stack": ("franka_panda", [0.52, -0.02, 0.61], 1.82, 136, -24),
    "panda-recorded": ("franka_panda", [0.51, 0.01, 0.59], 1.88, 136, -26),
    "go2-terrain": ("unitree_go2", [0.64, -0.02, 0.23], 3.18, 127, -20),
    "anymal-terrain": ("anymal_c", [0.68, 0.00, 0.30], 3.25, 124, -22),
    "stretch-delivery": ("hello_robot_stretch", [0.25, 0.22, 0.62], 3.0, 136, -21),
    "g1-policy": ("unitree_g1", [0, 0, 0.90], 3.20, 128, -12),
}


def _render(model: mujoco.MjModel, data: mujoco.MjData, target: Path, view: tuple) -> None:
    _robot, lookat, distance, azimuth, elevation = view
    model.vis.global_.offwidth = max(WIDTH, int(model.vis.global_.offwidth))
    model.vis.global_.offheight = max(HEIGHT, int(model.vis.global_.offheight))
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = lookat
    camera.distance = distance
    camera.azimuth = azimuth
    camera.elevation = elevation
    renderer = mujoco.Renderer(model, width=WIDTH, height=HEIGHT)
    try:
        renderer.update_scene(data, camera=camera)
        pixels = renderer.render()
        if pixels.shape != (HEIGHT, WIDTH, 3):
            raise RuntimeError("Unexpected real MuJoCo camera buffer dimensions")
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(pixels).save(target, format="JPEG", quality=90, optimize=True)
    finally:
        renderer.close()


def _model(menagerie: Path, robot_id: str) -> mujoco.MjModel:
    robot = next(robot for robot in ROBOTS if robot.id == robot_id)
    spec = mujoco.MjSpec.from_file(str(menagerie / robot.model / "scene.xml"))
    _light_scene(spec, robot)
    _task_checkpoint(spec, robot)
    add_physical_task_scene(spec, robot_id)
    return spec.compile()


def _panda_frames(
    model: mujoco.MjModel,
    controls: np.ndarray,
) -> dict[str, mujoco.MjData]:
    if controls.ndim != 2 or controls.shape[1] != 8 or len(controls) < 880:
        raise ValueError("Physically qualified Panda motor trace is missing or corrupt")
    snapshots: dict[str, mujoco.MjData] = {}
    data = initial_data(model)
    substeps = round((1.0 / 50.0) / float(model.opt.timestep))
    for frame in range(len(controls)):
        data.ctrl[:] = controls[frame]
        for _ in range(substeps):
            mujoco.mj_step(model, data)
        if frame == 385:
            snapshot = mujoco.MjData(model)
            mujoco.mj_copyData(snapshot, model, data)
            snapshots["panda-stack"] = snapshot
        if frame == len(controls) - 1:
            snapshot = mujoco.MjData(model)
            mujoco.mj_copyData(snapshot, model, data)
            snapshots["panda-recorded"] = snapshot
    if set(snapshots) != {"panda-stack", "panda-recorded"}:
        raise RuntimeError("Qualified Panda task did not reach capture checkpoints")
    return snapshots


def build(menagerie: Path, actions: Path, output: Path) -> dict:
    with np.load(actions, allow_pickle=False) as recorded:
        controls = np.asarray(recorded["actions"], dtype=np.float64)
    report = {"renderer": "MuJoCo Python offscreen", "image_source": "manufacturer meshes",
              "scenes": []}
    for robot_id in ("franka_panda", "unitree_go2", "anymal_c", "hello_robot_stretch", "unitree_g1"):
        model = _model(menagerie, robot_id)
        if robot_id == "franka_panda":
            captures = _panda_frames(model, controls)
        else:
            data = mujoco.MjData(model)
            if model.nkey:
                mujoco.mj_resetDataKeyframe(model, data, 0)
            mujoco.mj_forward(model, data)
            task_key = next(key for key, value in VIEWS.items() if value[0] == robot_id)
            captures = {task_key: data}
        for key, capture in captures.items():
            target = output / f"{key}.jpg"
            _render(model, capture, target, VIEWS[key])
            if target.stat().st_size < 12_000:
                raise RuntimeError(f"Scene preview suspiciously small: {target}")
            report["scenes"].append({
                "task_id": key,
                "robot_id": robot_id,
                "file": target.name,
                "size_bytes": target.stat().st_size,
                "actual_mujoco_scene": True,
                "native_panda_motor_replay": robot_id == "franka_panda",
            })
    if len(report["scenes"]) != len(VIEWS):
        raise RuntimeError("Missing rendered physical task gallery scene")
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.menagerie, args.actions, args.output), indent=2))


if __name__ == "__main__":
    main()
