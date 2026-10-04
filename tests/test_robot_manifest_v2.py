from pathlib import Path

import pytest

from p37_neuro.integration import load_robot_manifest, validate_robot_integration


def _write_urdf(tmp_path: Path) -> None:
    (tmp_path / "robot.urdf").write_text(
        """
<robot name="mapped">
  <link name="base"/>
  <link name="arm"/>
  <joint name="joint_1" type="revolute">
    <parent link="base"/><child link="arm"/>
    <limit lower="-1.0" upper="1.0" velocity="2.0" effort="10.0"/>
  </joint>
</robot>
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _write_v2(tmp_path: Path, *, joint: str = "joint_1", velocity: float = 1.5) -> Path:
    manifest = tmp_path / "robot.yaml"
    manifest.write_text(
        f"""
schema_version: 2
robot_id: mapped-robot
family: arm
description:
  format: urdf
  path: robot.urdf
runtime:
  transport: ros2
  control_frequency_hz: 100
  state_topic: /joint_states
  command_topic: /commands
  stop_topic: /stop
safety:
  max_observation_age_s: 0.1
  require_external_estop: true
  require_controller_watchdog: true
joints:
  - joint: {joint}
    command: motor_1
    state: encoder_1
    control_mode: position
    unit: rad
    safety:
      position_min: -0.9
      position_max: 0.9
      velocity_limit: {velocity}
      effort_limit: 9.0
sensor_mappings:
  - name: joint_state
    source: /joint_states
    modality: proprioception
    requirement: required
observation_mappings:
  - target: proprioception.joint_1_position
    source: encoder_1
    unit: rad
end_effectors:
  - name: tool
    link: arm
capabilities:
  observation_read: true
  action_write: true
  stop_request: true
  health: true
  position_control: true
metadata:
  owner: test
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_schema_v2_validates_explicit_robot_mapping(tmp_path: Path) -> None:
    _write_urdf(tmp_path)
    manifest_path = _write_v2(tmp_path)
    manifest = load_robot_manifest(manifest_path)
    result = validate_robot_integration(manifest_path)

    assert manifest.schema_version == 2
    assert manifest.joints[0].command == "motor_1"
    assert manifest.sensor_mappings[0].name == "joint_state"
    assert manifest.observation_mappings[0].target == "proprioception.joint_1_position"
    assert manifest.end_effectors[0].link == "arm"
    assert "joint_mapping_coverage" in result.checks
    assert "observation_mapping_contract" in result.checks
    assert "adapter_capabilities" in result.checks
    assert result.warnings == ()


def test_schema_v2_rejects_unknown_joint_mapping(tmp_path: Path) -> None:
    _write_urdf(tmp_path)
    manifest_path = _write_v2(tmp_path, joint="missing_joint")

    with pytest.raises(ValueError, match="unknown joints"):
        validate_robot_integration(manifest_path)


def test_schema_v2_rejects_safety_limit_above_robot_description(tmp_path: Path) -> None:
    _write_urdf(tmp_path)
    manifest_path = _write_v2(tmp_path, velocity=3.0)

    with pytest.raises(ValueError, match="velocity safety override exceeds"):
        validate_robot_integration(manifest_path)


def test_schema_v1_remains_readable_with_migration_warning(tmp_path: Path) -> None:
    _write_urdf(tmp_path)
    manifest = tmp_path / "robot-v1.yaml"
    manifest.write_text(
        """
schema_version: 1
robot_id: legacy
family: arm
description:
  format: urdf
  path: robot.urdf
runtime:
  transport: replay
  control_frequency_hz: 100
safety:
  max_observation_age_s: 0.1
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = validate_robot_integration(manifest)

    assert any("migrate to schema v2" in warning for warning in result.warnings)


def test_schema_v2_rejects_unknown_observation_source(tmp_path: Path) -> None:
    _write_urdf(tmp_path)
    manifest_path = _write_v2(tmp_path)
    content = manifest_path.read_text(encoding="utf-8").replace(
        "source: encoder_1",
        "source: missing_sensor",
    )
    manifest_path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="observation mappings reference unknown sources"):
        validate_robot_integration(manifest_path)
