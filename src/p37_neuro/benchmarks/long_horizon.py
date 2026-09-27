"""Long-horizon task evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LongHorizonResult:
    task_id: str
    completed_stages: int
    total_stages: int
    recoveries: int
    interventions: int
    completed: bool

    @property
    def progress(self) -> float:
        if self.total_stages <= 0:
            raise ValueError("total_stages must be positive")
        return self.completed_stages / self.total_stages
