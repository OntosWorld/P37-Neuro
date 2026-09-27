from p37_neuro.training.gates import EvaluationMetrics, GateThresholds, evaluate_gate
from p37_neuro.training.posttrain import PostTrainPlan


def test_gate_passes_good_candidate() -> None:
    metrics = EvaluationMetrics(0.9, 0.01, 0.0, 20.0)
    assert evaluate_gate(metrics, GateThresholds()).passed


def test_gate_reports_failed_dimensions() -> None:
    metrics = EvaluationMetrics(0.5, 0.2, 0.01, 100.0)
    decision = evaluate_gate(metrics, GateThresholds())
    assert not decision.passed
    assert "success_rate" in decision.reasons


def test_posttrain_plan_validation() -> None:
    plan = PostTrainPlan("base", "isaac", "ppo", 1000, 1, 100)
    assert plan.algorithm == "ppo"
