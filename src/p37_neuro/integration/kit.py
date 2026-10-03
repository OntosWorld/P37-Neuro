"""Robot Integration Kit validation and project scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from p37_neuro.integration.manifest import (
    RobotDescriptionFormat,
    RobotDescriptionRef,
    RobotIntegrationManifest,
    RuntimeInterface,
    SafetyProfile,
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
    if not manifest.sensors:
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
        schema_version=1,
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
        sensors={"joint_state": "/joint_states"},
        metadata={"owner": "replace-me", "site": "replace-me"},
    )
    path = destination / "robot.yaml"
    path.write_text(dump_robot_manifest(manifest), encoding="utf-8")
    return path
