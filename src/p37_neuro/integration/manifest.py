"""Declarative robot-integration manifest for P37 Neuro."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

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

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise RobotManifestError(f"unsupported robot manifest schema: {self.schema_version}")
        if not self.robot_id.strip():
            raise RobotManifestError("robot_id cannot be empty")
        if not self.family.strip():
            raise RobotManifestError("family cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["description"]["format"] = self.description.format.value
        value["runtime"]["transport"] = self.runtime.transport.value
        return value


def _mapping(raw: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RobotManifestError(f"{field_name} must be a mapping")
    return raw


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
