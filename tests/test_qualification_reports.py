from pathlib import Path

from p37_neuro.benchmarks.qualification import QualificationEvidence
from p37_neuro.qualification import (
    QualificationReportStatus,
    build_qualification_report,
    load_qualification_evidence,
    write_qualification_report,
)


def _evidence(path: Path) -> None:
    path.write_text(
        """
artifact_id: p37-enterprise-1
heldout_embodiments: 3
physical_embodiments: 2
cross_embodiment_success_rate: 0.8
one_shot_success_rate: 0.7
long_horizon_success_rate: 0.7
interventions_per_hour: 0.5
deterministic_safety_passed: true
fleet_feedback_verified: true
promotion_and_rollback_verified: true
benchmark_report_uri: s3://reports/p37-enterprise-1
""",
        encoding="utf-8",
    )


def test_qualification_report_writes_json_and_markdown(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.yaml"
    _evidence(evidence_path)
    report = build_qualification_report(load_qualification_evidence(evidence_path))
    assert report.status is QualificationReportStatus.QUALIFIES
    json_path, md_path = write_qualification_report(report, tmp_path / "report")
    assert '"status": "qualifies"' in json_path.read_text(encoding="utf-8")
    assert md_path.is_file()


def test_qualification_report_exposes_gates_requiring_more_validation(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.yaml"
    _evidence(evidence_path)
    evidence = load_qualification_evidence(evidence_path)
    report = build_qualification_report(
        QualificationEvidence(
            artifact_id=evidence.artifact_id,
            heldout_embodiments=evidence.heldout_embodiments,
            physical_embodiments=0,
            cross_embodiment_success_rate=evidence.cross_embodiment_success_rate,
            one_shot_success_rate=evidence.one_shot_success_rate,
            long_horizon_success_rate=evidence.long_horizon_success_rate,
            interventions_per_hour=evidence.interventions_per_hour,
            deterministic_safety_passed=evidence.deterministic_safety_passed,
            fleet_feedback_verified=evidence.fleet_feedback_verified,
            promotion_and_rollback_verified=evidence.promotion_and_rollback_verified,
            benchmark_report_uri=evidence.benchmark_report_uri,
        )
    )
    assert report.status is QualificationReportStatus.DOES_NOT_QUALIFY
    assert "physical_embodiments" in report.unmet_gates
