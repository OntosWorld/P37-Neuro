"""Generic P37 locomotion environment for Isaac Lab.

This module is imported only inside an Isaac Lab environment. Robot-specific
facts come from environment variables so the task package stays manufacturer
neutral.
"""

from __future__ import annotations

import os

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils.configclass import configclass
from isaaclab_tasks.manager_based.locomotion.velocity.velocity_env_cfg import (
    LocomotionVelocityRoughEnvCfg,
)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set for the P37 Isaac Lab task")
    return value


def _robot_cfg() -> ArticulationCfg:
    usd_path = _required("P37_ROBOT_USD")
    base_height = float(os.environ.get("P37_BASE_HEIGHT_M", "0.5"))
    effort_limit = float(os.environ.get("P37_ACTUATOR_EFFORT_LIMIT", "120"))
    stiffness = float(os.environ.get("P37_ACTUATOR_STIFFNESS", "40"))
    damping = float(os.environ.get("P37_ACTUATOR_DAMPING", "2"))

    return ArticulationCfg(
        spawn=sim_utils.UsdFileCfg(
            usd_path=usd_path,
            activate_contact_sensors=True,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                disable_gravity=False,
                retain_accelerations=False,
                linear_damping=0.0,
                angular_damping=0.0,
                max_linear_velocity=100.0,
                max_angular_velocity=100.0,
                max_depenetration_velocity=1.0,
            ),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                enabled_self_collisions=False,
                solver_position_iteration_count=8,
                solver_velocity_iteration_count=4,
            ),
        ),
        init_state=ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, base_height),
            joint_pos={".*": 0.0},
            joint_vel={".*": 0.0},
        ),
        soft_joint_pos_limit_factor=0.9,
        actuators={
            "all": ImplicitActuatorCfg(
                joint_names_expr=[".*"],
                effort_limit_sim=effort_limit,
                stiffness=stiffness,
                damping=damping,
            )
        },
    )


@configclass
class P37RoughLocomotionEnvCfg(LocomotionVelocityRoughEnvCfg):
    """Manufacturer-neutral rough-terrain velocity task."""

    def __post_init__(self) -> None:
        super().__post_init__()

        base_link = os.environ.get("P37_BASE_LINK", "base").strip()
        foot_regex = os.environ.get("P37_FOOT_REGEX", ".*[Ff][Oo][Oo][Tt].*").strip()
        undesired_contact_regex = os.environ.get("P37_UNDESIRED_CONTACT_REGEX", "").strip()

        self.scene.robot = _robot_cfg().replace(prim_path="{ENV_REGEX_NS}/Robot")
        self.scene.height_scanner.prim_path = f"{{ENV_REGEX_NS}}/Robot/{base_link}"

        base_sensor = SceneEntityCfg("contact_forces", body_names=base_link)
        foot_sensor = SceneEntityCfg("contact_forces", body_names=foot_regex)

        self.events.add_base_mass.params["asset_cfg"] = SceneEntityCfg(
            "robot",
            body_names=base_link,
        )
        if self.events.base_com is not None:
            self.events.base_com.params["asset_cfg"] = SceneEntityCfg(
                "robot",
                body_names=base_link,
            )
        self.events.base_external_force_torque.params["asset_cfg"] = SceneEntityCfg(
            "robot",
            body_names=base_link,
        )
        self.rewards.feet_air_time.params["sensor_cfg"] = foot_sensor
        self.terminations.base_contact.params["sensor_cfg"] = base_sensor

        if undesired_contact_regex:
            self.rewards.undesired_contacts.params["sensor_cfg"] = SceneEntityCfg(
                "contact_forces",
                body_names=undesired_contact_regex,
            )
        else:
            self.rewards.undesired_contacts = None
