"""Append-only deployment event logger."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FleetEvent:
    event_id: str
    robot_id: str
    model_id: str
    timestamp_s: float
    kind: str
    payload: dict[str, str | float | int | bool]


class FleetLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: FleetEvent) -> None:
        if not event.event_id.strip() or not event.robot_id.strip() or not event.model_id.strip():
            raise ValueError("event_id, robot_id and model_id are required")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")

    def read(self) -> tuple[FleetEvent, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            FleetEvent(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
