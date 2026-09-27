"""Promotion gates for post-training and physical transfer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateThresholds:
    min_success_rate: float = 0.8
    max_intervention_rate: float = 0.05
    max_catastrophic_failure_rate: float = 0.0
    max_p95_latency_ms: float = 50.0


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    success_rate: float
    intervention_rate: float
    catastrophic_failure_rate: float
    p95_latency_ms: float


@dataclass(frozen=True, slots=True)
class GateDecision:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_gate(metrics: EvaluationMetrics, thresholds: GateThresholds) -> GateDecision:
    reasons: list[str] = []
    if metrics.success_rate < thresholds.min_success_rate:
        reasons.append("success_rate")
    if metrics.intervention_rate > thresholds.max_intervention_rate:
        reasons.append("intervention_rate")
    if metrics.catastrophic_failure_rate > thresholds.max_catastrophic_failure_rate:
        reasons.append("catastrophic_failure_rate")
    if metrics.p95_latency_ms > thresholds.max_p95_latency_ms:
        reasons.append("p95_latency_ms")
    return GateDecision(passed=not reasons, reasons=tuple(reasons))
