"""Demonstration context model for one-shot task conditioning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DemonstrationReference:
    uri: str
    start_s: float = 0.0
    end_s: float | None = None
    viewpoint: str | None = None

    def __post_init__(self) -> None:
        if not self.uri.strip():
            raise ValueError("demonstration uri cannot be empty")
        if self.start_s < 0:
            raise ValueError("start_s must be non-negative")
        if self.end_s is not None and self.end_s <= self.start_s:
            raise ValueError("end_s must be greater than start_s")


@dataclass(frozen=True, slots=True)
class DemonstrationContext:
    task_id: str
    demonstrations: tuple[DemonstrationReference, ...]
    instruction: str | None = None
    goal_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id cannot be empty")
        if not self.demonstrations and not self.instruction and not self.goal_refs:
            raise ValueError("task context must include a demonstration, instruction, or goal")
