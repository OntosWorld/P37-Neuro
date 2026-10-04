"""Robot Integration Kit validation and project scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from p37_neuro.core.types import ControlMode, JointType
from p37_neuro.embodiment.schema import EmbodimentSpec
from p37_neuro.integration.manifest import (
    AdapterCapabilities,
    JointMapping,
    JointSafetyOverride,
    RobotDescriptionFormat,
    RobotDescriptionRef,
    RobotIntegrationManifest,
    RuntimeInterface,
    SafetyProfile,
    SensorMapping,
    SensorRequirement,
    TransportKind,
    dump_robot_manifest,
    load_manifest_embodiment,
    load_robot_manifest,
)


@dataclass(frozen=True, slots=True)
class IntegrationValidation:
    robot_id: str
    action_dimension: int
    control_frequency_hz: float
    checks: tuple[str, ...]
    warnings: tuple[str, ...]


def _validate_joint_mappings(
    manifest: RobotIntegrationManifest,
    *,
    body_joint_names: tuple[str, ...],
    body: EmbodimentSpec,
) -> tuple[list[str], list[str]]:
    checks: list[str] = []
    warnings: list[str] = []

    if manifest.schema_version == 1:
        warnings.append("schema v1 manifest: migrate to schema v2 for explicit joint mappings")
        return checks, warnings

    if not manifest.joints:
        raise ValueError("schema v2 robot manifest requires explicit joint mappings")

    mapped = tuple(mapping.joint for mapping in manifest.joints)
    unknown = sorted(set(mapped) - set(body_joint_names))
    missing = sorted(set(body_joint_names) - set(mapped))
    if unknown:
        raise ValueError("joint mappings reference unknown joints: " + ", ".join(unknown))
    if missing:
        raise ValueError("joint mappings are missing controllable joints: " + ", ".join(missing))

    command_names = [mapping.command for mapping in manifest.joints]
    state_names = [mapping.state for mapping in manifest.joints]
    if len(command_names) != len(set(command_names)):
        raise ValueError("joint command mappings must be unique")
    if len(state_names) != len(set(state_names)):
        raise ValueError("joint state mappings must be unique")

    for mapping in manifest.joints:
        joint = body.joint(mapping.joint)
        if not manifest.capabilities.supports(mapping.control_mode):
            raise ValueError(
                f"adapter capabilities do not support {mapping.control_mode.value} "
                f"control required by joint {mapping.joint}"
            )
        expected_unit = "m" if joint.joint_type is JointType.PRISMATIC else "rad"
        if mapping.unit != expected_unit:
            raise ValueError(
                f"joint {mapping.joint} uses unit {mapping.unit!r}; expected {expected_unit!r}"
            )
        override = mapping.safety
        if (
            override.velocity_limit is not None
            and joint.velocity_limit is not None
            and override.velocity_limit > joint.velocity_limit
        ):
            raise ValueError(
                f"joint {mapping.joint} velocity safety override exceeds robot limit"
            )
        if (
            override.effort_limit is not None
            and joint.effort_limit is not None
            and override.effort_limit > joint.effort_limit
        ):
            raise ValueError(
                f"joint {mapping.joint} effort safety override exceeds robot limit"
            )
        if joint.position is not None:
            if override.position_min is not None and override.position_min < joint.position.minimum:
                raise ValueError(
                    f"joint {mapping.joint} position_min is outside robot description limit"
                )
            if override.position_max is not None and override.position_max > joint.position.maximum:
                raise ValueError(
                    f"joint {mapping.joint} position_max is outside robot description limit"
                )

    checks.extend(("joint_mapping_coverage", "joint_units", "joint_safety_overrides"))
    return checks, warnings


def validate_robot_integration(path: str | Path) -> IntegrationValidation:
    manifest = load_robot_manifest(path)
    body = load_manifest_embodiment(manifest, manifest_path=path)
    if body.action_dimension <= 0:
        raise ValueError("robot description has no controllable joints")

    checks = [
        "manifest_schema",
        "robot_description",
        "joint_contract",
        "control_frequency",
        "safety_profile",
    ]
    warnings: list[str] = []
    mapping_checks, mapping_warnings = _validate_joint_mappings(
        manifest,
        body_joint_names=tuple(joint.name for joint in body.joints),
        body=body,
    )
    checks.extend(mapping_checks)
    warnings.extend(mapping_warnings)

    if manifest.schema_version == 2:
        if not manifest.sensor_mappings:
            warnings.append("no v2 sensor mappings declared")
        else:
            required_sensors = [
                mapping.name
                for mapping in manifest.sensor_mappings
                if mapping.requirement is SensorRequirement.REQUIRED
            ]
            if required_sensors:
                checks.append("required_sensor_contract")

        if not manifest.observation_mappings:
            warnings.append("no canonical observation mappings declared")
        else:
            sensor_sources = {mapping.source for mapping in manifest.sensor_mappings}
            joint_states = {mapping.state for mapping in manifest.joints}
            allowed_sources = sensor_sources | joint_states
            unknown_observation_sources = sorted(
                mapping.source
                for mapping in manifest.observation_mappings
                if mapping.source not in allowed_sources
            )
            if unknown_observation_sources:
                raise ValueError(
                    "observation mappings reference unknown sources: "
                    + ", ".join(unknown_observation_sources)
                )
            checks.append("observation_mapping_contract")
        if not all(
            (
                manifest.capabilities.observation_read,
                manifest.capabilities.action_write,
                manifest.capabilities.stop_request,
                manifest.capabilities.health,
            )
        ):
            raise ValueError(
                "schema v2 adapter must support observation_read, action_write, "
                "stop_request and health"
            )
        checks.append("adapter_capabilities")
    elif not manifest.sensors:
        warnings.append("no sensor mappings declared")

    if not manifest.safety.require_external_estop:
        warnings.append("external emergency-stop requirement is disabled")
    if not manifest.safety.require_controller_watchdog:
        warnings.append("controller watchdog requirement is disabled")

    if manifest.runtime.transport is TransportKind.ROS2:
        checks.append("ros2_topic_contract")

    return IntegrationValidation(
        robot_id=manifest.robot_id,
        action_dimension=body.action_dimension,
        control_frequency_hz=manifest.runtime.control_frequency_hz,
        checks=tuple(checks),
        warnings=tuple(warnings),
    )


def create_robot_manifest_template(name: str, output: str | Path) -> Path:
    robot_id = name.strip()
    if not robot_id:
        raise ValueError("robot name cannot be empty")
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = RobotIntegrationManifest(
        schema_version=2,
        robot_id=robot_id,
        family="custom",
        description=RobotDescriptionRef(RobotDescriptionFormat.URDF, "robot.urdf"),
        runtime=RuntimeInterface(
            transport=TransportKind.ROS2,
            control_frequency_hz=100.0,
            state_topic="/joint_states",
            command_topic="/p37/joint_commands",
            stop_topic="/p37/stop",
        ),
        safety=SafetyProfile(),
        joints=(
            JointMapping(
                joint="replace_with_urdf_joint",
                command="replace_with_controller_command",
                state="replace_with_controller_state",
                control_mode=ControlMode.POSITION,
                unit="rad",
                safety=JointSafetyOverride(),
            ),
        ),
        sensor_mappings=(
            SensorMapping(
                name="joint_state",
                source="/joint_states",
                modality="proprioception",
                requirement=SensorRequirement.REQUIRED,
            ),
        ),
        observation_mappings=(),
        capabilities=AdapterCapabilities(
            observation_read=True,
            action_write=True,
            stop_request=True,
            health=True,
            position_control=True,
        ),
        metadata={"owner": "replace-me", "site": "replace-me"},
    )
    path = destination / "robot.yaml"
    path.write_text(dump_robot_manifest(manifest), encoding="utf-8")
    return path
