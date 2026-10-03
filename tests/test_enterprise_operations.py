from pathlib import Path

import pytest

from p37_neuro.data.governance import (
    DataGovernancePolicy,
    evaluate_data_use,
    governance_metadata,
    require_episode_use,
)
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.observability import JsonlMetricExporter, RuntimeMetrics, prometheus_text


def test_runtime_metrics_export_prometheus_and_jsonl(tmp_path: Path) -> None:
    metrics = RuntimeMetrics(max_samples=4)
    for value in (4.0, 5.0, 6.0, 7.0):
        metrics.observe_inference_ms(value)
    metrics.observe_observation_age_ms(2.0)
    metrics.increment_rejected_commands()
    snapshot = metrics.snapshot(
        robot_id="robot-1",
        artifact_id="p37-1",
        timestamp_s=10.0,
        control_loop_hz=100.0,
    )
    assert snapshot.inference_p95_ms == 7.0
    assert "p37_rejected_commands_total" in prometheus_text(snapshot)
    path = tmp_path / "metrics.jsonl"
    JsonlMetricExporter(path).export(snapshot)
    assert '"robot_id": "robot-1"' in path.read_text(encoding="utf-8")


def _episode(policy: DataGovernancePolicy) -> Episode:
    return Episode(
        episode_id="e1",
        embodiment_id="r1",
        task_id="pick",
        steps=(
            EpisodeStep(
                observation=Observation(0.0, {"j": 0.0}, {"j": 0.0}),
                action=Action(0.0, {"j": 0.0}),
                terminal=True,
            ),
        ),
        source="fleet",
        metadata=governance_metadata(policy),
    )


def test_governance_blocks_training_and_cross_region_use() -> None:
    policy = DataGovernancePolicy(
        customer_id="customer-a",
        site_id="site-1",
        region="eu-west",
        training_allowed=False,
        allowed_purposes=("evaluation", "training"),
    )
    decision = evaluate_data_use(policy, purpose="training", destination_region="us-east")
    assert not decision.allowed
    assert set(decision.reasons) == {"training_not_allowed", "cross_region_transfer_not_allowed"}

    with pytest.raises(PermissionError):
        require_episode_use(_episode(policy), purpose="training", destination_region="eu-west")
