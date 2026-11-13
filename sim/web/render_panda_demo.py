"""Render the independently validated native Panda task to a public video.

Frames are rendered from the SAME eight actuator controls that passed contact,
lift, release, settled placement, negative control, and replay qualification.
The cube poses are never manually set during the rollout. This cinematic
recording is scripted MuJoCo physics, never a P37 learned policy.

Requires: MUJOCO_GL=osmesa, FFmpeg, libosmesa6; output video is fail-closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import mujoco
import numpy as np
from build_mjswan import _light_scene
from catalog import ROBOTS
from panda_physical_stack import CONTROL_DT, RATE, initial_data, simulate
from physical_task_scenes import add_physical_task_scene

FPS = 25
WIDTH = 960
HEIGHT = 540


def render(menagerie: Path, controls: Path, qualification: Path, video: Path, poster: Path) -> dict:
    evidence = json.loads(qualification.read_text(encoding="utf-8"))
    for key in (
        "native_physics_verified",
        "contact_grasp_observed",
        "lift_observed",
        "release_observed",
        "stable_stack_observed",
        "replay_verified",
        "open_jaw_negative_control_failed",
    ):
        if evidence.get(key) is not True:
            raise RuntimeError(f"Refusing to render an unqualified task: {key}")

    with np.load(controls, allow_pickle=False) as record:
        actions = np.asarray(record["actions"], dtype=np.float32)
    digest = hashlib.sha256(actions.tobytes()).hexdigest()
    if digest != evidence.get("sha256"):
        raise RuntimeError("Physical task recording does not match its qualified SHA-256")
    if actions.ndim != 2 or actions.shape[1] != 8 or len(actions) < 500:
        raise RuntimeError("Incomplete Panda motor sequence")

    # Mirror the public robot viewer's graphite lighting; these light/texture
    # edits and non-colliding reference markers do NOT alter Panda dynamics.
    spec = mujoco.MjSpec.from_file(str(menagerie / "franka_emika_panda" / "scene.xml"))
    panda = next(robot for robot in ROBOTS if robot.id == "franka_panda")
    _light_scene(spec, panda)
    add_physical_task_scene(spec, "franka_panda")
    model = spec.compile()
    # The fluorescent ring is a debug waypoint, not part of the task object.
    # Hide it in the film without editing its model collision properties.
    ring_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "p37_stack_target")
    if ring_id >= 0:
        model.geom_rgba[ring_id, 3] = 0
    if model.nu != 8:
        raise RuntimeError("Expected eight actual Panda actuators")
    # Re-run the measured contact predicates in this exact rendered model.
    # Visual staging must never invalidate the successful physical rollout.
    _, rendered_trial = simulate(model, reference_controls=actions)
    if not rendered_trial["report"]["success"]:
        raise RuntimeError("Styled Panda film no longer reproduces physical task completion")
    model.vis.global_.offwidth = WIDTH
    model.vis.global_.offheight = HEIGHT
    data = initial_data(model)

    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(camera)
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = [0.50, 0.0, 0.65]
    camera.distance = 1.37
    camera.azimuth = 126
    camera.elevation = -24

    video.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{WIDTH}x{HEIGHT}",
            "-framerate",
            str(FPS),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if ffmpeg.stdin is None:
        raise RuntimeError("FFmpeg did not start")

    substeps = max(1, round(CONTROL_DT / model.opt.timestep))
    rendered = 0
    interval = RATE // FPS
    try:
        with mujoco.Renderer(model, height=HEIGHT, width=WIDTH) as renderer:
            for idx, action in enumerate(actions):
                data.ctrl[:] = action
                for _ in range(substeps):
                    mujoco.mj_step(model, data)
                if not np.isfinite(data.qpos).all():
                    raise RuntimeError("Nonfinite native object state while rendering")
                if idx % interval == 0:
                    renderer.update_scene(data, camera=camera)
                    ffmpeg.stdin.write(renderer.render().tobytes())
                    rendered += 1
    finally:
        ffmpeg.stdin.close()
    stderr = ffmpeg.stderr.read().decode("utf-8", "replace") if ffmpeg.stderr else ""
    if ffmpeg.wait(timeout=90) != 0:
        raise RuntimeError(f"Failed to render Panda video: {stderr[-600:]}")
    if rendered < 350 or not video.exists() or video.stat().st_size < 100_000:
        raise RuntimeError("Panda video is missing or incomplete")

    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "10",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-vf",
            "scale=960:540",
            str(poster),
        ],
        check=True,
    )
    if not poster.is_file() or poster.stat().st_size < 15_000:
        raise RuntimeError("Task poster frame was not rendered")

    report = {
        "robot": "franka_panda",
        "task": "physical_cube_stack",
        "engine": "MuJoCo",
        "controller": "deterministic_scripted_motor_reference",
        "source_sha256": digest,
        "learned_p37_policy": False,
        "native_physics_verified": True,
        "negative_control_passed": True,
        "frames": rendered,
        "fps": FPS,
        "duration_seconds": round(rendered / FPS, 2),
        "video_bytes": video.stat().st_size,
        "video": video.name,
        "poster": poster.name,
    }
    (video.parent / "panda-cube-stack-video.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--poster", type=Path, required=True)
    args = parser.parse_args()
    render(args.menagerie, args.controls, args.qualification, args.video, args.poster)


if __name__ == "__main__":
    main()
