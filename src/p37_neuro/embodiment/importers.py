"""Robot-description importers into the canonical P37 embodiment schema."""

from __future__ import annotations

from importlib import import_module
from math import isfinite, radians
from pathlib import Path
from typing import Any
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
                control_mode=(
                    ControlMode.VELOCITY
                    if joint_type is JointType.CONTINUOUS
                    else ControlMode.POSITION
                ),
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
        else:
            raise RobotDescriptionError(
                f"MJCF joint {name!r} requires an explicit range for position control"
            )

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


def load_usd(path: str | Path, *, embodiment_id: str | None = None) -> EmbodimentSpec:
    """Load OpenUSD Physics revolute/prismatic joints.

    OpenUSD revolute limits are authored in degrees and are converted to radians.
    Prismatic limits are authored in stage distance units and converted to metres.
    The importer is intentionally lazy so the core package remains usable outside
    Isaac/OpenUSD environments.
    """
    source = Path(path)
    try:
        usd: Any = import_module("pxr.Usd")
        usd_geom: Any = import_module("pxr.UsdGeom")
        usd_physics: Any = import_module("pxr.UsdPhysics")
    except ModuleNotFoundError as exc:
        raise RobotDescriptionError(
            "OpenUSD Python bindings are required to import USD robot descriptions"
        ) from exc

    stage = usd.Stage.Open(str(source))
    if stage is None:
        raise RobotDescriptionError(f"unable to open USD stage: {source}")

    metres_per_unit = float(usd_geom.GetStageMetersPerUnit(stage))
    joints: list[JointSpec] = []

    for prim in stage.Traverse():
        joint_type: JointType | None = None
        lower: float | None = None
        upper: float | None = None

        if prim.IsA(usd_physics.RevoluteJoint):
            schema = usd_physics.RevoluteJoint(prim)
            joint_type = JointType.REVOLUTE
            raw_lower = schema.GetLowerLimitAttr().Get()
            raw_upper = schema.GetUpperLimitAttr().Get()
            if raw_lower is not None and raw_upper is not None:
                lower = radians(float(raw_lower))
                upper = radians(float(raw_upper))
        elif prim.IsA(usd_physics.PrismaticJoint):
            schema = usd_physics.PrismaticJoint(prim)
            joint_type = JointType.PRISMATIC
            raw_lower = schema.GetLowerLimitAttr().Get()
            raw_upper = schema.GetUpperLimitAttr().Get()
            if raw_lower is not None and raw_upper is not None:
                lower = float(raw_lower) * metres_per_unit
                upper = float(raw_upper) * metres_per_unit

        if joint_type is None:
            continue

        name = str(prim.GetName()).strip()
        if not name:
            raise RobotDescriptionError("USD physics joint has no name")

        bounded = lower is not None and upper is not None and isfinite(lower) and isfinite(upper)
        if not bounded:
            if joint_type is JointType.REVOLUTE:
                joints.append(
                    JointSpec(
                        name=name,
                        joint_type=JointType.CONTINUOUS,
                        control_mode=ControlMode.VELOCITY,
                    )
                )
                continue
            raise RobotDescriptionError(
                f"USD prismatic joint {name!r} requires finite lower/upper limits"
            )

        assert lower is not None and upper is not None
        joints.append(
            JointSpec(
                name=name,
                joint_type=joint_type,
                control_mode=ControlMode.POSITION,
                position=NumericRange(lower, upper),
            )
        )

    if not joints:
        raise RobotDescriptionError("USD stage contains no supported physics joints")

    return EmbodimentSpec(
        embodiment_id=embodiment_id or source.stem,
        family="usd",
        joints=tuple(joints),
        metadata={
            "source_format": "usd",
            "source_path": str(source),
            "metres_per_unit": str(metres_per_unit),
        },
    )
