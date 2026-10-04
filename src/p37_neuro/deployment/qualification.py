"""Qualification verification required before creating a deployment rollout."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DeploymentQualificationError(ValueError):
    """Raised when a qualification report is not safe to use for deployment."""


@dataclass(frozen=True, slots=True)
class VerifiedQualification:
    artifact_id: str
    report_path: Path
    sha256: str
    evidence_level: str
    status: str


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a report file."""
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_qualification_for_deployment(
    report_path: str | Path,
    *,
    artifact_id: str,
    expected_sha256: str,
) -> VerifiedQualification:
    """Verify a release qualification is deployable for exactly one artifact."""
    source = Path(report_path)
    if not source.is_file():
        raise DeploymentQualificationError(
            "qualification report must be a local file that can be verified before deployment"
        )

    expected_digest = expected_sha256.strip().lower()
    if len(expected_digest) != 64 or any(ch not in "0123456789abcdef" for ch in expected_digest):
        raise DeploymentQualificationError(
            "qualification SHA-256 must be a 64-character hexadecimal digest"
        )

    actual_digest = sha256_file(source)
    if actual_digest != expected_digest:
        raise DeploymentQualificationError(
            "qualification report SHA-256 does not match the trusted expected digest"
        )

    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentQualificationError("qualification report is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise DeploymentQualificationError("qualification report must be a JSON object")

    _require_release_report_shape(raw)

    report_artifact = str(raw["artifact_id"])
    requested_artifact = artifact_id.strip()
    if report_artifact != requested_artifact:
        raise DeploymentQualificationError(
            f"qualification artifact {report_artifact!r} does not match deployment "
            f"artifact {requested_artifact!r}"
        )

    status = str(raw["status"])
    if status != "qualifies":
        raise DeploymentQualificationError(
            f"qualification status must be 'qualifies', got {status!r}"
        )

    evidence_level = str(raw["evidence_level"])
    if evidence_level != "release qualification":
        raise DeploymentQualificationError(
            "deployment requires a full release qualification report; "
            f"got evidence level {evidence_level!r}"
        )

    unmet = raw["unmet_gates"]
    if not isinstance(unmet, list):
        raise DeploymentQualificationError("qualification unmet_gates must be a list")
    if unmet:
        raise DeploymentQualificationError("qualification report still has unmet release gates")

    evidence = raw["evidence"]
    if not isinstance(evidence, dict):
        raise DeploymentQualificationError("qualification evidence must be an object")
    if str(evidence.get("artifact_id", "")) != requested_artifact:
        raise DeploymentQualificationError(
            "qualification evidence artifact does not match the deployment artifact"
        )

    return VerifiedQualification(
        artifact_id=requested_artifact,
        report_path=source.resolve(),
        sha256=actual_digest,
        evidence_level=evidence_level,
        status=status,
    )


def _require_release_report_shape(raw: dict[str, Any]) -> None:
    if int(raw.get("schema_version", 0)) != 1:
        raise DeploymentQualificationError("unsupported qualification report schema")

    if "level" in raw or "external_evidence_required" in raw:
        raise DeploymentQualificationError(
            "staged qualification reports cannot authorize deployment"
        )

    required = {
        "artifact_id",
        "status",
        "evidence_level",
        "unmet_gates",
        "thresholds",
        "evidence",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise DeploymentQualificationError(
            "not a release qualification report; missing fields: " + ", ".join(missing)
        )
