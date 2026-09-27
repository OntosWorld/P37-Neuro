"""Progressive recovery and disturbance curricula."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CurriculumStage:
    name: str
    parameters: Mapping[str, float]
    advance_success_rate: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("curriculum stage name cannot be empty")
        if not 0.0 <= self.advance_success_rate <= 1.0:
            raise ValueError("advance_success_rate must be in [0, 1]")


@dataclass(slots=True)
class ProgressiveCurriculum:
    """Deterministic stage progression driven by held-out success rate."""

    stages: tuple[CurriculumStage, ...]
    stage_index: int = 0
    history: list[tuple[str, float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("curriculum requires at least one stage")
        if not 0 <= self.stage_index < len(self.stages):
            raise ValueError("stage_index out of range")

    @property
    def current(self) -> CurriculumStage:
        return self.stages[self.stage_index]

    @property
    def complete(self) -> bool:
        return self.stage_index == len(self.stages) - 1

    def observe(self, success_rate: float) -> CurriculumStage:
        if not 0.0 <= success_rate <= 1.0:
            raise ValueError("success_rate must be in [0, 1]")
        self.history.append((self.current.name, success_rate))
        if (
            success_rate >= self.current.advance_success_rate
            and self.stage_index < len(self.stages) - 1
        ):
            self.stage_index += 1
        return self.current


def recovery_curriculum() -> ProgressiveCurriculum:
    """Recovery curriculum from nominal errors to compound failures."""
    return ProgressiveCurriculum(
        (
            CurriculumStage(
                "retry",
                {"failed_grasp_probability": 0.1, "obstruction_probability": 0.0},
                0.90,
            ),
            CurriculumStage(
                "recover",
                {"failed_grasp_probability": 0.2, "obstruction_probability": 0.1},
                0.85,
            ),
            CurriculumStage(
                "replan",
                {
                    "failed_grasp_probability": 0.25,
                    "obstruction_probability": 0.2,
                    "goal_change_probability": 0.05,
                },
                0.80,
            ),
        )
    )


def disturbance_curriculum() -> ProgressiveCurriculum:
    """Adversarial physical curriculum for RL post-training."""
    return ProgressiveCurriculum(
        (
            CurriculumStage(
                "nominal",
                {
                    "mass_scale_span": 0.10,
                    "friction_scale_span": 0.10,
                    "external_impulse": 0.0,
                    "actuator_degradation": 0.0,
                },
                0.90,
            ),
            CurriculumStage(
                "randomized",
                {
                    "mass_scale_span": 0.25,
                    "friction_scale_span": 0.30,
                    "external_impulse": 0.15,
                    "actuator_degradation": 0.10,
                },
                0.85,
            ),
            CurriculumStage(
                "adversarial",
                {
                    "mass_scale_span": 0.40,
                    "friction_scale_span": 0.50,
                    "external_impulse": 0.35,
                    "actuator_degradation": 0.25,
                },
                0.75,
            ),
        )
    )
