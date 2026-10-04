"""Staged qualification orchestration for enterprise robot integrations."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from p37_neuro.integration import (
    SimulationPreflightResult,
    run_mujoco_preflight,
    validate_robot_integration,
)
from p37_neuro.integration.manifest import TransportKind, load_robot_manifest


class QualificationLevel(StrEnum):
    """Operational qualification levels exposed by the product CLI."""

    INTEGRATION = "integration"
    SIMULATION = "simulation"
    HIL = "hil"
    PHYSICAL = "physical"
    FLEET = "fleet"


class StageQualificationStatus(StrEnum):
    PASSED = "passed"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class StageCheck:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class StageQualificationReport:
    schema_version: int
    generated_at_utc: str
    artifact_id: str
    robot_id: str
    level: QualificationLevel
    status: StageQualificationStatus
    checks: tuple[StageCheck, ...]
    external_evidence_required: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["level"] = self.level.value
        value["status"] = self.status.value
        return value


SimulationRunner = Callable[..., SimulationPreflightResult]


def run_staged_qualification(
    *,
    robot_manifest: str | Path,
    artifact_id: str,
    level: QualificationLevel,
    simulation_steps: int = 20,
    simulation_seed: int = 0,
    simulation_runner: SimulationRunner = run_mujoco_preflight,
) -> StageQualificationReport:
    """Execute every generic qualification check P37 can safely run at this level.

    Hardware-dependent levels deliberately stop at the generic integration boundary and
    record the evidence that must come from the customer/controller environment.
    """
    artifact = artifact_id.strip()
    if not artifact:
        raise ValueError("artifact_id cannot be empty")

    integration = validate_robot_integration(robot_manifest)
    manifest = load_robot_manifest(robot_manifest)
    checks: list[StageCheck] = [
        StageCheck(
            "robot_integration",
            True,
            (
                f"{integration.action_dimension} controllable joints at "
                f"{integration.control_frequency_hz:g} Hz"
            ),
        )
    ]
    required: list[str] = []

    if level is QualificationLevel.INTEGRATION:
        pass
    elif level is QualificationLevel.SIMULATION:
        result = simulation_runner(
            robot_manifest,
            steps=simulation_steps,
            seed=simulation_seed,
        )
        checks.append(
            StageCheck(
                "simulation_preflight",
                True,
                (
                    f"{result.backend}: {result.steps} steps, "
                    f"final_time={result.final_time_s:.6f}s"
                ),
            )
        )
    elif level is QualificationLevel.HIL:
        checks.append(
            StageCheck(
                "controller_transport",
                manifest.runtime.transport is TransportKind.ROS2,
                f"declared transport: {manifest.runtime.transport.value}",
            )
        )
        required.extend(
            (
                "target-compute inference latency and numerical comparison",
                "ROS 2/controller timing, stale-state, disconnect and watchdog evidence",
                "command path verified with motor power disabled or restricted I/O",
            )
        )
    elif level is QualificationLevel.PHYSICAL:
        required.extend(
            (
                "completed HIL qualification for the same artifact and robot integration",
                "independent emergency-stop and controller safety verification",
                "restricted low-speed actuation evidence",
                "supervised task success, intervention and recovery metrics",
            )
        )
    elif level is QualificationLevel.FLEET:
        required.extend(
            (
                "physical qualification evidence for deployment robot classes",
                "signed artifact and qualification-report verification",
                "canary rollout health evidence",
                "promotion and rollback audit evidence",
                "fleet feedback and dataset-lineage verification",
            )
        )
    else:  # pragma: no cover - enum exhaustiveness
        raise ValueError(f"unsupported qualification level: {level}")

    generic_checks_passed = all(check.passed for check in checks)
    status = (
        StageQualificationStatus.PASSED
        if generic_checks_passed and not required
        else StageQualificationStatus.INCOMPLETE
    )
    return StageQualificationReport(
        schema_version=1,
        generated_at_utc=datetime.now(UTC).isoformat(),
        artifact_id=artifact,
        robot_id=integration.robot_id,
        level=level,
        status=status,
        checks=tuple(checks),
        external_evidence_required=tuple(required),
    )


def write_staged_qualification_report(
    report: StageQualificationReport,
    output: str | Path,
) -> tuple[Path, Path]:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "qualification-stage.json"
    md_path = destination / "qualification-stage.md"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    check_lines = [
        f"- {'PASS' if check.passed else 'FAIL'} — {check.name}: {check.detail}"
        for check in report.checks
    ]
    evidence_lines = (
        ["- none"]
        if not report.external_evidence_required
        else [f"- {item}" for item in report.external_evidence_required]
    )
    md_path.write_text(
        "\n".join(
            [
                "# P37 Neuro Staged Qualification",
                "",
                f"- Artifact: {report.artifact_id}",
                f"- Robot: {report.robot_id}",
                f"- Level: {report.level.value}",
                f"- Status: **{report.status.value}**",
                f"- Generated: {report.generated_at_utc}",
                "",
                "## Executed checks",
                "",
                *check_lines,
                "",
                "## External evidence still required",
                "",
                *evidence_lines,
                "",
                (
                    "A passed lower-level check does not imply physical or fleet capability. "
                    "Claims are limited to the qualification level and evidence recorded here."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, md_path
