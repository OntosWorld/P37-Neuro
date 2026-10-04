import pytest

from p37_neuro.core.types import ControlMode
from p37_neuro.data.schema import Action
from p37_neuro.integration import (
    AdapterCapabilities,
    JointMapping,
    JointSafetyOverride,
    ObservationMapping,
    RawRobotObservation,
    RobotDescriptionFormat,
    RobotDescriptionRef,
    RobotIOMapper,
    MappedRobotAdapter,
    RobotIntegrationManifest,
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
