"""Build physically simulated robot scenes with an editorial lab presentation.

This bundles true Menagerie MJCF geometry and MuJoCo WebAssembly. Styling
adds lights and non-colliding visual markers, never hidden locomotion scripts.
Only verified trained controllers may be attached as P37 policies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import mjswan
import mujoco
import onnx
from catalog import ROBOTS, RobotScene, check_catalog
from mjswan.envs.mdp.actions import JointEffortActionCfg, JointPositionActionCfg
from model_motion_library import create_library

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


def build(
    menagerie: Path,
    base_path: str = "/simulator/",
    *,
    p37_artifact: Path | None = None,
) -> Path:
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
        "The Unitree G1 scene includes an experimental, unqualified P37 ONNX policy.\n"
        "Model-derived motion datasets on all ten bodies are not learned P37 skills."
    )

    if p37_artifact is None:
        raise ValueError("The public build requires the verified P37 ONNX artifact")
    from p37_browser_policy import attach_g1_policy

    motion_dir = ROOT / "motion_data"
    library = create_library(menagerie, ROBOTS, motion_dir)
    built_scenes = []
    for robot in ROBOTS:
        path = menagerie / robot.model / "scene.xml"
        if not path.is_file():
            raise FileNotFoundError(f"Missing physical robot model: {path}")
        spec = mujoco.MjSpec.from_file(str(path))
        _light_scene(spec, robot)
        scene = project.add_scene(
            spec=spec,
            name=robot.name,
            control_dt=0.02,
        )
        if robot.id == "unitree_g1":
            attach_g1_policy(
                scene,
                path,
                p37_artifact,
            )
        for clip in library["motions"][robot.id]:
            clip_id = clip["id"]
            policy_model = onnx.load(str(motion_dir / f"{robot.id}-{clip_id}.onnx"))
            if clip["physics_control"] == "motor_effort":
                # Includes Crazyflie site-thrust/moment actuators and any
                # motor-only source model; never pretend they are joints.
                replay_actions = {
                    "motor": JointEffortActionCfg(
                        actuator_names=tuple(
                            re.escape(name) for name in clip["actuator_or_joint_names"]
                        ),
                        scale=1.0,
                    )
                }
                action_names = None
            else:
                action_names = clip["actuator_or_joint_names"]
                replay_actions = {
                    "joint_pos": JointPositionActionCfg(
                        actuator_names=tuple(re.escape(name) for name in action_names),
                        scale=0.35,
                        use_default_offset=True,
                        stiffness=45.0,
                        damping=2.0,
                    )
                }
            scene.add_policy(
                name=clip["name"],
                policy=policy_model,
                in_keys=["time_step"],
                out_keys=["action"],
                actions=replay_actions,
                observations={},
                commands={},
                terminations={},
                policy_joint_names=action_names,
                policy_num_actions=clip["actuators"],
                default=(robot.id != "unitree_g1" and clip_id == "articulation"),
                extras={
                    "source": "MuJoCo model-derived actuator motion dataset",
                    "dataset_file": clip["dataset_file"],
                    "model_derived": True,
                    "learned_p37_policy": False,
                    "locomotion_qualified": False,
                },
            )
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

    # Compatibility with a newer mjlab Scene GUI API: the optional GUI
    # recorder in mjswan currently builds a metadata-only fake model lacking
    # ncam. That recorder is not part of the physics or policy runtime. Keep
    # the real native model/ONNX build intact and skip only that optional GUI
    # snapshot if the known incompatibility is encountered.
    from mjswan.build import manifest as manifest_module

    original_gui = manifest_module.record_scene_gui

    def compatible_gui():
        try:
            return original_gui()
        except AttributeError as exc:
            if "ncam" not in str(exc):
                raise
            print("Skipping incompatible optional mjlab Scene GUI metadata")
            return None

    manifest_module.record_scene_gui = compatible_gui
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
    # Export the actual sampled joint/motor trajectories for inspection.
    import shutil

    target = output / "motion_data"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(motion_dir, target)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--base-path", default="/simulator/")
    parser.add_argument("--p37-artifact", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.menagerie, args.base_path, p37_artifact=args.p37_artifact))


if __name__ == "__main__":
    main()
