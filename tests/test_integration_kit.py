from pathlib import Path

import pytest

from p37_neuro.integration import (
    RobotManifestError,
    create_robot_manifest_template,
    load_robot_manifest,
    validate_robot_integration,
)


def _urdf(path: Path) -> None:
    path.write_text(
        '<robot name="enterprise_arm"><joint name="joint_1" type="revolute">'
        '<limit lower="-1" upper="1" velocity="2" effort="4"/>'
        "</joint></robot>",
        encoding="utf-8",
    )


def test_robot_manifest_validates_description_and_runtime(tmp_path: Path) -> None:
    _urdf(tmp_path / "robot.urdf")
    manifest_path = create_robot_manifest_template("enterprise-arm", tmp_path)
    result = validate_robot_integration(manifest_path)
    assert result.robot_id == "enterprise-arm"
    assert result.action_dimension == 1
    assert "ros2_topic_contract" in result.checks


def test_robot_manifest_rejects_missing_ros_topic(tmp_path: Path) -> None:
    _urdf(tmp_path / "robot.urdf")
    path = tmp_path / "robot.yaml"
    path.write_text(
        """
schema_version: 1
robot_id: broken
family: arm
description:
  format: urdf
  path: robot.urdf
runtime:
  transport: ros2
  control_frequency_hz: 100
  state_topic: /joint_states
  command_topic: /commands
""",
        encoding="utf-8",
    )
    with pytest.raises(RobotManifestError):
        load_robot_manifest(path)
