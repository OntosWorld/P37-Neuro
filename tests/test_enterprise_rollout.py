from pathlib import Path

from p37_neuro.deployment import (
    DeploymentTarget,
    RolloutHealth,
    RolloutPlan,
    build_rollback_plan,
    load_rollout_plan,
    rollout_requires_rollback,
    write_rollout_plan,
)


def _plan() -> RolloutPlan:
    return RolloutPlan(
        schema_version=1,
        artifact_id="p37-v2",
        previous_artifact_id="p37-v1",
        target=DeploymentTarget(
            "ontos-enterprise",
            "factory-1",
            "picking",
            ("robot-1", "robot-2", "robot-3", "robot-4"),
        ),
        qualification_report_uri="s3://reports/p37-v2.json",
        canary_count=1,
        batch_size=2,
    )


def test_rollout_plan_uses_canary_then_batches(tmp_path: Path) -> None:
    plan = _plan()
    assert plan.batches() == (
        ("robot-1",),
        ("robot-2", "robot-3"),
        ("robot-4",),
    )
    path = write_rollout_plan(plan, tmp_path / "plan.json")
    assert load_rollout_plan(path) == plan


def test_health_policy_and_rollback_plan() -> None:
    plan = _plan()
    assert not rollout_requires_rollback(plan, RolloutHealth(10, 1))
    assert rollout_requires_rollback(plan, RolloutHealth(10, 2))
    rollback = build_rollback_plan(plan)
    assert rollback.artifact_id == "p37-v1"
    assert rollback.previous_artifact_id == "p37-v2"
