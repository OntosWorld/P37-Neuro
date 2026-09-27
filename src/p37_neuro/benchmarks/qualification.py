"""Release-level qualification gate for a complete P37 robot-brain candidate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QualificationThresholds:
    """Minimum evidence required before calling a release capability-validated."""

    minimum_heldout_embodiments: int = 3
    minimum_physical_embodiments: int = 2
    minimum_cross_embodiment_success_rate: float = 0.70
    minimum_one_shot_success_rate: float = 0.60
    minimum_long_horizon_success_rate: float = 0.60
    maximum_interventions_per_hour: float = 1.0

    def __post_init__(self) -> None:
        if self.minimum_heldout_embodiments <= 0 or self.minimum_physical_embodiments <= 0:
            raise ValueError("embodiment thresholds must be positive")
        for value in (
            self.minimum_cross_embodiment_success_rate,
            self.minimum_one_shot_success_rate,
            self.minimum_long_horizon_success_rate,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("success-rate thresholds must be in [0, 1]")
        if self.maximum_interventions_per_hour < 0:
            raise ValueError("maximum_interventions_per_hour must be non-negative")


@dataclass(frozen=True, slots=True)
class QualificationEvidence:
    """Measured evidence for one immutable model release."""

    artifact_id: str
    heldout_embodiments: int
    physical_embodiments: int
    cross_embodiment_success_rate: float
    one_shot_success_rate: float
    long_horizon_success_rate: float
    interventions_per_hour: float
    deterministic_safety_passed: bool
    fleet_feedback_verified: bool
    promotion_and_rollback_verified: bool
    benchmark_report_uri: str | None

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact_id cannot be empty")
        if self.heldout_embodiments < 0 or self.physical_embodiments < 0:
            raise ValueError("embodiment counts must be non-negative")
        for value in (
            self.cross_embodiment_success_rate,
            self.one_shot_success_rate,
            self.long_horizon_success_rate,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("success rates must be in [0, 1]")
        if self.interventions_per_hour < 0:
            raise ValueError("interventions_per_hour must be non-negative")


@dataclass(frozen=True, slots=True)
class QualificationResult:
    passed: bool
    failed_gates: tuple[str, ...]


def qualify_release(
    evidence: QualificationEvidence,
    thresholds: QualificationThresholds | None = None,
) -> QualificationResult:
    """Evaluate a release without hiding missing physical evidence."""
    limits = thresholds or QualificationThresholds()
    failures: list[str] = []

    if evidence.heldout_embodiments < limits.minimum_heldout_embodiments:
        failures.append("heldout_embodiments")
    if evidence.physical_embodiments < limits.minimum_physical_embodiments:
        failures.append("physical_embodiments")
    if evidence.cross_embodiment_success_rate < limits.minimum_cross_embodiment_success_rate:
        failures.append("cross_embodiment_success_rate")
    if evidence.one_shot_success_rate < limits.minimum_one_shot_success_rate:
        failures.append("one_shot_success_rate")
    if evidence.long_horizon_success_rate < limits.minimum_long_horizon_success_rate:
        failures.append("long_horizon_success_rate")
    if evidence.interventions_per_hour > limits.maximum_interventions_per_hour:
        failures.append("interventions_per_hour")
    if not evidence.deterministic_safety_passed:
        failures.append("deterministic_safety")
    if not evidence.fleet_feedback_verified:
        failures.append("fleet_feedback")
    if not evidence.promotion_and_rollback_verified:
        failures.append("promotion_and_rollback")
    if evidence.benchmark_report_uri is None or not evidence.benchmark_report_uri.strip():
        failures.append("benchmark_report")

    return QualificationResult(passed=not failures, failed_gates=tuple(failures))
