"""Teleoperation sample normalization."""

from __future__ import annotations

from dataclasses import dataclass

from p37_neuro.data.schema import Action, Observation


@dataclass(frozen=True, slots=True)
class TeleopSample:
    operator_id: str
    observation: Observation
    action: Action
    accepted: bool = True

    def __post_init__(self) -> None:
        if not self.operator_id.strip():
            raise ValueError("operator_id cannot be empty")
