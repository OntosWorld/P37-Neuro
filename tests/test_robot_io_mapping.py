from pathlib import Path

import pytest

from p37_neuro.core.types import ControlMode
from p37_neuro.data.schema import Action
from p37_neuro.integration import (
    AdapterCapabilities,
    AdapterHealth,
    JointMapping,
    JointSafetyOverride,
    MappedRobotAdapter,
    ObservationMapping,
    RawRobotObservation,
    RobotDescriptionFormat,
    RobotDescriptionRef,
    RobotIntegrationManifest,
    RobotIOMapper,
    RobotMappingError,
    RuntimeInterface,
    SafetyProfile,
    SensorMapping,
    SensorRequirement,
    TransportKind,
)


def _manifest() -> RobotIntegrationManifest:
    return RobotIntegrationManifest(
        schema_version=2,
        robot_id="mapped-arm",
        family="arm",
        description=RobotDescriptionRef(RobotDescriptionFormat.URDF, "robot.urdf"),
        runtime=RuntimeInterface(
            transport=TransportKind.REPLAY,
            control_frequency_hz=100.0,
        ),
        safety=SafetyProfile(),
        joints=(
            JointMapping(
                joint="shoulder",
                command="axis_1_target",
                state="axis_1_position",
                control_mode=ControlMode.POSITION,
                unit="rad",
                scale=2.0,
                offset=0.5,
                safety=JointSafetyOverride(position_min=-1.0, position_max=1.0),
            ),
        ),
        sensor_mappings=(
            SensorMapping(
                name="wrist_rgb",
                source="camera://wrist",
                modality="rgb",
                requirement=SensorRequirement.OPTIONAL,
            ),
            SensorMapping(
                name="payload_mass",
                source="payload_kg",
                modality="scalar",
                requirement=SensorRequirement.REQUIRED,
            ),
        ),
        observation_mappings=(
            ObservationMapping(
                target="state.payload_mass",
                source="payload_kg",
                unit="kg",
                scale=1.0,
            ),
            ObservationMapping(
                target="vision.wrist_rgb",
                source="camera://wrist",
                required=False,
            ),
        ),
        capabilities=AdapterCapabilities(position_control=True),
    )


def test_maps_controller_observation_into_canonical_p37_observation() -> None:
    mapper = RobotIOMapper(_manifest())
    observation = mapper.map_observation(
        RawRobotObservation(
            timestamp_s=4.0,
            values={
                "axis_1_position": 1.5,
                "payload_kg": 3.2,
            },
            sensor_refs={"camera://wrist": "frame://123"},
        )
    )

    assert observation.joint_position == {"shoulder": 0.5}
    assert observation.state == {"state.payload_mass": 3.2}
    assert observation.sensor_refs == {"vision.wrist_rgb": "frame://123"}


def test_maps_canonical_action_into_controller_command() -> None:
    mapper = RobotIOMapper(_manifest())
    command = mapper.map_action(
        Action(timestamp_s=5.0, joint_commands={"shoulder": 0.25})
    )

    assert command.timestamp_s == 5.0
    assert command.values == {"axis_1_target": 1.0}


def test_mapping_rejects_missing_required_joint_state() -> None:
    mapper = RobotIOMapper(_manifest())

    with pytest.raises(RobotMappingError, match="axis_1_position"):
        mapper.map_observation(
            RawRobotObservation(timestamp_s=1.0, values={"payload_kg": 2.0})
        )


def test_mapping_enforces_manifest_safety_before_controller_conversion() -> None:
    mapper = RobotIOMapper(_manifest())

    with pytest.raises(RobotMappingError, match="position_max"):
        mapper.map_action(
            Action(timestamp_s=5.0, joint_commands={"shoulder": 1.1})
        )


class _Transport:
    def __init__(self) -> None:
        self.commands: list[object] = []
        self.stop_reason: str | None = None

    def read_observation(self) -> RawRobotObservation:
        return RawRobotObservation(
            timestamp_s=2.0,
            values={"axis_1_position": 0.2},
        )

    def write_command(self, command: object) -> None:
        self.commands.append(command)

    def request_stop(self, reason: str) -> None:
        self.stop_reason = reason

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            connected=True,
            state_fresh=True,
            controller_ready=True,
            estop_available=True,
            watchdog_available=True,
        )


def _write_adapter_fixture(tmp_path: Path) -> Path:
    (tmp_path / "robot.urdf").write_text(
        """
<robot name="mapped">
  <link name="base"/>
  <link name="arm"/>
  <joint name="shoulder" type="revolute">
    <parent link="base"/><child link="arm"/>
    <limit lower="-1.0" upper="1.0" velocity="2.0" effort="10.0"/>
  </joint>
</robot>
""".strip()
        + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "robot.yaml"
    manifest.write_text(
        """
schema_version: 2
robot_id: mapped-arm
family: arm
description:
  format: urdf
  path: robot.urdf
runtime:
  transport: replay
  control_frequency_hz: 100
safety:
  max_observation_age_s: 0.1
  require_external_estop: true
  require_controller_watchdog: true
joints:
  - joint: shoulder
    command: axis_1_target
    state: axis_1_position
    control_mode: position
    unit: rad
    safety:
      position_min: -1.0
      position_max: 1.0
sensor_mappings: []
observation_mappings:
  - target: state.shoulder
    source: axis_1_position
    unit: rad
capabilities:
  observation_read: true
  action_write: true
  stop_request: true
  health: true
  position_control: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_mapped_adapter_wraps_raw_transport(tmp_path: Path) -> None:
    manifest_path = _write_adapter_fixture(tmp_path)
    transport = _Transport()
    adapter = MappedRobotAdapter(manifest_path, transport)

    observation = adapter.read_observation()
    adapter.write_action(Action(timestamp_s=2.0, joint_commands={"shoulder": 0.3}))
    adapter.request_stop("operator")

    assert observation.joint_position == {"shoulder": 0.2}
    assert observation.state == {"state.shoulder": 0.2}
    assert len(transport.commands) == 1
    assert transport.stop_reason == "operator"
    assert adapter.health().ready
