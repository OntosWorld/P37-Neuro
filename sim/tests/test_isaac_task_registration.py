import sys

from p37_neuro_sim.isaac_tasks.registration import (
    TASK_ID,
    register_from_isaac_cli,
    registration_spec,
)


def test_p37_isaac_task_registration_metadata() -> None:
    spec = registration_spec()
    assert spec.task_id == TASK_ID
    assert spec.entry_point == "isaaclab.envs:ManagerBasedRLEnv"
    assert "P37RoughLocomotionEnvCfg" in spec.env_cfg_entry_point
    assert "P37RoughPPORunnerCfg" in spec.agent_cfg_entry_point


def test_external_callback_preserves_cli_args(monkeypatch) -> None:
    monkeypatch.setattr(
        "p37_neuro_sim.isaac_tasks.registration.register",
        lambda: None,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["train", "--task", TASK_ID, "--num_envs", "64"],
    )
    assert register_from_isaac_cli() == ["--task", TASK_ID, "--num_envs", "64"]
