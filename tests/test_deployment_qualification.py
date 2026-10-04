import json
from pathlib import Path

import pytest

from p37_neuro.deployment import (
    DeploymentQualificationError,
    DeploymentTarget,
    RolloutPlan,
    rollout_ready,
    sha256_file,
    verify_qualification_for_deployment,
)


def _write_release_report(
    tmp_path: Path,
    *,
    artifact_id: str = "p37-v2",
    status: str = "qualifies",
    evidence_level: str = "release qualification",
    unmet_gates: list[str] | None = None,
) -> Path:
    path = tmp_path / "qualification.json"
    payload = {
        "schema_version": 1,
        "generated_at_utc": "2026-10-04T00:00:00+00:00",
        "artifact_id": artifact_id,
        "status": status,
        "evidence_level": evidence_level,
        "unmet_gates": unmet_gates or [],
        "thresholds": {"minimum_heldout_embodiments": 3},
        "evidence": {
            "artifact_id": artifact_id,
            "heldout_embodiments": 3,
            "physical_embodiments": 2,
            "cross_embodiment_success_rate": 0.8,
            "one_shot_success_rate": 0.7,
            "long_horizon_success_rate": 0.7,
            "interventions_per_hour": 0.2,
            "deterministic_safety_passed": True,
            "fleet_feedback_verified": True,
            "promotion_and_rollback_verified": True,
            "benchmark_report_uri": "artifact://benchmark",
        },
        "robot_integration": None,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_verifies_release_qualification_for_exact_artifact(tmp_path: Path) -> None:
    report = _write_release_report(tmp_path)
    digest = sha256_file(report)

    verified = verify_qualification_for_deployment(
        report,
        artifact_id="p37-v2",
        expected_sha256=digest,
    )

    assert verified.artifact_id == "p37-v2"
    assert verified.sha256 == digest
    assert verified.status == "qualifies"


def test_rejects_digest_mismatch(tmp_path: Path) -> None:
    report = _write_release_report(tmp_path)

    with pytest.raises(DeploymentQualificationError, match="SHA-256"):
        verify_qualification_for_deployment(
            report,
            artifact_id="p37-v2",
            expected_sha256="0" * 64,
        )


def test_rejects_qualification_for_different_artifact(tmp_path: Path) -> None:
    report = _write_release_report(tmp_path, artifact_id="p37-v1")

    with pytest.raises(DeploymentQualificationError, match="does not match deployment"):
        verify_qualification_for_deployment(
            report,
            artifact_id="p37-v2",
            expected_sha256=sha256_file(report),
        )


def test_rejects_failed_release_qualification(tmp_path: Path) -> None:
    report = _write_release_report(
        tmp_path,
        status="does_not_qualify",
        unmet_gates=["physical embodiment count"],
    )

    with pytest.raises(DeploymentQualificationError, match="must be 'qualifies'"):
        verify_qualification_for_deployment(
            report,
            artifact_id="p37-v2",
            expected_sha256=sha256_file(report),
        )


def test_rejects_staged_qualification_report(tmp_path: Path) -> None:
    report = tmp_path / "qualification-stage.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_id": "p37-v2",
                "robot_id": "robot-1",
                "level": "simulation",
                "status": "passed",
                "checks": [],
                "external_evidence_required": [],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(DeploymentQualificationError, match="staged qualification"):
        verify_qualification_for_deployment(
            report,
            artifact_id="p37-v2",
            expected_sha256=sha256_file(report),
        )


def test_rollout_readiness_requires_verified_qualification_digest() -> None:
    target = DeploymentTarget("acme", "factory-1", "picking", ("robot-1",))
    unverified = RolloutPlan(
        schema_version=1,
        artifact_id="p37-v2",
        previous_artifact_id="p37-v1",
        target=target,
        qualification_report_uri="/tmp/qualification.json",
        required_approvals=1,
        approvals=("robotics-lead",),
    )
    verified = RolloutPlan(
        schema_version=1,
        artifact_id="p37-v2",
        previous_artifact_id="p37-v1",
        target=target,
        qualification_report_uri="/tmp/qualification.json",
        qualification_report_sha256="a" * 64,
        required_approvals=1,
        approvals=("robotics-lead",),
    )

    assert not rollout_ready(unverified)
    assert rollout_ready(verified)
