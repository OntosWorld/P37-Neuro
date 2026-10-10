"""MuJoCo-backed implementation of the canonical simulator contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree

import mujoco
import numpy as np
from numpy.typing import NDArray
from p37_neuro.core.types import ControlMode
from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.importers import load_mjcf
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


class MuJoCoConfigurationError(ValueError):
    """Raised when an MJCF control surface cannot be represented safely."""


def _ctrl_limit(element: ElementTree.Element) -> float | None:
    raw = element.attrib.get("ctrlrange")
    if not raw:
        return None
    pieces = raw.split()
    if len(pieces) != 2:
        raise MuJoCoConfigurationError("actuator ctrlrange must contain two numbers")
    low, high = float(pieces[0]), float(pieces[1])
    return max(abs(low), abs(high))


def _actuators(path: Path) -> dict[str, tuple[str, ControlMode, float | None]]:
    root = ElementTree.parse(path).getroot()
    result: dict[str, tuple[str, ControlMode, float | None]] = {}
    actuator_root = root.find("actuator")
    if actuator_root is None:
        return result
    supported = {
        "position": ControlMode.POSITION,
        "velocity": ControlMode.VELOCITY,
    }
    for element in actuator_root:
        mode = supported.get(element.tag)
        if mode is None:
            continue
        name = element.attrib.get("name", "").strip()
        joint = element.attrib.get("joint", "").strip()
        if not name or not joint:
            raise MuJoCoConfigurationError(
                "supported actuators require explicit name and joint attributes"
            )
        result[name] = (joint, mode, _ctrl_limit(element))
    return result


class MuJoCoAdapter:
    """Deterministic scalar-joint simulation backend.

    Position and velocity actuator shortcuts are supported directly. More complex
    transmission semantics are intentionally rejected rather than guessed.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        joint_to_actuator: Mapping[str, str] | None = None,
        control_period_s: float | None = None,
    ) -> None:
        self.path = Path(path)
        self.model = mujoco.MjModel.from_xml_path(str(self.path))
        self.data = mujoco.MjData(self.model)
        self._renderer: mujoco.Renderer | None = None
        definitions = _actuators(self.path)
        if not definitions:
            raise MuJoCoConfigurationError("MJCF contains no supported position/velocity actuators")

        mapping = dict(joint_to_actuator or self._infer_mapping(definitions))
        if not mapping:
            raise MuJoCoConfigurationError("no controllable joint mapping was resolved")

        base = load_mjcf(self.path)
        base_by_name = {joint.name: joint for joint in base.joints}
        resolved: list[JointSpec] = []
        self._actuator_ids: dict[str, int] = {}
        for joint_name, actuator_name in mapping.items():
            if joint_name not in base_by_name:
                raise MuJoCoConfigurationError(f"unknown joint in mapping: {joint_name}")
            if actuator_name not in definitions:
                raise MuJoCoConfigurationError(f"unsupported actuator: {actuator_name}")
            target, mode, magnitude = definitions[actuator_name]
            if target != joint_name:
                raise MuJoCoConfigurationError(
                    f"actuator {actuator_name!r} targets {target!r}, not {joint_name!r}"
                )
            actuator_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_name)
            if actuator_id < 0:
                raise MuJoCoConfigurationError(f"compiled actuator missing: {actuator_name}")
            self._actuator_ids[joint_name] = actuator_id
            source = base_by_name[joint_name]
            if mode is ControlMode.VELOCITY:
                resolved.append(replace(source, control_mode=mode, velocity_limit=magnitude))
            else:
                resolved.append(replace(source, control_mode=mode))

        self._embodiment = EmbodimentSpec(
            embodiment_id=base.embodiment_id,
            family="mujoco",
            joints=tuple(resolved),
            sensors=base.sensors,
            metadata={**base.metadata, "backend": "mujoco"},
        )
        self._joint_names = tuple(joint.name for joint in resolved)
        timestep = float(self.model.opt.timestep)
        requested = timestep if control_period_s is None else control_period_s
        if requested <= 0:
            raise MuJoCoConfigurationError("control_period_s must be positive")
        self._physics_steps = max(1, round(requested / timestep))
        actual = self._physics_steps * timestep
        if abs(actual - requested) > timestep * 0.5 + 1e-12:
            raise MuJoCoConfigurationError(
                f"control period {requested} cannot be represented by timestep {timestep}"
            )

    @staticmethod
    def _infer_mapping(
        definitions: Mapping[str, tuple[str, ControlMode, float | None]],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for actuator_name, (joint_name, _, _) in definitions.items():
            if joint_name in mapping:
                raise MuJoCoConfigurationError(
                    f"multiple supported actuators target joint {joint_name!r}; provide a mapping"
                )
            mapping[joint_name] = actuator_name
        return mapping

    @property
    def embodiment(self) -> EmbodimentSpec:
        return self._embodiment

    def reset(self, seed: int) -> Observation:
        """Reset to MJCF defaults. Seed is accepted for backend-contract compatibility."""
        _ = seed
        mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)
        return self._observation()

    def step(self, action: Action) -> Observation:
        expected = set(self._joint_names)
        received = set(action.joint_commands)
        if received != expected:
            missing = sorted(expected - received)
            extra = sorted(received - expected)
            raise ValueError(f"action must command every joint; missing={missing}, extra={extra}")
        mujoco.mj_resetCtrl(self.model, self.data)
        for joint_name, value in action.joint_commands.items():
            self.data.ctrl[self._actuator_ids[joint_name]] = value
        for _ in range(self._physics_steps):
            mujoco.mj_step(self.model, self.data)
        return self._observation()

    def render(
        self, *, width: int = 320, height: int = 240, camera: str | int = -1
    ) -> NDArray[np.uint8]:
        if (
            self._renderer is None
            or self._renderer.width != width
            or self._renderer.height != height
        ):
            if self._renderer is not None:
                self._renderer.close()
            self._renderer = mujoco.Renderer(self.model, height=height, width=width)
        self._renderer.update_scene(self.data, camera=camera)
        image = self._renderer.render()
        return np.asarray(image, dtype=np.uint8)

    def close(self) -> None:
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None

    def body_position(self, name: str) -> tuple[float, float, float]:
        """Return a named body's world-frame position for task evaluation."""
        body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
        if body_id < 0:
            raise ValueError(f"unknown MuJoCo body: {name}")
        position = self.data.xpos[body_id]
        return (float(position[0]), float(position[1]), float(position[2]))

    def _observation(self) -> Observation:
        position: dict[str, float] = {}
        velocity: dict[str, float] = {}
        for name in self._joint_names:
            joint_data = self.data.joint(name)
            if joint_data.qpos.size != 1 or joint_data.qvel.size != 1:
                raise RuntimeError(f"P37 MuJoCo adapter only supports scalar joint {name!r}")
            position[name] = float(joint_data.qpos[0])
            velocity[name] = float(joint_data.qvel[0])
        return Observation(
            timestamp_s=float(self.data.time),
            joint_position=position,
            joint_velocity=velocity,
        )
