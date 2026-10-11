import json
from pathlib import Path

import pytest

p37_neuro_ml = pytest.importorskip("p37_neuro_ml")

from p37_neuro_sim.learned_reach import (  # noqa: E402
    _wilson_interval,
    run_learned_reach_experiment,
    run_learned_reach_suite,
)


def _manifest() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "tabletop_arm" / "robot-mujoco.yaml"


def test_goal_conditioned_experiment_writes_complete_evidence(tmp_path: Path) -> None:
    result = run_learned_reach_experiment(
        _manifest(),
        output_dir=tmp_path,
        seed=19,
        train_target_count=8,
        evaluation_target_count=3,
        epochs=5,
        evaluation_steps=20,
        qualification_success_rate=0.0,
    )

    assert result["training_targets"] == 8
    assert result["evaluation_targets"] == 3
    assert result["final_action_loss"] >= 0.0
    assert result["baseline_success_rate"] == 1.0
    assert result["nominal_qualified"] is True
    assert len(tuple((tmp_path / "demonstrations").glob("*.jsonl"))) == 8
    assert len(tuple((tmp_path / "learned-evaluations").glob("*.jsonl"))) == 3
    metrics = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["checkpoint_dir"] == str(tmp_path / "checkpoint")


def test_invalid_experiment_size_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        run_learned_reach_experiment(
            _manifest(),
            output_dir=tmp_path,
            train_target_count=0,
        )


def test_wilson_interval_contains_observed_rate() -> None:
    low, high = _wilson_interval(90, 100)
    assert low < 0.9 < high


def test_multi_seed_suite_writes_aggregate_gate(tmp_path: Path) -> None:
    result = run_learned_reach_suite(
        _manifest(),
        output_dir=tmp_path,
        seeds=(11, 23),
        train_target_count=8,
        evaluation_target_count=3,
        epochs=5,
        evaluation_steps=20,
        qualification_success_rate=0.0,
    )
    assert result["runs"] == 2
    assert result["total_heldout_trials"] == 6
    assert result["suite_qualified"] is True
    assert Path(result["metrics_path"]).is_file()


def test_multi_seed_suite_rejects_duplicate_seeds(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty and unique"):
        run_learned_reach_suite(
            _manifest(),
            output_dir=tmp_path,
            seeds=(7, 7),
        )
