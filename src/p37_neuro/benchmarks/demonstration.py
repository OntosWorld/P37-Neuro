"""One-shot unseen-task evaluation for demonstration-conditioned policies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OneShotTrial:
    """One evaluation trial with leakage controls recorded explicitly."""

    task_id: str
    embodiment_id: str
    task_was_held_out: bool
    demonstration_count: int
    gradient_updates: int
    success: bool
    completed_stages: int
    total_stages: int
    recoveries: int = 0
    interventions: int = 0
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.embodiment_id.strip():
            raise ValueError("task_id and embodiment_id cannot be empty")
        if self.demonstration_count < 0 or self.gradient_updates < 0:
            raise ValueError("demonstration_count and gradient_updates must be non-negative")
        if self.total_stages <= 0:
            raise ValueError("total_stages must be positive")
        if not 0 <= self.completed_stages <= self.total_stages:
            raise ValueError("completed_stages must be within total_stages")
        if self.recoveries < 0 or self.interventions < 0 or self.duration_s < 0:
            raise ValueError("trial counters and duration must be non-negative")

    @property
    def qualifies_as_one_shot(self) -> bool:
        """True only for held-out tasks with one demo and no weight updates."""
        return (
            self.task_was_held_out and self.demonstration_count == 1 and self.gradient_updates == 0
        )

    @property
    def progress(self) -> float:
        return self.completed_stages / self.total_stages


def one_shot_metrics(trials: tuple[OneShotTrial, ...]) -> dict[str, float]:
    """Aggregate only scientifically valid one-shot trials.

    Invalid trials are rejected instead of silently mixing fine-tuned or seen
    tasks into the headline metric.
    """
    if not trials:
        raise ValueError("trials cannot be empty")
    invalid = [trial.task_id for trial in trials if not trial.qualifies_as_one_shot]
    if invalid:
        raise ValueError(f"non-one-shot trials present: {invalid}")

    count = len(trials)
    return {
        "trial_count": float(count),
        "success_rate": sum(trial.success for trial in trials) / count,
        "mean_progress": sum(trial.progress for trial in trials) / count,
        "mean_recoveries": sum(trial.recoveries for trial in trials) / count,
        "mean_interventions": sum(trial.interventions for trial in trials) / count,
        "mean_duration_s": sum(trial.duration_s for trial in trials) / count,
        "embodiment_count": float(len({trial.embodiment_id for trial in trials})),
        "task_count": float(len({trial.task_id for trial in trials})),
    }
