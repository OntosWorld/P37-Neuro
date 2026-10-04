from pathlib import Path

from p37_neuro.integration import SimulationPreflightResult
from p37_neuro.qualification import (
    QualificationLevel,
    StageQualificationStatus,
    run_staged_qualification,
)


def _write_robot(tmp_path: Path, *, transport: str = "replay") -> Path:
    (tmp_path / "robot.mjcf").write_text(
        """
<mujoco model="test">
  <worldbody>
    <body name="base">
      <body name="link">
        <joint name="joint_1" type="hinge" range="-1 1"/>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position name="joint_1_position" joint="joint_1" ctrlrange="-1 1"/>
  </actuator>
</mujoco>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    runtime = (
        """
runtime:
  transport: ros2
  control_frequency_hz: 100
  state_topic: /joint_states
  command_topic: /p37/commands
  stop_topic: /p37/stop
"""
        if transport == "ros2"
        else """
runtime:
  transport: replay
  control_frequency_hz: 100
"""
    )
    manifest = tmp_path / "robot.yaml"
    manifest.write_text(
        (
            """
schema_version: 1
robot_id: test-robot
family: test
description:
  format: mjcf
  path: robot.mjcf
"""
            + runtime
            + """
safety:
  max_observation_age_s: 0.1
  require_external_estop: true
  require_controller_watchdog: true
sensors:
  joint_state: /joint_states
"""
        ),
        encoding="utf-8",
    )
    return manifest


def test_simulation_level_executes_preflight(tmp_path: Path) -> None:
    manifest = _write_robot(tmp_path)

    def fake_runner(
        robot_manifest: str | Path,
        *,
        steps: int,
        seed: int,
    ) -> SimulationPreflightResult:
        assert Path(robot_manifest) == manifest
        assert steps == 12
        assert seed == 7
        return SimulationPreflightResult(
            robot_id="test-robot",
            backend="mujoco",
            steps=steps,
            action_dimension=1,
            final_time_s=0.12,
        )

    report = run_staged_qualification(
        robot_manifest=manifest,
        artifact_id="artifact-123",
        level=QualificationLevel.SIMULATION,
        simulation_steps=12,
        simulation_seed=7,
        simulation_runner=fake_runner,
    )

    assert report.status is StageQualificationStatus.PASSED
    assert report.level is QualificationLevel.SIMULATION
    assert [check.name for check in report.checks] == [
        "robot_integration",
        "simulation_preflight",
    ]
    assert report.external_evidence_required == ()


def test_hil_level_is_honest_about_external_evidence(tmp_path: Path) -> None:
    manifest = _write_robot(tmp_path, transport="ros2")
    report = run_staged_qualification(
        robot_manifest=manifest,
        artifact_id="artifact-123",
        level=QualificationLevel.HIL,
    )

    assert report.status is StageQualificationStatus.INCOMPLETE
    assert any(check.name == "controller_transport" and check.passed for check in report.checks)
    assert report.external_evidence_required
    assert any("watchdog" in item for item in report.external_evidence_required)


def test_physical_level_never_claims_completion_from_static_checks(tmp_path: Path) -> None:
    manifest = _write_robot(tmp_path)
    report = run_staged_qualification(
        robot_manifest=manifest,
        artifact_id="artifact-123",
        level=QualificationLevel.PHYSICAL,
    )

    assert report.status is StageQualificationStatus.INCOMPLETE
    assert any("emergency-stop" in item for item in report.external_evidence_required)
