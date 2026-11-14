"""Native task scenes attached to the actual MuJoCo Menagerie robot models.

These are real colliding MuJoCo objects and terrain, not video props. Their
task predicates are measured from MuJoCo state in the browser. A simulated
object moving by itself is NEVER called a completed robot task. Controllers
may fail and task completion is not assumed.
"""

from __future__ import annotations

import mujoco

# Experiment names and spawn coordinates are part of the browser protocol.
TASK_SCENE_VERSION = 2
TERRAIN_ROBOTS = ("unitree_go2", "anymal_c")
TERRAIN_WAYPOINTS = {
    "unitree_go2": 1.7,
    "anymal_c": 1.6,
}


def _marker(spec: mujoco.MjSpec, name: str, x: float, y: float, z: float) -> None:
    spec.worldbody.add_geom(
        name=name,
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        pos=[x, y, z],
        size=[0.16, 0.006, 0],
        rgba=[0.16, 0.54, 0.34, 0.52],
        contype=0,
        conaffinity=0,
    )


def _box(
    spec: mujoco.MjSpec,
    name: str,
    *,
    pos: tuple[float, float, float],
    half: tuple[float, float, float],
    color: tuple[float, float, float, float],
    friction: tuple[float, float, float] = (0.9, 0.005, 0.0001),
) -> None:
    spec.worldbody.add_geom(
        name=name,
        type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=list(pos),
        size=list(half),
        rgba=list(color),
        friction=list(friction),
        contype=1,
        conaffinity=1,
    )


def _cube(
    spec: mujoco.MjSpec,
    name: str,
    *,
    pos: tuple[float, float, float],
    rgba: tuple[float, float, float, float],
) -> None:
    # Real 6-DoF freejoint with mass, inertia and contact response.
    body = spec.worldbody.add_body(name=name, pos=list(pos))
    body.add_freejoint()
    body.add_geom(
        name=name + "_collision",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        size=[0.03, 0.03, 0.03],
        mass=0.065,
        friction=[1.1, 0.005, 0.0001],
        rgba=list(rgba),
        contype=1,
        conaffinity=1,
    )


def add_physical_task_scene(spec: mujoco.MjSpec, robot_id: str) -> None:
    """Add non-destructive physical task environment to the real robot scene."""
    if robot_id in TERRAIN_ROBOTS:
        # Low curbs and offset blocks. Obstacles collide with the real model.
        # No fake body translation or hidden gait/balance script is added here.
        _box(
            spec,
            "p37_terrain_curb",
            pos=(0.50, 0.0, 0.035),
            half=(0.10, 0.56, 0.035),
            color=(0.40, 0.45, 0.44, 1.0),
        )
        _box(
            spec,
            "p37_terrain_step",
            pos=(1.02, 0.14, 0.055),
            half=(0.13, 0.33, 0.055),
            color=(0.49, 0.52, 0.50, 1.0),
        )
        _box(
            spec,
            "p37_terrain_pylon",
            pos=(1.34, -0.42, 0.13),
            half=(0.06, 0.06, 0.13),
            color=(0.71, 0.52, 0.30, 1.0),
        )
        _marker(spec, "p37_terrain_finish", TERRAIN_WAYPOINTS[robot_id], 0, 0.013)

    elif robot_id == "franka_panda":
        # Panda base is bolted at the world origin. 0.55 m high bench within
        # its workspace, with two independent dynamical cubes above the top.
        _box(
            spec,
            "p37_stack_bench",
            pos=(0.53, 0.0, 0.27),
            half=(0.32, 0.36, 0.27),
            color=(0.38, 0.40, 0.39, 1.0),
        )
        _cube(
            spec,
            "p37_stack_blue",
            pos=(0.45, -0.16, 0.57),
            rgba=(0.20, 0.44, 0.78, 1.0),
        )
        _cube(
            spec,
            "p37_stack_amber",
            pos=(0.53, 0.12, 0.57),
            rgba=(0.86, 0.50, 0.24, 1.0),
        )
        _marker(spec, "p37_stack_target", 0.53, 0.12, 0.546)

    elif robot_id == "franka_pick_place":
        # Dedicated tabletop placement scene. This is a separate physical
        # task from stacking, with one dynamic cube and a non-colliding target.
        _box(
            spec,
            "p37_pick_bench",
            pos=(0.53, 0.0, 0.27),
            half=(0.32, 0.36, 0.27),
            color=(0.38, 0.40, 0.39, 1.0),
        )
        _cube(
            spec,
            "p37_pick_cube",
            pos=(0.45, -0.16, 0.57),
            rgba=(0.20, 0.44, 0.78, 1.0),
        )
        _marker(spec, "p37_pick_target", 0.53, 0.12, 0.546)

    elif robot_id == "hello_robot_stretch":
        # Menagerie already contains the real 6-DoF source object on its
        # source table. Add a distinct receiving station with actual contact.
        _box(
            spec,
            "p37_delivery_station",
            pos=(0.72, 0.55, 0.22),
            half=(0.34, 0.29, 0.22),
            color=(0.28, 0.36, 0.32, 1.0),
        )
        _marker(spec, "p37_delivery_goal", 0.72, 0.55, 0.447)


def validate_task_scene(model: mujoco.MjModel, robot_id: str) -> None:
    """Reject missing task collision geometry at build time."""
    expected = {
        "unitree_go2": ("p37_terrain_curb", "p37_terrain_step", "p37_terrain_pylon"),
        "anymal_c": ("p37_terrain_curb", "p37_terrain_step", "p37_terrain_pylon"),
        "franka_panda": (
            "p37_stack_bench",
            "p37_stack_blue_collision",
            "p37_stack_amber_collision",
        ),
        "franka_pick_place": ("p37_pick_bench", "p37_pick_cube_collision"),
        "hello_robot_stretch": ("p37_delivery_station",),
    }.get(robot_id, ())
    for name in expected:
        geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
        if geom < 0:
            raise ValueError(f"missing physical task geom {robot_id}/{name}")
        if int(model.geom_contype[geom]) == 0 or int(model.geom_conaffinity[geom]) == 0:
            raise ValueError(f"task geom {robot_id}/{name} must have physical collision")
    if robot_id in {"franka_panda", "franka_pick_place"}:
        cube_names = (
            ("p37_stack_blue", "p37_stack_amber")
            if robot_id == "franka_panda"
            else ("p37_pick_cube",)
        )
        for name in cube_names:
            body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
            if body < 0:
                raise ValueError(f"missing cube body {name}")
            if model.body_mass[body] <= 0:
                raise ValueError(f"nonphysical cube mass {name}")
    if (
        robot_id == "hello_robot_stretch"
        and mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "object") < 0
    ):
        raise ValueError("Stretch source physical object missing")
