"""Single source of truth for curated, real MuJoCo Menagerie robot scenes.

The scene ids are exact mjswan slug ids of the human-readable scene names.
They are intentionally stable public URLs. No policy is attributed to a robot
unless it has actually been attached and validated in the browser.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RobotScene:
    id: str
    name: str
    model: str
    kind: str
    short: str
    capability: str
    task: str
    camera: tuple[float, float, float]
    distance: float
    elevation: float = -21.0
    azimuth: float = -128.0
    weight: int = 0

    def to_public(self) -> dict:
        value = asdict(self)
        value.pop("camera")
        value.pop("distance")
        value.pop("elevation")
        value.pop("azimuth")
        value.pop("weight")
        return value


ROBOTS: tuple[RobotScene, ...] = (
    RobotScene(
        "unitree_g1", "Unitree G1", "unitree_g1", "Humanoids",
        "29-DoF humanoid", "Whole-body balance", "Balance under perturbation",
        (0, 0, 0.88), 3.5, weight=1,
    ),
    RobotScene(
        "unitree_h1", "Unitree H1", "unitree_h1", "Humanoids",
        "Full-size humanoid", "Locomotion research", "Whole-body physics",
        (0, 0, 0.96), 4.1, weight=2,
    ),
    RobotScene(
        "booster_t1", "Booster T1", "booster_t1", "Humanoids",
        "Compact humanoid", "Motor control", "Articulated dynamics",
        (0, 0, 0.62), 2.9, weight=3,
    ),
    RobotScene(
        "unitree_go2", "Unitree Go2", "unitree_go2", "Quadrupeds",
        "12-DoF quadruped", "Contact dynamics", "External-force challenge",
        (0, 0, 0.39), 2.8, weight=4,
    ),
    RobotScene(
        "spot", "Boston Dynamics Spot", "boston_dynamics_spot", "Quadrupeds",
        "Industrial quadruped", "Terrain mobility", "Terrain and balance",
        (0, 0, 0.53), 3.0, weight=5,
    ),
    RobotScene(
        "anymal_c", "ANYmal C", "anybotics_anymal_c", "Quadrupeds",
        "Inspection quadruped", "Legged robotics", "Body stability",
        (0, 0, 0.48), 2.9, weight=6,
    ),
    RobotScene(
        "franka_panda", "Franka Panda", "franka_emika_panda", "Manipulators",
        "7-axis robot arm", "Grasping research", "Contact and interaction",
        (0, 0, 0.45), 2.15, weight=7,
    ),
    RobotScene(
        "ur5e", "Universal Robots UR5e", "universal_robots_ur5e", "Manipulators",
        "Industrial robot arm", "Precision motion", "Reach and articulation",
        (0, 0, 0.38), 2.65, weight=8,
    ),
    RobotScene(
        "stretch", "Hello Robot Stretch", "hello_robot_stretch", "Mobile",
        "Mobile manipulator", "Mobile manipulation", "Body and arm control",
        (0, 0, 0.72), 3.3, weight=9,
    ),
    RobotScene(
        "crazyflie_2", "Crazyflie 2", "bitcraze_crazyflie_2", "Aerial",
        "Micro quadrotor", "Flight dynamics", "Free-body motion",
        (0, 0, 0.65), 2.0, weight=10,
    ),
)


def check_catalog() -> None:
    ids = [robot.id for robot in ROBOTS]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate robot scene IDs")
    models = [robot.model for robot in ROBOTS]
    if len(set(models)) != len(models):
        raise ValueError("Duplicate physical robot models")
    for robot in ROBOTS:
        slug = "".join(c.lower() if c.isalnum() else "_" for c in robot.name).strip("_")
        # mjswan removes repeated underscores as well.
        while "__" in slug:
            slug = slug.replace("__", "_")
        if robot.id != slug:
            raise ValueError(f"ID {robot.id} disagrees with mjswan name {robot.name!r}")


check_catalog()
