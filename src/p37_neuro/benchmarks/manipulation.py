"""Manipulation transfer benchmark."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ManipulationTrial:
    embodiment_id: str
    task_id: str
    success: bool
    intervention_count: int
    duration_s: float


def transfer_metrics(trials: tuple[ManipulationTrial, ...]) -> dict[str, float]:
    if not trials:
        raise ValueError("trials cannot be empty")
    return {
        "success_rate": sum(t.success for t in trials) / len(trials),
        "mean_interventions": sum(t.intervention_count for t in trials) / len(trials),
        "mean_duration_s": sum(t.duration_s for t in trials) / len(trials),
    }
