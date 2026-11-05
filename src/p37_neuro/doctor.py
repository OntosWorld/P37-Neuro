"""Enterprise readiness diagnostics for P37 installations."""

from __future__ import annotations

import json
import platform
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from p37_neuro.deployment import load_rollout_plan, rollout_ready
from p37_neuro.integration import validate_robot_integration


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ready: bool
    detail: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class DoctorReport:
    schema_version: int
    ready: bool
    checks: tuple[DoctorCheck, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _qualification_check(path: Path) -> DoctorCheck:
    if not path.is_file():
        return DoctorCheck("qualification_report", False, f"missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return DoctorCheck("qualification_report", False, f"unreadable: {exc}")
    status = str(raw.get("status", ""))
    artifact_id = str(raw.get("artifact_id", "unknown"))
    return DoctorCheck(
        "qualification_report",
        status == "qualifies",
        f"artifact={artifact_id}, status={status or 'missing'}",
    )


def run_doctor(
    *,
    robot_manifest: str | Path | None = None,
    qualification_report: str | Path | None = None,
    rollout_plan: str | Path | None = None,
    require_cpp: bool = False,
) -> DoctorReport:
    checks: list[DoctorCheck] = []
    version = sys.version_info
    checks.append(
        DoctorCheck(
            "python",
            (version.major, version.minor) in {(3, 12), (3, 13)},
            f"{platform.python_version()} ({sys.executable})",
        )
    )
    checks.append(
        DoctorCheck(
            "operating_system",
            sys.platform.startswith("linux"),
            f"{platform.system()} {platform.release()}",
            required=False,
        )
    )

    cmake = shutil.which("cmake")
    checks.append(
        DoctorCheck(
            "cmake",
            cmake is not None or not require_cpp,
            cmake or "not found; required only for C++ runtime builds",
            required=require_cpp,
        )
    )
    compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
    checks.append(
        DoctorCheck(
            "cxx20_toolchain",
            compiler is not None or not require_cpp,
            compiler or "not found; required only for C++ runtime builds",
            required=require_cpp,
        )
    )

    if robot_manifest is not None:
        try:
            result = validate_robot_integration(robot_manifest)
        except Exception as exc:
            checks.append(DoctorCheck("robot_integration", False, str(exc)))
        else:
            detail = (
                f"{result.robot_id}: {result.action_dimension} joints at "
                f"{result.control_frequency_hz:g} Hz"
            )
            if result.warnings:
                detail += "; warnings=" + "; ".join(result.warnings)
            checks.append(DoctorCheck("robot_integration", True, detail))

    if qualification_report is not None:
        checks.append(_qualification_check(Path(qualification_report)))

    if rollout_plan is not None:
        try:
            plan = load_rollout_plan(rollout_plan)
        except Exception as exc:
            checks.append(DoctorCheck("rollout_plan", False, str(exc)))
        else:
            checks.append(
                DoctorCheck(
                    "rollout_plan",
                    rollout_ready(plan),
                    (
                        f"artifact={plan.artifact_id}; approvals="
                        f"{len(plan.approvals)}/{plan.required_approvals}; "
                        f"qualification_digest={'present' if plan.qualification_report_sha256 else 'missing'}"
                    ),
                )
            )

    ready = all(check.ready for check in checks if check.required)
    return DoctorReport(schema_version=1, ready=ready, checks=tuple(checks))


def write_doctor_report(report: DoctorReport, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination
