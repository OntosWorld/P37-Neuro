"""Curated interactive MuJoCo tasks on real Menagerie robot embodiments.

Each task modifies the actual MJCF scene with collidable bodies. It does not
add a learned policy, a scripted motion, or a pre-recorded animation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import mujoco


@dataclass(frozen=True, slots=True)
class Demo:
    id: str
    name: str
    robot_id: str
    body: str
    task: str
    summary: str
    interaction: str
    policy: str = "physics-only"

    def public(self) -> dict[str, str]:
        return asdict(self)


DEMOS: tuple[Demo, ...] = (
    Demo(
        "g1_impact_lab",
        "Impact laboratory",
        "unitree_g1",
        "Unitree G1",
        "External contact",
        "Apply force to a humanoid and inspect its response to collisions.",
        "Pull the weighted sphere into the robot. Reset to repeat.",
    ),
    Demo(
        "go2_contact_field",
        "Contact field",
        "unitree_go2",
        "Unitree Go2",
        "Obstacle contacts",
        "Explore how a four-legged robot interacts with different obstacles.",
        "Drag the robot through the contact field. No gait controller is attached.",
    ),
    Demo(
        "franka_gravity_stack",
        "Gravity and objects",
        "franka_panda",
        "Franka Panda",
        "Object interaction",
        "Move objects around the work area and observe collisions and stacking.",
        "Pull and release the blocks. There is no trained pick-and-place policy.",
    ),
)


def decorate_task(spec: mujoco.MjSpec, demo_id: str) -> None:
    """Add visible, physical objects to an existing Menagerie model."""
    if demo_id == "g1_impact_lab":
        body = spec.worldbody.add_body(name="p37_weighted_sphere", pos=[0.9, 0.1, 0.38])
        body.add_geom(
            name="p37_impact_ball",
            type=mujoco.mjtGeom.mjGEOM_SPHERE,
            size=[0.21, 0, 0],
            rgba=[0.83, 0.86, 0.89, 1],
            density=1300,
            friction=[0.8, 0.01, 0.001],
        )
        body.add_freejoint()
        spec.worldbody.add_geom(
            name="p37_start_line",
            type=mujoco.mjtGeom.mjGEOM_BOX,
            pos=[0.95, 0.1, 0.004],
            size=[0.35, 0.015, 0.005],
            rgba=[0.31, 0.38, 0.44, 0.8],
            contype=0,
            conaffinity=0,
        )
    elif demo_id == "go2_contact_field":
        for i, (x, y, height) in enumerate(
            ((0.8, -0.3, 0.10), (1.12, 0.35, 0.17), (1.6, -0.25, 0.23))
        ):
            spec.worldbody.add_geom(
                name=f"p37_obstacle_{i}",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                pos=[x, y, height / 2],
                size=[0.16, 0.27, height / 2],
                rgba=[0.58 - i * 0.07, 0.64 - i * 0.08, 0.70 - i * 0.07, 1],
                friction=[0.9, 0.015, 0.001],
            )
    elif demo_id == "franka_gravity_stack":
        # Three unfixed rigid bodies, each independently simulated by MuJoCo.
        # Leave space between them so the scene starts in a valid state.
        positions = ((0.50, 0.15, 0.17), (0.73, 0.02, 0.23), (0.58, -0.20, 0.31))
        for i, pos in enumerate(positions):
            body = spec.worldbody.add_body(name=f"p37_block_body_{i}", pos=list(pos))
            body.add_geom(
                name=f"p37_block_{i}",
                type=mujoco.mjtGeom.mjGEOM_BOX,
                size=[0.075, 0.075, 0.075],
                rgba=[0.66 + i * 0.05, 0.71 + i * 0.035, 0.76 + i * 0.02, 1],
                density=650,
                friction=[0.8, 0.01, 0.001],
            )
            body.add_freejoint()
    else:
        raise ValueError(f"Unknown physical demo id: {demo_id}")
