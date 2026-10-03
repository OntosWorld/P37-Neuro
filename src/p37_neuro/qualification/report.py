"""Executable qualification reports for P37 releases."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from p37_neuro.benchmarks.qualification import (
    QualificationEvidence,
    QualificationThresholds,
    qualify_release,
)
from p37_neuro.integration import validate_robot_integration


class QualificationReportStatus(StrEnum):
    QUALIFIES = "qualifies"
    DOES_NOT_QUALIFY = "does_not_qualify"


@dataclass(frozen=True, slots=True)
class EnterpriseQualificationReport:
    schema_version: int
    generated_at_utc: str
    artifact_id: str
    status: QualificationReportStatus
    evidence_level: str
    unmet_gates: tuple[str, ...]
    thresholds: QualificationThresholds
    evidence: QualificationEvidence
    robot_integration: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


def load_qualification_evidence(path: str | Path) -> QualificationEvidence:
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"qualification evidence does not exist: {source}")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("qualification evidence must be a mapping")
    required = (
        "artifact_id",
        "heldout_embodiments",
        "physical_embodiments",
        "cross_embodiment_success_rate",
        "one_shot_success_rate",
        "long_horizon_success_rate",
        "interventions_per_hour",
        "deterministic_safety_passed",
        "fleet_feedback_verified",
        "promotion_and_rollback_verified",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"missing qualification evidence fields: {missing}")
    return QualificationEvidence(
        artifact_id=str(raw["artifact_id"]),
        heldout_embodiments=int(raw["heldout_embodiments"]),
        physical_embodiments=int(raw["physical_embodiments"]),
        cross_embodiment_success_rate=float(raw["cross_embodiment_success_rate"]),
        one_shot_success_rate=float(raw["one_shot_success_rate"]),
        long_horizon_success_rate=float(raw["long_horizon_success_rate"]),
        interventions_per_hour=float(raw["interventions_per_hour"]),
        deterministic_safety_passed=bool(raw["deterministic_safety_passed"]),
        fleet_feedback_verified=bool(raw["fleet_feedback_verified"]),
        promotion_and_rollback_verified=bool(raw["promotion_and_rollback_verified"]),
        benchmark_report_uri=(
            None if raw.get("benchmark_report_uri") is None else str(raw["benchmark_report_uri"])
        ),
    )


def build_qualification_report(
    evidence: QualificationEvidence,
    *,
    thresholds: QualificationThresholds | None = None,
    robot_manifest: str | Path | None = None,
    evidence_level: str = "release qualification",
) -> EnterpriseQualificationReport:
    limits = thresholds or QualificationThresholds()
    result = qualify_release(evidence, limits)
    robot: dict[str, Any] | None = None
    if robot_manifest is not None:
        integration = validate_robot_integration(robot_manifest)
        robot = {
            "robot_id": integration.robot_id,
            "action_dimension": integration.action_dimension,
            "control_frequency_hz": integration.control_frequency_hz,
            "checks": list(integration.checks),
            "warnings": list(integration.warnings),
        }
    return EnterpriseQualificationReport(
        schema_version=1,
        generated_at_utc=datetime.now(UTC).isoformat(),
        artifact_id=evidence.artifact_id,
        status=(
            QualificationReportStatus.QUALIFIES
            if result.passed
            else QualificationReportStatus.DOES_NOT_QUALIFY
        ),
        evidence_level=evidence_level,
        unmet_gates=result.failed_gates,
        thresholds=limits,
        evidence=evidence,
        robot_integration=robot,
    )


def write_qualification_report(
    report: EnterpriseQualificationReport,
    output: str | Path,
) -> tuple[Path, Path]:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "qualification.json"
    md_path = destination / "qualification.md"
    json_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    gate_lines = (
        ["- none"] if not report.unmet_gates else [f"- {gate}" for gate in report.unmet_gates]
    )
    robot_lines = ["Not supplied."]
    if report.robot_integration is not None:
        robot_lines = [
            f"Robot: **{report.robot_integration['robot_id']}**",
            f"Controllable joints: {report.robot_integration['action_dimension']}",
            f"Control frequency: {report.robot_integration['control_frequency_hz']} Hz",
        ]

    md = "\n".join(
        [
            "# P37 Neuro Qualification Report",
            "",
            f"- Artifact: {report.artifact_id}",
            f"- Result: **{report.status.value.replace('_', ' ')}**",
            f"- Evidence level: {report.evidence_level}",
            f"- Generated: {report.generated_at_utc}",
            "",
            "## Robot integration",
            "",
            *robot_lines,
            "",
            "## Qualification gates requiring further validation",
            "",
            *gate_lines,
            "",
            "## Evidence",
            "",
            f"- Held-out embodiments: {report.evidence.heldout_embodiments}",
            f"- Physical embodiments: {report.evidence.physical_embodiments}",
            (
                "- Cross-embodiment success rate: "
                f"{report.evidence.cross_embodiment_success_rate:.3f}"
            ),
            f"- One-shot success rate: {report.evidence.one_shot_success_rate:.3f}",
            f"- Long-horizon success rate: {report.evidence.long_horizon_success_rate:.3f}",
            f"- Interventions/hour: {report.evidence.interventions_per_hour:.3f}",
            "",
            "This report records qualification evidence for the stated artifact and scope. "
            "It does not extend the claim beyond the evidence level shown above.",
            "",
        ]
    )
    md_path.write_text(md, encoding="utf-8")
    return json_path, md_path
