from pathlib import Path

import pytest

from p37_neuro_sim.isaac_lab import (
    IsaacLabRun,
    IsaacLabRunner,
    IsaacLabUnavailableError,
)


def test_isaac_lab_command_is_reproducible() -> None:
    run = IsaacLabRun(
        task="Isaac-Reach-Franka-v0",
        run_name="p37-e1",
        num_envs=128,
        seed=7,
        checkpoint=Path("model.pt"),
        extra_args=("--video",),
    )
    command = run.command("/opt/isaaclab")
    assert command[:3] == ("/opt/isaaclab", "train", "--rl_library")
    assert "--headless" in command
    assert command[-1] == "--video"


def test_missing_isaac_lab_fails_clearly() -> None:
    runner = IsaacLabRunner("definitely-not-an-installed-binary")
    assert not runner.available()
    with pytest.raises(IsaacLabUnavailableError):
        runner.run(IsaacLabRun(task="Task", run_name="run"))
