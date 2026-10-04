"""Declarative robot-integration manifest for P37 Neuro."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from p37_neuro.core.types import ControlMode
from p37_neuro.embodiment.importers import load_mjcf, load_urdf, load_usd
from p37_neuro.embodiment.schema import EmbodimentSpec


class RobotManifestError(ValueError):
    """Raised when a robot integration manifest is invalid."""


class RobotDescriptionFormat(StrEnum):
    URDF = "urdf"
    MJCF = "mjcf"
    USD = "usd"


class TransportKind(StrEnum):
    ROS2 = "ros2"
    DIRECT = "direct"
    REPLAY = "replay"


class SensorRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class RobotDescriptionRef:
    format: RobotDescriptionFormat
    path: str

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise RobotManifestError("description.path cannot be empty")


@dataclass(frozen=True, slots=True)
class RuntimeInterface:
    transport: TransportKind
    control_frequency_hz: float
    state_topic: str | None = None
    command_topic: str | None = None
    stop_topic: str | None = None

    def __post_init__(self) -> None:
        if self.control_frequency_hz <= 0:
            raise RobotManifestError("runtime.control_frequency_hz must be positive")
        if self.transport is TransportKind.ROS2:
            for name, value in (
                ("state_topic", self.state_topic),
                ("command_topic", self.command_topic),
                ("stop_topic", self.stop_topic),
            ):
                if value is None or not value.strip():
                    raise RobotManifestError(f"runtime.{name} is required for ros2")


@dataclass(frozen=True, slots=True)
class JointSafetyOverride:
    position_min: float | None = None
    position_max: float | None = None
    velocity_limit: float | None = None
    effort_limit: float | None = None

    def __post_init__(self) -> None:
        if (
            self.position_min is not None
            and self.position_max is not None
            and self.position_min > self.position_max
        ):
            raise RobotManifestError("joint safety position_min cannot exceed position_max")
        for name, value in (
            ("velocity_limit", self.velocity_limit),
            ("effort_limit", self.effort_limit),
        ):
            if value is not None and value <= 0:
                raise RobotManifestError(f"joint safety {name} must be positive")


@dataclass(frozen=True, slots=True)
class JointMapping:
    joint: str
    command: str
    state: str
    control_mode: ControlMode
    unit: str
    scale: float = 1.0
    offset: float = 0.0
    safety: JointSafetyOverride = JointSafetyOverride()

    def __post_init__(self) -> None:
        for name, value in (
            ("joint", self.joint),
            ("command", self.command),
            ("state", self.state),
        ):
            if not value.strip():
                raise RobotManifestError(f"joint mapping {name} cannot be empty")
        if not self.unit.strip():
            raise RobotManifestError("joint mapping unit cannot be empty")
        if self.scale == 0:
            raise RobotManifestError("joint mapping scale cannot be zero")


@dataclass(frozen=True, slots=True)
class SensorMapping:
    name: str
    source: str
    modality: str
    requirement: SensorRequirement = SensorRequirement.OPTIONAL
    frame: str | None = None

    def __post_init__(self) -> None:
        for field_name, value in (
            ("name", self.name),
            ("source", self.source),
            ("modality", self.modality),
        ):
            if not value.strip():
                raise RobotManifestError(f"sensor mapping {field_name} cannot be empty")


@dataclass(frozen=True, slots=True)
class ObservationMapping:
    target: str
    source: str
    unit: str | None = None
    scale: float = 1.0
    offset: float = 0.0
    required: bool = True

    def __post_init__(self) -> None:
        if not self.target.strip() or not self.source.strip():
            raise RobotManifestError("observation target and source are required")
        if self.scale == 0:
            raise RobotManifestError("observation mapping scale cannot be zero")


@dataclass(frozen=True, slots=True)
class EndEffectorMapping:
    name: str
    link: str
    command_group: str | None = None
    frame: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.link.strip():
            raise RobotManifestError("end-effector name and link are required")


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    observation_read: bool = True
    action_write: bool = True
    stop_request: bool = True
    health: bool = True
    position_control: bool = True
    velocity_control: bool = False
    effort_control: bool = False
    time_synchronized: bool = False

    def supports(self, mode: ControlMode) -> bool:
        if mode is ControlMode.POSITION:
            return self.position_control
        if mode is ControlMode.VELOCITY:
            return self.velocity_control
        return self.effort_control


@dataclass(frozen=True, slots=True)
class SafetyProfile:
    max_observation_age_s: float = 0.1
    require_external_estop: bool = True
    require_controller_watchdog: bool = True

    def __post_init__(self) -> None:
        if self.max_observation_age_s <= 0:
            raise RobotManifestError("safety.max_observation_age_s must be positive")


@dataclass(frozen=True, slots=True)
class RobotIntegrationManifest:
    schema_version: int
    robot_id: str
    family: str
    description: RobotDescriptionRef
    runtime: RuntimeInterface
    safety: SafetyProfile = SafetyProfile()
    sensors: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    joints: tuple[JointMapping, ...] = ()
    sensor_mappings: tuple[SensorMapping, ...] = ()
    observation_mappings: tuple[ObservationMapping, ...] = ()
    end_effectors: tuple[EndEffectorMapping, ...] = ()
    capabilities: AdapterCapabilities = AdapterCapabilities()

    def __post_init__(self) -> None:
        if self.schema_version not in (1, 2):
            raise RobotManifestError(f"unsupported robot manifest schema: {self.schema_version}")
        if not self.robot_id.strip():
            raise RobotManifestError("robot_id cannot be empty")
        if not self.family.strip():
            raise RobotManifestError("family cannot be empty")
        joint_names = [mapping.joint for mapping in self.joints]
        if len(joint_names) != len(set(joint_names)):
            raise RobotManifestError("joint mappings must be unique by canonical joint")
        sensor_names = [mapping.name for mapping in self.sensor_mappings]
        if len(sensor_names) != len(set(sensor_names)):
            raise RobotManifestError("sensor mappings must use unique names")
        observation_targets = [mapping.target for mapping in self.observation_mappings]
        if len(observation_targets) != len(set(observation_targets)):
            raise RobotManifestError("observation mappings must use unique canonical targets")
        end_effector_names = [mapping.name for mapping in self.end_effectors]
        if len(end_effector_names) != len(set(end_effector_names)):
            raise RobotManifestError("end-effector mappings must use unique names")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["description"]["format"] = self.description.format.value
        value["runtime"]["transport"] = self.runtime.transport.value
        if self.schema_version == 1:
            value.pop("joints", None)
            value.pop("sensor_mappings", None)
            value.pop("observation_mappings", None)
            value.pop("end_effectors", None)
            value.pop("capabilities", None)
            return value

        value["joints"] = []
        for mapping in self.joints:
            item = asdict(mapping)
            item["control_mode"] = mapping.control_mode.value
            value["joints"].append(item)
        value["sensor_mappings"] = []
        for mapping in self.sensor_mappings:
            item = asdict(mapping)
            item["requirement"] = mapping.requirement.value
            value["sensor_mappings"].append(item)
        return value


def _mapping(raw: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RobotManifestError(f"{field_name} must be a mapping")
    return raw


def _sequence(raw: Any, field_name: str) -> list[Any]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RobotManifestError(f"{field_name} must be a list")
    return raw


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _load_joint_mapping(raw: Any) -> JointMapping:
    item = _mapping(raw, "joints[]")
    safety_raw = _mapping(item.get("safety", {}), "joints[].safety")
    try:
        return JointMapping(
            joint=str(item["joint"]),
            command=str(item["command"]),
            state=str(item["state"]),
            control_mode=ControlMode(str(item["control_mode"])),
            unit=str(item["unit"]),
            scale=float(item.get("scale", 1.0)),
            offset=float(item.get("offset", 0.0)),
            safety=JointSafetyOverride(
                position_min=_optional_float(safety_raw.get("position_min")),
                position_max=_optional_float(safety_raw.get("position_max")),
                velocity_limit=_optional_float(safety_raw.get("velocity_limit")),
                effort_limit=_optional_float(safety_raw.get("effort_limit")),
            ),
        )
    except KeyError as exc:
        raise RobotManifestError(f"missing joint mapping field: {exc.args[0]}") from exc


def _load_sensor_mapping(raw: Any) -> SensorMapping:
    item = _mapping(raw, "sensor_mappings[]")
    try:
        return SensorMapping(
            name=str(item["name"]),
            source=str(item["source"]),
            modality=str(item["modality"]),
            requirement=SensorRequirement(str(item.get("requirement", "optional"))),
            frame=_optional_string(item.get("frame")),
        )
    except KeyError as exc:
        raise RobotManifestError(f"missing sensor mapping field: {exc.args[0]}") from exc


def _load_observation_mapping(raw: Any) -> ObservationMapping:
    item = _mapping(raw, "observation_mappings[]")
    try:
        return ObservationMapping(
            target=str(item["target"]),
            source=str(item["source"]),
            unit=_optional_string(item.get("unit")),
            scale=float(item.get("scale", 1.0)),
            offset=float(item.get("offset", 0.0)),
            required=bool(item.get("required", True)),
        )
    except KeyError as exc:
        raise RobotManifestError(f"missing observation mapping field: {exc.args[0]}") from exc


def _load_end_effector(raw: Any) -> EndEffectorMapping:
    item = _mapping(raw, "end_effectors[]")
    try:
        return EndEffectorMapping(
            name=str(item["name"]),
            link=str(item["link"]),
            command_group=_optional_string(item.get("command_group")),
            frame=_optional_string(item.get("frame")),
        )
    except KeyError as exc:
        raise RobotManifestError(f"missing end-effector field: {exc.args[0]}") from exc


def load_robot_manifest(path: str | Path) -> RobotIntegrationManifest:
    source = Path(path)
    if not source.is_file():
        raise RobotManifestError(f"robot manifest does not exist: {source}")
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    root = _mapping(raw, "manifest")
    description = _mapping(root.get("description"), "description")
    runtime = _mapping(root.get("runtime"), "runtime")
    safety_raw = _mapping(root.get("safety", {}), "safety")
    sensors_raw = _mapping(root.get("sensors", {}), "sensors")
    metadata_raw = _mapping(root.get("metadata", {}), "metadata")
    capabilities_raw = _mapping(root.get("capabilities", {}), "capabilities")
    try:
        description_ref = RobotDescriptionRef(
            format=RobotDescriptionFormat(str(description["format"])),
            path=str(description["path"]),
        )
        runtime_interface = RuntimeInterface(
            transport=TransportKind(str(runtime["transport"])),
            control_frequency_hz=float(runtime["control_frequency_hz"]),
            state_topic=_optional_string(runtime.get("state_topic")),
            command_topic=_optional_string(runtime.get("command_topic")),
            stop_topic=_optional_string(runtime.get("stop_topic")),
        )
    except KeyError as exc:
        raise RobotManifestError(f"missing robot manifest field: {exc.args[0]}") from exc

    return RobotIntegrationManifest(
        schema_version=int(root.get("schema_version", 0)),
        robot_id=str(root.get("robot_id", "")),
        family=str(root.get("family", "")),
        description=description_ref,
        runtime=runtime_interface,
        safety=SafetyProfile(
            max_observation_age_s=float(safety_raw.get("max_observation_age_s", 0.1)),
            require_external_estop=bool(safety_raw.get("require_external_estop", True)),
            require_controller_watchdog=bool(safety_raw.get("require_controller_watchdog", True)),
        ),
        sensors={str(k): str(v) for k, v in sensors_raw.items()},
        metadata={str(k): str(v) for k, v in metadata_raw.items()},
        joints=tuple(_load_joint_mapping(item) for item in _sequence(root.get("joints"), "joints")),
        sensor_mappings=tuple(
            _load_sensor_mapping(item)
            for item in _sequence(root.get("sensor_mappings"), "sensor_mappings")
        ),
        observation_mappings=tuple(
            _load_observation_mapping(item)
            for item in _sequence(root.get("observation_mappings"), "observation_mappings")
        ),
        end_effectors=tuple(
            _load_end_effector(item)
            for item in _sequence(root.get("end_effectors"), "end_effectors")
        ),
        capabilities=AdapterCapabilities(
            observation_read=bool(capabilities_raw.get("observation_read", True)),
            action_write=bool(capabilities_raw.get("action_write", True)),
            stop_request=bool(capabilities_raw.get("stop_request", True)),
            health=bool(capabilities_raw.get("health", True)),
            position_control=bool(capabilities_raw.get("position_control", True)),
            velocity_control=bool(capabilities_raw.get("velocity_control", False)),
            effort_control=bool(capabilities_raw.get("effort_control", False)),
            time_synchronized=bool(capabilities_raw.get("time_synchronized", False)),
        ),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def resolve_description(
    manifest: RobotIntegrationManifest,
    *,
    manifest_path: str | Path,
) -> Path:
    candidate = Path(manifest.description.path)
    if not candidate.is_absolute():
        candidate = Path(manifest_path).resolve().parent / candidate
    return candidate.resolve()


def load_manifest_embodiment(
    manifest: RobotIntegrationManifest,
    *,
    manifest_path: str | Path,
) -> EmbodimentSpec:
    description_path = resolve_description(manifest, manifest_path=manifest_path)
    if not description_path.is_file():
        raise RobotManifestError(f"robot description does not exist: {description_path}")
    if manifest.description.format is RobotDescriptionFormat.URDF:
        return load_urdf(description_path, embodiment_id=manifest.robot_id)
    if manifest.description.format is RobotDescriptionFormat.MJCF:
        return load_mjcf(description_path, embodiment_id=manifest.robot_id)
    return load_usd(description_path, embodiment_id=manifest.robot_id)


def dump_robot_manifest(manifest: RobotIntegrationManifest) -> str:
    return yaml.safe_dump(manifest.to_dict(), sort_keys=False)
