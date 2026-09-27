"""Robot-description importers into the canonical P37 embodiment schema."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


class RobotDescriptionError(ValueError):
    """Raised when a robot description cannot be normalized safely."""


def _float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise RobotDescriptionError(f"invalid numeric value: {value}") from exc


def load_urdf(path: str | Path, *, embodiment_id: str | None = None) -> EmbodimentSpec:
    """Parse controllable joints from a URDF file."""
    source = Path(path)
    root = ElementTree.parse(source).getroot()
    if root.tag != "robot":
        raise RobotDescriptionError("URDF root element must be <robot>")

    joints: list[JointSpec] = []
    for element in root.findall("joint"):
        raw_type = element.attrib.get("type", "")
        if raw_type == "fixed":
            continue
        try:
            joint_type = JointType(raw_type)
        except ValueError as exc:
            raise RobotDescriptionError(f"unsupported URDF joint type: {raw_type}") from exc

        name = element.attrib.get("name", "").strip()
        limit = element.find("limit")
        lower = _float(limit.attrib.get("lower")) if limit is not None else None
        upper = _float(limit.attrib.get("upper")) if limit is not None else None
        velocity = _float(limit.attrib.get("velocity")) if limit is not None else None
        effort = _float(limit.attrib.get("effort")) if limit is not None else None

        position: NumericRange | None = None
        if joint_type is not JointType.CONTINUOUS:
            if lower is None or upper is None:
                raise RobotDescriptionError(f"bounded joint {name!r} requires lower/upper limits")
            position = NumericRange(lower, upper)

        joints.append(
            JointSpec(
                name=name,
                joint_type=joint_type,
                control_mode=ControlMode.POSITION,
                position=position,
                velocity_limit=velocity,
                effort_limit=effort,
            )
        )

    robot_name = root.attrib.get("name", source.stem)
    return EmbodimentSpec(
        embodiment_id=embodiment_id or robot_name,
        family="urdf",
        joints=tuple(joints),
        metadata={"source_format": "urdf", "source_path": str(source)},
    )


def load_mjcf(path: str | Path, *, embodiment_id: str | None = None) -> EmbodimentSpec:
    """Parse hinge/slide joints from an MJCF file."""
    source = Path(path)
    root = ElementTree.parse(source).getroot()
    if root.tag != "mujoco":
        raise RobotDescriptionError("MJCF root element must be <mujoco>")

    joints: list[JointSpec] = []
    for element in root.findall(".//joint"):
        raw_type = element.attrib.get("type", "hinge")
        if raw_type == "free":
            continue
        if raw_type == "hinge":
            joint_type = JointType.REVOLUTE
        elif raw_type == "slide":
            joint_type = JointType.PRISMATIC
        else:
            raise RobotDescriptionError(f"unsupported MJCF joint type: {raw_type}")

        name = element.attrib.get("name", "").strip()
        raw_range = element.attrib.get("range")
        position: NumericRange | None = None
        if raw_range:
            pieces = raw_range.split()
            if len(pieces) != 2:
                raise RobotDescriptionError(f"invalid MJCF range for {name!r}")
            position = NumericRange(float(pieces[0]), float(pieces[1]))

        joints.append(
            JointSpec(
                name=name,
                joint_type=joint_type,
                control_mode=ControlMode.POSITION,
                position=position,
            )
        )

    model_name = root.attrib.get("model", source.stem)
    return EmbodimentSpec(
        embodiment_id=embodiment_id or model_name,
        family="mjcf",
        joints=tuple(joints),
        metadata={"source_format": "mjcf", "source_path": str(source)},
    )
