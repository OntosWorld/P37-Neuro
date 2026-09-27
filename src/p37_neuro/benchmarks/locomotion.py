"""Cross-morphology locomotion benchmark definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LocomotionResult:
    embodiment_id: str
    distance_m: float
    falls: int
    interventions: int
    recovered: bool

    @property
    def score(self) -> float:
        penalty = self.falls * 1.0 + self.interventions * 2.0
        bonus = 1.0 if self.recovered else 0.0
        return max(0.0, self.distance_m + bonus - penalty)


def aggregate(results: tuple[LocomotionResult, ...]) -> dict[str, float]:
    if not results:
        raise ValueError("results cannot be empty")
    return {
        "mean_score": sum(result.score for result in results) / len(results),
        "recovery_rate": sum(result.recovered for result in results) / len(results),
        "mean_interventions": sum(result.interventions for result in results) / len(results),
    }
