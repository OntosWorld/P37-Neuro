import json
from pathlib import Path

from p37_neuro.artifact_schemas import export_schemas, schema_names
from p37_neuro.doctor import run_doctor, write_doctor_report


def test_doctor_reports_core_environment() -> None:
    report = run_doctor()
    names = {check.name for check in report.checks}
    assert {"python", "cmake", "cxx20_toolchain"} <= names


def test_doctor_writes_machine_readable_report(tmp_path: Path) -> None:
    output = write_doctor_report(run_doctor(), tmp_path / "doctor.json")
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["schema_version"] == 1
    assert isinstance(raw["checks"], list)


def test_exported_artifact_schemas_are_versioned_json(tmp_path: Path) -> None:
    assert "robot-manifest-v2" in schema_names()
    exported = export_schemas(tmp_path)
    assert len(exported) == 4
    for path in exported:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["$schema"].endswith("2020-12/schema")
