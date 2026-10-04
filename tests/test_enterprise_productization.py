from p37_neuro.data.schema import Action, Observation
from p37_neuro.deployment import (
    DeploymentTarget,
    RolloutHealth,
    RolloutPlan,
    rollout_ready,
    rollout_requires_rollback,
)
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec
from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.integration import AdapterHealth, validate_adapter
from p37_neuro.observability import (
    RuntimeHealthState,
    RuntimeMetricSnapshot,
    evaluate_runtime_health,
)


class FakeAdapter:
    def __init__(self) -> None:
        self._body = EmbodimentSpec(
            embodiment_id="robot-1",
            family="test",
            joints=(
                JointSpec(
                    "joint_1",
                    JointType.REVOLUTE,
                    ControlMode.POSITION,
                    NumericRange(-1.0, 1.0),
                    1.0,
                    2.0,
                ),
            ),
        )

    @property
    def embodiment(self) -> EmbodimentSpec:
        return self._body

    def read_observation(self) -> Observation:
        return Observation(0.0, {"joint_1": 0.0}, {"joint_1": 0.0})

    def write_action(self, action: Action) -> None:
        del action

    def request_stop(self, reason: str) -> None:
        del reason

    def health(self) -> AdapterHealth:
        return AdapterHealth(True, True, True, True, True)


def test_robot_adapter_contract_is_vendor_neutral() -> None:
    health = validate_adapter(FakeAdapter())
    assert health.ready


def test_runtime_health_distinguishes_ready_and_not_ready() -> None:
    snapshot = RuntimeMetricSnapshot(
        robot_id="robot-1",
        artifact_id="p37-v1",
        timestamp_s=1.0,
        control_loop_hz=100.0,
        inference_p50_ms=5.0,
        inference_p95_ms=7.0,
        inference_p99_ms=9.0,
        observation_age_p95_ms=4.0,
        rejected_commands=0,
        watchdog_events=0,
        interventions=0,
        runtime_restarts=0,
    )
    assert evaluate_runtime_health(snapshot).state is RuntimeHealthState.READY
    degraded = RuntimeMetricSnapshot(
        **{**snapshot.__dict__, "control_loop_hz": 0.0}
    )
    report = evaluate_runtime_health(degraded)
    assert report.state is RuntimeHealthState.NOT_READY
    assert not report.safe_to_command


def test_rollout_requires_enterprise_approvals_and_supports_manual_rollback_policy() -> None:
    target = DeploymentTarget("org", "site", "fleet", ("r1", "r2"))
    plan = RolloutPlan(
        1,
        "v2",
        "v1",
        target,
        "s3://report",
        required_approvals=2,
        approvals=("ops",),
        automatic_rollback=False,
    )
    assert not rollout_ready(plan)
    assert not rollout_requires_rollback(plan, RolloutHealth(2, 2))
    assert rollout_requires_rollback(plan, RolloutHealth(2, 0, stop_requested=True))
