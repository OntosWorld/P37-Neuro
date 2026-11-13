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
import numpy as np
import onnx
from catalog import ROBOTS, RobotScene, check_catalog
from mjswan.envs.mdp.actions import JointPositionActionCfg, MuscleActivationActionCfg
from model_motion_library import _onnx_table, create_library
from panda_physical_stack import run as qualify_panda_stack
from physical_task_scenes import add_physical_task_scene, validate_task_scene

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


def _task_checkpoint(spec: mujoco.MjSpec, robot: RobotScene) -> None:
    """Create an inert visual waypoint in the same coordinate frame as MuJoCo.

    This is a measurable target, not an actor, motion clip, or hidden controller.
    It has no collision response and cannot advance a task on its own. The
    runtime reports actual body displacement / hinge travel to the UI.
    """
    targets = {
        "unitree_g1": 1.0,
        "unitree_h1": 1.0,
        "booster_t1": 0.9,
        "boston_dynamics_spot": 1.2,
        "hello_robot_stretch": 0.8,
        "unitree_go2": 1.7,
        "anymal_c": 1.6,
    }
    if robot.id in targets:
        x = targets[robot.id]
        spec.worldbody.add_geom(
            name="p37_task_waypoint_floor",
            type=mujoco.mjtGeom.mjGEOM_CYLINDER,
            pos=[x, 0.0, 0.012],
            size=[0.28, 0.012, 0.0],
            rgba=[0.21, 0.43, 0.32, 0.72],
            contype=0,
            conaffinity=0,
        )
        spec.worldbody.add_geom(
            name="p37_task_waypoint_center",
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            pos=[x, 0.0, 0.16],
            size=[0.045, 0.045, 0.045],
            rgba=[0.89, 0.93, 0.82, 1.0],
            contype=0,
            conaffinity=0,
        )
    elif robot.id == "crazyflie_2":
        spec.worldbody.add_geom(
            name="p37_task_hover_reference",
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            pos=[0.0, 0.0, 0.65],
            size=[0.06, 0.06, 0.06],
            rgba=[0.32, 0.59, 0.44, 0.55],
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
        "Model-derived motion datasets on all ten bodies are not learned P37 skills.\\n"
        "Task scenes add colliding cubes, delivery props or obstacle terrain where supported;\\n"
        "user steering and scripted force assistance are not learned locomotion or manipulation."
    )

    if p37_artifact is None:
        raise ValueError("The public build requires the verified P37 ONNX artifact")
    from p37_browser_policy import attach_g1_policy

    motion_dir = ROOT / "motion_data"
    library = create_library(menagerie, ROBOTS, motion_dir)
    # Fail the public build if native contact / lift / release / final stack or
    # deterministic replay fails. The validated actions remain scripted.
    panda_qualification = qualify_panda_stack(menagerie, motion_dir, require_success=True)
    with np.load(motion_dir / "panda-physical-stack.npz", allow_pickle=False) as data:
        panda_actions = np.asarray(data["actions"], dtype=np.float32)
    panda_policy_path = motion_dir / "panda-physical-stack.onnx"
    # The ordinary motion clips cycle. This finite task must NOT loop back
    # through another grasp after it has released and settled the stack.
    # Clamp the ONNX frame index to the final safe open-gripper command.
    panda_table = _onnx_table(panda_actions)
    frame_index = next(node for node in panda_table.graph.node if node.op_type == "Mod")
    frame_index.op_type = "Min"
    frame_index.input[1] = "p37_last_frame"
    panda_table.graph.initializer.append(
        onnx.helper.make_tensor(
            "p37_last_frame",
            onnx.TensorProto.INT64,
            [1],
            [len(panda_actions) - 1],
        )
    )
    panda_table.producer_name = "Ontos contact-verified finite Panda scripted task"
    onnx.checker.check_model(panda_table)
    onnx.save(panda_table, str(panda_policy_path))
    built_scenes = []
    for robot in ROBOTS:
        path = menagerie / robot.model / "scene.xml"
        if not path.is_file():
            raise FileNotFoundError(f"Missing physical robot model: {path}")
        spec = mujoco.MjSpec.from_file(str(path))
        _light_scene(spec, robot)
        _task_checkpoint(spec, robot)
        add_physical_task_scene(spec, robot.id)
        validate_task_scene(spec.compile(), robot.id)
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
                    "motor": MuscleActivationActionCfg(
                        actuator_names=tuple(
                            re.escape(name) for name in clip["actuator_or_joint_names"]
                        ),
                        action_mode="direct",
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
        if robot.id == "franka_panda":
            # Full physically validated grasp/lift/carry/release stack, recorded
            # from the *same* Menagerie model and the same real contact objects.
            # All eight actuators are addressed with their native ctrl values.
            scene.add_policy(
                name="Panda Physical Cube Stack Scripted",
                policy=onnx.load(str(panda_policy_path)),
                in_keys=["time_step"],
                out_keys=["action"],
                actions={
                    "motor": MuscleActivationActionCfg(
                        actuator_names=tuple(f"actuator{i}" for i in range(1, 9)),
                        action_mode="direct",
                        scale=1.0,
                    )
                },
                observations={},
                commands={},
                terminations={},
                policy_joint_names=None,
                policy_num_actions=8,
                default=False,
                extras={
                    "source": "Physically qualified deterministic Panda IK reference",
                    "task_id": "panda-physical-cube-stack",
                    "scripted_reference": True,
                    "learned_p37_policy": False,
                    "contact_lift_release_stack_verified": True,
                    "independent_native_replay_verified": True,
                    "control_sha256": panda_qualification["sha256"],
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

    # mjswan's native direct-actuator runtime can write validated site/tendon
    # motors, but its Python muscle checker normally permits only mjDYN_MUSCLE.
    # Our model-derived non-learned clips use the exact source motor names and
    # direct ctrl ranges. Enforce strict bounds/matching before accepting them;
    # leave the normal validator in place for actual muscle policies.
    from mjswan.build import pipeline as pipeline_module
    from mjswan.envs.mdp.actions.actions import validate_muscle_actuators

    def validate_direct_source_motors(scene_config):
        direct = [
            (name, cfg)
            for policy in scene_config.policies
            for name, cfg in (getattr(policy, "actions", None) or {}).items()
            if isinstance(cfg, MuscleActivationActionCfg)
        ]
        if not direct:
            return
        model = scene_config.model
        if model is None and scene_config.spec is not None:
            model = scene_config.spec.compile()
        if model is None:
            raise RuntimeError("Physical source model required for motor replay")
        actual_names = [
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)
        ]
        for term_name, cfg in direct:
            if term_name != "motor" or cfg.mode != "direct":
                validate_muscle_actuators(model, cfg, term_name=term_name)
                continue
            patterns = list(cfg.actuator_names)
            matched = [
                name
                for name in actual_names
                if any(re.fullmatch(pattern, name or "") for pattern in patterns)
            ]
            if (
                not all(actual_names)
                or len(set(actual_names)) != len(actual_names)
                or matched != actual_names
                or any(int(dyn) != int(mujoco.mjtDyn.mjDYN_NONE) for dyn in model.actuator_dyntype)
            ):
                raise ValueError(
                    "Direct motion replay must name every nondynamic motor "
                    "in the original model actuator order"
                )
            for index in range(model.nu):
                if model.actuator_ctrllimited[index]:
                    lo, hi = model.actuator_ctrlrange[index]
                    if not (float("-inf") < lo < hi < float("inf")):
                        raise ValueError("Invalid native motor control limits")

    pipeline_module._validate_muscle_action_terms = validate_direct_source_motors

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
    # mjswan currently exposes the simulation through a private Engine instance.
    # Add one narrowly scoped integration hook to the *build-time template*.
    # The public steering bridge never replaces the robot meshes or physics.
    from mjswan.build import frontend as frontend_module

    app_source = frontend_module.TEMPLATE_DIR / "src" / "App.tsx"
    original_app = app_source.read_text(encoding="utf-8")
    hook = "      engineRef.current = engine;"
    if original_app.count(hook) != 1:
        raise RuntimeError("Upstream mjswan engine integration hook changed")
    patched_app = original_app.replace(
        hook,
        hook
        + "\n"
        + ("      (window as Window & { __p37Engine?: unknown }).__p37Engine = engine;"),
        1,
    )
    old_cwd = Path.cwd()
    try:
        app_source.write_text(patched_app, encoding="utf-8")
        os.chdir(ROOT)
        builder.build()
    finally:
        os.chdir(old_cwd)
        app_source.write_text(original_app, encoding="utf-8")

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
    # The bridge is loaded into the same-origin iframe after Vite has compiled
    # mjswan, and sends measured displacement back to the P37 parent page.
    import shutil

    shutil.copyfile(ROOT / "steering_bridge.js", output / "steering_bridge.js")
    index = output / "index.html"
    html = index.read_text(encoding="utf-8")
    if html.count("</body>") != 1:
        raise RuntimeError("Upstream mjswan HTML no longer has one body closing tag")
    index.write_text(
        html.replace("</body>", '<script defer src="./steering_bridge.js"></script></body>'),
        encoding="utf-8",
    )
    # Export the actual sampled joint/motor trajectories for inspection.
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
