"""Fleet-scoped rollout plans and rollback policy."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DeploymentTarget:
    organization_id: str
    site_id: str
    fleet_id: str
    robot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not self.organization_id.strip()
            or not self.site_id.strip()
            or not self.fleet_id.strip()
        ):
            raise ValueError("organization_id, site_id and fleet_id are required")
        if not self.robot_ids:
            raise ValueError("at least one robot is required")
        if len(self.robot_ids) != len(set(self.robot_ids)):
            raise ValueError("robot_ids must be unique")
        if any(not robot.strip() for robot in self.robot_ids):
            raise ValueError("robot_ids cannot contain empty values")


@dataclass(frozen=True, slots=True)
class RolloutPlan:
    schema_version: int
    artifact_id: str
    previous_artifact_id: str
    target: DeploymentTarget
    qualification_report_uri: str
    canary_count: int = 1
    batch_size: int = 10
    maximum_unhealthy_fraction: float = 0.10

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported rollout plan schema")
        if not self.artifact_id.strip() or not self.previous_artifact_id.strip():
            raise ValueError("artifact_id and previous_artifact_id are required")
        if not self.qualification_report_uri.strip():
            raise ValueError("qualification_report_uri is required")
        if self.canary_count < 0 or self.canary_count > len(self.target.robot_ids):
            raise ValueError("canary_count must be within the target robot count")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not 0.0 <= self.maximum_unhealthy_fraction <= 1.0:
            raise ValueError("maximum_unhealthy_fraction must be in [0, 1]")

    def batches(self) -> tuple[tuple[str, ...], ...]:
        robots = self.target.robot_ids
        batches: list[tuple[str, ...]] = []
        offset = 0
        if self.canary_count:
            batches.append(robots[: self.canary_count])
            offset = self.canary_count
        while offset < len(robots):
            batches.append(robots[offset : offset + self.batch_size])
            offset += self.batch_size
        return tuple(batches)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RolloutHealth:
    evaluated_robots: int
    unhealthy_robots: int
    stop_requested: bool = False

    def __post_init__(self) -> None:
        if self.evaluated_robots < 0 or self.unhealthy_robots < 0:
            raise ValueError("robot counts must be non-negative")
        if self.unhealthy_robots > self.evaluated_robots:
            raise ValueError("unhealthy_robots cannot exceed evaluated_robots")

    @property
    def unhealthy_fraction(self) -> float:
        if self.evaluated_robots == 0:
            return 0.0
        return self.unhealthy_robots / self.evaluated_robots


def rollout_requires_rollback(plan: RolloutPlan, health: RolloutHealth) -> bool:
    return health.stop_requested or health.unhealthy_fraction > plan.maximum_unhealthy_fraction


def write_rollout_plan(plan: RolloutPlan, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination


def load_rollout_plan(path: str | Path) -> RolloutPlan:
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    target = raw["target"]
    return RolloutPlan(
        schema_version=int(raw["schema_version"]),
        artifact_id=str(raw["artifact_id"]),
        previous_artifact_id=str(raw["previous_artifact_id"]),
        target=DeploymentTarget(
            organization_id=str(target["organization_id"]),
            site_id=str(target["site_id"]),
            fleet_id=str(target["fleet_id"]),
            robot_ids=tuple(str(robot) for robot in target["robot_ids"]),
        ),
        qualification_report_uri=str(raw["qualification_report_uri"]),
        canary_count=int(raw["canary_count"]),
        batch_size=int(raw["batch_size"]),
        maximum_unhealthy_fraction=float(raw["maximum_unhealthy_fraction"]),
    )


def build_rollback_plan(plan: RolloutPlan) -> RolloutPlan:
    return RolloutPlan(
        schema_version=1,
        artifact_id=plan.previous_artifact_id,
        previous_artifact_id=plan.artifact_id,
        target=plan.target,
        qualification_report_uri=plan.qualification_report_uri,
        canary_count=0,
        batch_size=plan.batch_size,
        maximum_unhealthy_fraction=plan.maximum_unhealthy_fraction,
    )
