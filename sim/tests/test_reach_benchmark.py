from pathlib import Path

import pytest
from p37_neuro.data.storage import read_episode
from p37_neuro.integration import run_mujoco_reach_benchmark


def _manifest() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "tabletop_arm" / "robot-mujoco.yaml"


def test_closed_loop_reach_writes_replayable_evidence(tmp_path: Path) -> None:
    result = run_mujoco_reach_benchmark(_manifest(), output_dir=tmp_path, steps=200, seed=42)

    assert result.success
    assert result.final_distance_m <= result.success_threshold_m
    assert result.final_distance_m < result.initial_distance_m
    assert result.safety_clamp_count == 0
    assert result.replay_max_joint_error == pytest.approx(0.0, abs=1e-12)
    assert Path(result.metrics_path).is_file()
    episode = read_episode(result.episode_path)
    assert episode.task_id == "cartesian-reach"
    assert episode.steps[-1].terminal
    assert episode.steps[-1].failure_code is None
    assert "end_effector_x_m" in episode.steps[-1].observation.state


def test_unreachable_target_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the reference arm workspace"):
        run_mujoco_reach_benchmark(
            _manifest(),
            output_dir=tmp_path,
            target_x=1.0,
            target_y=1.0,
        )
