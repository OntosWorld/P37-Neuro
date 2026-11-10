"""Build physically simulated robot scenes with an editorial lab presentation.

This bundles true Menagerie MJCF geometry and MuJoCo WebAssembly. Styling
adds lights and non-colliding visual markers, never hidden locomotion scripts.
Only verified trained controllers may be attached as P37 policies.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mjswan
import mujoco
from catalog import ROBOTS, RobotScene, check_catalog
from demo_specs import DEMOS, decorate_task

ROOT = Path(__file__).resolve().parent


def _light_scene(spec: mujoco.MjSpec, robot: RobotScene) -> None:
    """Three practical light sources for legible white/black robot surfaces."""
    # All lights are non-physical presentation assets; dynamics are unchanged.
    # Recolor Menagerie's saturated blue procedural ground and sky into
    # neutral graphite. These are purely visual texture parameters.
    for texture in spec.textures:
        name = getattr(texture, "name", "")
        if name == "groundplane":
            texture.rgb1 = [0.22, 0.23, 0.25]
            texture.rgb2 = [0.19, 0.20, 0.22]
            texture.markrgb = [0.26, 0.28, 0.30]
        elif texture.type == mujoco.mjtTexture.mjTEXTURE_SKYBOX:
            texture.rgb1 = [0.22, 0.25, 0.28]
            texture.rgb2 = [0.07, 0.08, 0.10]
    spec.worldbody.add_light(
        name="p37_key",
        pos=[-3.8, -3.2, 5.5],
        dir=[0.65, 0.55, -1.0],
        diffuse=[0.70, 0.73, 0.78],
        specular=[0.24, 0.26, 0.29],
    )
    spec.worldbody.add_light(
        name="p37_fill",
        pos=[3.4, 2.3, 4.2],
        dir=[-0.65, -0.55, -1.0],
        diffuse=[0.38, 0.42, 0.48],
        specular=[0.09, 0.11, 0.14],
    )
    # Subtle static reference edges help place the robot in 3D.
    radius = 1.65 if robot.kind in ("Humanoids", "Quadrupeds") else 1.15
    color = [0.23, 0.29, 0.34, 0.60]
    for i, (x, y, sx, sy) in enumerate(
        (
            (-radius, 0, 0.012, radius),
            (radius, 0, 0.012, radius),
            (0, -radius, radius, 0.012),
            (0, radius, radius, 0.012),
        )
    ):
        spec.worldbody.add_geom(
            name=f"p37_marker_{i}",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[x, y, -0.005],
            size=[sx, sy, 0.004],
            rgba=color,
            contype=0,
            conaffinity=0,
        )


def build(menagerie: Path, base_path: str = "/simulator/") -> Path:
    check_catalog()
    menagerie = menagerie.resolve()
    if not menagerie.is_dir():
        raise FileNotFoundError(f"MuJoCo Menagerie checkout missing: {menagerie}")
    if not base_path.startswith("/") or not base_path.endswith("/"):
        raise ValueError("base_path must begin and end with '/'")

    builder = mjswan.Builder(
        base_path=base_path,
        license="Apache-2.0",
        copyright="2026 Ontos",
    )
    project = builder.add_project(name="P37 Robot Models", default=True)
    project.set_notice(
        "Real MuJoCo Menagerie models under their original licenses.\n"
        "Lab lights and reference markers are visual only.\n"
        "No trained P37 policy is attached in this build.\n"
        "Passive physics and user forces are not learned skills."
    )

    built_scenes = []
    for robot in ROBOTS:
        path = menagerie / robot.model / "scene.xml"
        if not path.is_file():
            raise FileNotFoundError(f"Missing physical robot model: {path}")
        spec = mujoco.MjSpec.from_file(str(path))
        _light_scene(spec, robot)
        scene = project.add_scene(spec=spec, name=robot.name)
        scene.set_viewer(
            mjswan.ViewerConfig(
                lookat=robot.camera,
                distance=robot.distance,
                elevation=robot.elevation,
                azimuth=robot.azimuth,
                origin_type=mjswan.ViewerConfig.OriginType.WORLD,
            )
        )
        built_scenes.append(robot.id)

    # Extra scenes are genuine physics experiments built from the *same*
    # official MJCF robot source as the gallery. They contain real obstacles,
    # collidable blocks, and free moving rigid bodies; no scripted outcomes.
    by_id = {robot.id: robot for robot in ROBOTS}
    for demo in DEMOS:
        robot = by_id[demo.robot_id]
        path = menagerie / robot.model / "scene.xml"
        spec = mujoco.MjSpec.from_file(str(path))
        _light_scene(spec, robot)
        decorate_task(spec, demo.id)
        scene = project.add_scene(spec=spec, name=demo.name)
        scene.set_viewer(
            mjswan.ViewerConfig(
                lookat=(
                    robot.camera[0] + 0.23,
                    robot.camera[1],
                    robot.camera[2],
                ),
                distance=robot.distance * 1.17,
                elevation=robot.elevation,
                azimuth=robot.azimuth,
                origin_type=mjswan.ViewerConfig.OriginType.WORLD,
            )
        )
        built_scenes.append(demo.id)

    old_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        builder.build()
    finally:
        os.chdir(old_cwd)

    output = ROOT / "dist"
    manifest = output / "manifest.json"
    if not manifest.is_file():
        raise RuntimeError(f"mjswan build produced no manifest at {manifest}")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    generated_ids = {
        scene["id"]
        for project_data in metadata.get("projects", [])
        for scene in project_data.get("scenes", [])
    }
    if not set(built_scenes).issubset(generated_ids):
        raise RuntimeError(f"missing compiled scenes: {sorted(set(built_scenes) - generated_ids)}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--base-path", default="/simulator/")
    args = parser.parse_args()
    print(build(args.menagerie, args.base_path))


if __name__ == "__main__":
    main()
