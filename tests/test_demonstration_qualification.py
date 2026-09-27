import pytest

from p37_neuro.benchmarks.demonstration import OneShotTrial, one_shot_metrics
from p37_neuro.benchmarks.qualification import (
    QualificationEvidence,
    qualify_release,
)


def test_one_shot_metrics_reject_training_leakage() -> None:
    invalid = OneShotTrial(
        task_id="unseen-pick",
        embodiment_id="arm-a",
        task_was_held_out=True,
        demonstration_count=1,
        gradient_updates=1,
        success=True,
        completed_stages=1,
        total_stages=1,
    )
    with pytest.raises(ValueError, match="non-one-shot"):
        one_shot_metrics((invalid,))


def test_one_shot_metrics_cover_multiple_embodiments() -> None:
    trials = tuple(
        OneShotTrial(
            task_id=f"task-{index}",
            embodiment_id=f"body-{index}",
            task_was_held_out=True,
            demonstration_count=1,
            gradient_updates=0,
            success=index != 2,
            completed_stages=1 if index != 2 else 0,
            total_stages=1,
        )
        for index in range(3)
    )
    metrics = one_shot_metrics(trials)
    assert metrics["embodiment_count"] == 3.0
    assert metrics["success_rate"] == pytest.approx(2 / 3)


def test_release_qualification_keeps_missing_physical_evidence_open() -> None:
    result = qualify_release(
        QualificationEvidence(
            artifact_id="candidate-1",
            heldout_embodiments=4,
            physical_embodiments=0,
            cross_embodiment_success_rate=0.9,
            one_shot_success_rate=0.8,
            long_horizon_success_rate=0.8,
            interventions_per_hour=0.1,
            deterministic_safety_passed=True,
            fleet_feedback_verified=True,
            promotion_and_rollback_verified=True,
            benchmark_report_uri="reports/candidate-1.json",
        )
    )
    assert not result.passed
    assert result.failed_gates == ("physical_embodiments",)
