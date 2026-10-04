"""Runtime health evaluation for non-real-time enterprise monitoring."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from p37_neuro.observability.metrics import RuntimeMetricSnapshot


class RuntimeHealthState(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    NOT_READY = "not_ready"


@dataclass(frozen=True, slots=True)
class RuntimeHealthThresholds:
    minimum_control_loop_hz: float = 1.0
    maximum_inference_p99_ms: float = 100.0
    maximum_observation_age_p95_ms: float = 100.0
    maximum_watchdog_events: int = 0

    def __post_init__(self) -> None:
        if self.minimum_control_loop_hz < 0:
            raise ValueError("minimum_control_loop_hz must be non-negative")
        if self.maximum_inference_p99_ms < 0 or self.maximum_observation_age_p95_ms < 0:
            raise ValueError("latency thresholds must be non-negative")
        if self.maximum_watchdog_events < 0:
            raise ValueError("maximum_watchdog_events must be non-negative")


@dataclass(frozen=True, slots=True)
class RuntimeHealthReport:
    robot_id: str
    artifact_id: str
    state: RuntimeHealthState
    safe_to_command: bool
    reasons: tuple[str, ...]

    def to_json(self) -> str:
        value = asdict(self)
        value["state"] = self.state.value
        return json.dumps(value, indent=2, sort_keys=True) + "\n"


def evaluate_runtime_health(
    snapshot: RuntimeMetricSnapshot,
    thresholds: RuntimeHealthThresholds | None = None,
) -> RuntimeHealthReport:
    limits = thresholds or RuntimeHealthThresholds()
    hard_reasons: list[str] = []
    soft_reasons: list[str] = []

    if snapshot.control_loop_hz < limits.minimum_control_loop_hz:
        hard_reasons.append("control_loop_below_minimum")
    if snapshot.observation_age_p95_ms > limits.maximum_observation_age_p95_ms:
        hard_reasons.append("observation_age_above_limit")
    if snapshot.watchdog_events > limits.maximum_watchdog_events:
        hard_reasons.append("watchdog_event_detected")
    if snapshot.inference_p99_ms > limits.maximum_inference_p99_ms:
        soft_reasons.append("inference_latency_above_target")
    if snapshot.rejected_commands > 0:
        soft_reasons.append("commands_rejected")
    if snapshot.interventions > 0:
        soft_reasons.append("operator_interventions_recorded")

    if hard_reasons:
        state = RuntimeHealthState.NOT_READY
    elif soft_reasons:
        state = RuntimeHealthState.DEGRADED
    else:
        state = RuntimeHealthState.READY

    return RuntimeHealthReport(
        robot_id=snapshot.robot_id,
        artifact_id=snapshot.artifact_id,
        state=state,
        safe_to_command=not hard_reasons,
        reasons=tuple(hard_reasons + soft_reasons),
    )
