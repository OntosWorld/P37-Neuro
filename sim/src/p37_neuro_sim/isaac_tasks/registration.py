"""Gym registration for the P37 locomotion task."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib import import_module
from typing import Any

TASK_ID = "P37-Neuro-Locomotion-Rough-v0"


@dataclass(frozen=True, slots=True)
class TaskRegistration:
    task_id: str
    entry_point: str
    env_cfg_entry_point: str
    agent_cfg_entry_point: str


def registration_spec() -> TaskRegistration:
    """Return registration metadata without importing Isaac Lab."""
    return TaskRegistration(
        task_id=TASK_ID,
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        env_cfg_entry_point=(
            "p37_neuro_sim.isaac_tasks.locomotion_env_cfg:P37RoughLocomotionEnvCfg"
        ),
        agent_cfg_entry_point=(
            "p37_neuro_sim.isaac_tasks.agents.rsl_rl_ppo_cfg:P37RoughPPORunnerCfg"
        ),
    )


def register() -> None:
    """Register the P37 task in Gymnasium inside an Isaac Lab process."""
    gym: Any = import_module("gymnasium")
    spec = registration_spec()
    if spec.task_id in gym.registry:
        return
    gym.register(
        id=spec.task_id,
        entry_point=spec.entry_point,
        disable_env_checker=True,
        kwargs={
            "env_cfg_entry_point": spec.env_cfg_entry_point,
            "rsl_rl_cfg_entry_point": spec.agent_cfg_entry_point,
        },
    )


def register_from_isaac_cli() -> list[str]:
    """Isaac Lab external-callback hook.

    P37 consumes no CLI arguments here, so all original arguments are returned
    for Isaac Lab and Hydra to process.
    """
    register()
    return sys.argv[1:]
