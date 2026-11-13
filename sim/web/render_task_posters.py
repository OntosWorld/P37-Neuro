"""Produce truthful task gallery covers from actual MuJoCo Menagerie geometry.

This renderer loads the very same MJCF robot and contact scene used in the
interactive simulator. Panda's cover captures a real motor-controlled lift
frame, never a posed or composited fake. Images are previews only; the user
opens the live physics viewer from the gallery.

Run with MUJOCO_GL=osmesa on Linux for software offscreen rendering.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image

from build_mjswan import _light_scene, _task_checkpoint
from catalog import ROBOTS, RobotScene
from panda_physical_stack import initial_data, simulate
from physical_task_scenes import add_physical_task_scene

WIDTH = 1080
HEIGHT = 700


def _model(menagerie: Path, robot: RobotScene) -> mujoco.MjModel:
    path = menagerie / robot.model / "scene.xml"
    if not path.is_file():
        raise FileNotFoundError(f"Manufacturer model missing: {path}")
    spec = mujoco.MjSpec.from_file(str(path))
    _light_scene(spec, robot)
    _task_checkpoint(spec, robot)
    add_physical_task_scene(spec, robot.id)
    model = spec.compile()
    model.vis.global_.offwidth = WIDTH
    model.vis.global_.offheight = HEIGHT
    return model


def _panda_lift_frame(model: mujoco.MjModel) -> mujoco.MjData:
    actions, record = simulate(model)
    if not record["report"]["success"]:
        raise RuntimeError("Refusing to render unqualified Panda manipulation as a task")
    data = initial_data(model)
    # 9.0 s is during the real native lift/carry. Each motor sample advances
    # actual physics, contact and gravity. Cube qpos is never set by the poster.
    count = min(round(9.0 * 50), len(actions))
    substeps = max(1, round((1.0 / 50) / model.opt.timestep))
    for frame in actions[:count]:
        data.ctrl[:] = frame
        for _ in range(substeps):
            mujoco.mj_step(model, data)
    blue = data.xpos[model.body("p37_stack_blue").id]
    if blue[2] < 0.66:
        raise RuntimeError("Panda preview must show a real physically lifted cube")
    return data


def _camera(robot: RobotScene) -> mujoco.MjvCamera:
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = robot.camera
    camera.distance = robot.distance
    camera.azimuth = robot.azimuth
    camera.elevation = robot.elevation
    if robot.id == "franka_panda":
        camera.lookat[:] = [0.49, -0.02, 0.66]
        camera.distance = 1.72
        camera.azimuth = -135
        camera.elevation = -23
    if robot.id in ("unitree_go2", "anymal_c"):
        camera.lookat[:] = [0.38, 0.0, 0.38]
        camera.distance = 2.55
        camera.azimuth = -132
        camera.elevation = -18
    if robot.id == "hello_robot_stretch":
        camera.lookat[:] = [0.25, -0.10, 0.66]
        camera.distance = 2.85
    return camera


def render(menagerie: Path, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    provenance = {
        "format": "p37-native-mujoco-task-posters",
        "generated_from": "google-deepmind/mujoco_menagerie",
        "engine": "mujoco",
        "robot_count": len(ROBOTS),
        "posters": [],
    }
    for robot in ROBOTS:
        model = _model(menagerie, robot)
        if robot.id == "franka_panda":
            data = _panda_lift_frame(model)
        else:
            data = mujoco.MjData(model)
            mujoco.mj_resetData(model, data)
            if model.nkey > 0:
                mujoco.mj_resetDataKeyframe(model, data, 0)
            mujoco.mj_forward(model, data)
        with mujoco.Renderer(model, width=WIDTH, height=HEIGHT) as renderer:
            renderer.update_scene(data, camera=_camera(robot))
            pixels = renderer.render().copy()
        if pixels.shape != (HEIGHT, WIDTH, 3) or pixels.dtype != np.uint8:
            raise RuntimeError(f"Renderer produced invalid image for {robot.id}")
        poster = destination / f"{robot.id}.webp"
        Image.fromarray(pixels).save(poster, "WEBP", quality=86, method=5)
        if poster.stat().st_size < 7000:
            raise RuntimeError(f"Native poster suspiciously small: {robot.id}")
        provenance["posters"].append({
            "robot_id": robot.id,
            "filename": poster.name,
            "model": robot.model + "/scene.xml",
            "width": WIDTH,
            "height": HEIGHT,
            "pixels_from_native_renderer": True,
            "panda_lift_frame_from_actual_motors": robot.id == "franka_panda",
        })
        print(f"POSTER {robot.id}: {poster.stat().st_size:,} bytes", flush=True)
    (destination / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.menagerie, args.output), indent=2))


if __name__ == "__main__":
    main()
