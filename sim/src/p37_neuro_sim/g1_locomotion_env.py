"""Gymnasium-compatible G1 locomotion environment backed by real MuJoCo physics.

Requires optional sim training dependencies: gymnasium and stable-baselines3.
The policy learns residual joint targets over the standing pose; it must be
trained and evaluated before anyone describes it as walking.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import mujoco
import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:
    raise ImportError("Install the sim training extra: uv sync --extra train") from exc


class G1LocomotionEnv(gym.Env):
    metadata: ClassVar[dict[str, list[str]]] = {"render_modes": []}

    def __init__(
        self,
        model_path: str | Path,
        *,
        episode_seconds: float = 10.0,
        control_dt: float = 0.02,
        command_velocity_m_s: float = 0.3,
        action_scale_rad: float = 0.35,
        stiffness: float = 45.0,
        damping: float = 2.0,
        fall_height_m: float = 0.45,
        reset_noise_rad: float = 0.02,
        push_newtons: float = 0.0,
        push_start_s: float = 2.0,
        push_end_s: float = 2.15,
    ) -> None:
        super().__init__()
        self.model_path = Path(model_path).resolve()
        self.model = mujoco.MjModel.from_xml_path(str(self.model_path))
        self.data = mujoco.MjData(self.model)
        self.episode_seconds = episode_seconds
        self.command_velocity_m_s = command_velocity_m_s
        self.action_scale_rad = action_scale_rad
        self.stiffness = stiffness
        self.damping = damping
        self.fall_height_m = fall_height_m
        self.reset_noise_rad = reset_noise_rad
        self.push_newtons = push_newtons
        self.push_start_s = push_start_s
        self.push_end_s = push_end_s
        if min(episode_seconds, control_dt, action_scale_rad, stiffness, fall_height_m) <= 0:
            raise ValueError("positive simulation parameters required")
        if min(damping, reset_noise_rad, push_newtons) < 0:
            raise ValueError("damping, noise and force cannot be negative")
        if not 0 <= push_start_s < push_end_s <= episode_seconds:
            raise ValueError("invalid push timing")
        steps = round(control_dt / self.model.opt.timestep)
        if steps < 1 or abs(steps * self.model.opt.timestep - control_dt) > 1e-9:
            raise ValueError("control_dt must be an integer multiple of MuJoCo timestep")
        self._substeps = steps
        self._control_dt = control_dt
        self._actuators = []
        self._position_servo = []
        self._gears = []
        for index in range(self.model.nu):
            if self.model.actuator_trntype[index] != mujoco.mjtTrn.mjTRN_JOINT:
                raise ValueError("only direct joint-transmission motors supported")
            joint_id = int(self.model.actuator_trnid[index, 0])
            if self.model.jnt_type[joint_id] != mujoco.mjtJoint.mjJNT_HINGE:
                raise ValueError("only hinge motor actuators supported")
            if self.model.actuator_dyntype[index] != mujoco.mjtDyn.mjDYN_NONE:
                raise ValueError("dynamic actuators not supported")
            gear = float(self.model.actuator_gear[index, 0])
            gain = float(self.model.actuator_gainprm[index, 0])
            bias_position = float(self.model.actuator_biasprm[index, 1])
            bias_velocity = float(self.model.actuator_biasprm[index, 2])
            if abs(gear * gain) < 1e-8:
                raise ValueError("zero actuator transmission gain")
            is_servo = abs(bias_position) > 1e-8
            if is_servo and abs(bias_position + gain) > 1e-6 * max(1.0, abs(gain)):
                raise ValueError("unsupported affine position actuator")
            if not is_servo and abs(bias_velocity) > 1e-8:
                raise ValueError("unsupported velocity servo")
            self._position_servo.append(is_servo)
            self._gears.append(gear)
            self._actuators.append(
                (
                    int(self.model.jnt_qposadr[joint_id]),
                    int(self.model.jnt_dofadr[joint_id]),
                    gear * gain,
                )
            )
        if not self._actuators:
            raise ValueError("robot has no supported motor actuators")
        self._base_joints = [
            j
            for j in range(self.model.njnt)
            if self.model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE
        ]
        if len(self._base_joints) != 1:
            raise ValueError("expected exactly one free-floating root joint")
        root = self._base_joints[0]
        self._base_q = int(self.model.jnt_qposadr[root])
        self._base_v = int(self.model.jnt_dofadr[root])
        self._root_body = int(self.model.jnt_bodyid[root])
        self._joint_q = np.array([x[0] for x in self._actuators])
        self._joint_v = np.array([x[1] for x in self._actuators])
        self._gains = np.array([x[2] for x in self._actuators])
        self._gears = np.asarray(self._gears, dtype=np.float64)
        self._position_servo = np.asarray(self._position_servo, dtype=bool)
        self._reference = np.zeros(self.model.nq)
        key = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_KEY, "stand")
        self._key = key if key >= 0 else (0 if self.model.nkey else -1)
        self._reset_model()
        self._reference[:] = self.data.qpos
        self._initial_height = float(self.data.xpos[self._root_body, 2])
        n = len(self._actuators)
        # joint error, joint velocity, base linear velocity, angular velocity,
        # gravity projection, and forward command
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(2 * n + 10,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(n,), dtype=np.float32)
        self._elapsed = 0.0

    def _reset_model(self) -> None:
        if self._key >= 0:
            mujoco.mj_resetDataKeyframe(self.model, self.data, self._key)
        else:
            mujoco.mj_resetData(self.model, self.data)
        mujoco.mj_forward(self.model, self.data)

    def _observe(self) -> np.ndarray:
        orientation = self.data.qpos[self._base_q + 3 : self._base_q + 7]
        rotation = np.empty(9, dtype=np.float64)
        mujoco.mju_quat2Mat(rotation, orientation)
        # World Z axis in local coordinates.
        gravity_local = rotation.reshape(3, 3).T @ np.array([0.0, 0.0, -1.0])
        return np.concatenate(
            (
                self.data.qpos[self._joint_q] - self._reference[self._joint_q],
                self.data.qvel[self._joint_v],
                self.data.qvel[self._base_v : self._base_v + 3],
                self.data.qvel[self._base_v + 3 : self._base_v + 6],
                gravity_local,
                [self.command_velocity_m_s],
            )
        ).astype(np.float32)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._reset_model()
        noise = self.np_random.uniform(
            -self.reset_noise_rad, self.reset_noise_rad, len(self._joint_q)
        )
        self.data.qpos[self._joint_q] += noise
        self.data.xfrc_applied[:] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self._elapsed = 0.0
        return self._observe(), {"seed": seed, "initial_height_m": self._initial_height}

    def step(self, action: np.ndarray):
        action = np.asarray(action, dtype=np.float64)
        if action.shape != self.action_space.shape or not np.all(np.isfinite(action)):
            raise ValueError("invalid locomotion action")
        action = np.clip(action, -1.0, 1.0)
        target = self._reference[self._joint_q] + self.action_scale_rad * action
        control = (
            self.stiffness * (target - self.data.qpos[self._joint_q])
            - self.damping * self.data.qvel[self._joint_v]
        ) / self._gains
        # MuJoCo position actuators expect the desired transmission length,
        # whereas motor actuators expect force-like controls.
        control[self._position_servo] = (
            target[self._position_servo] * self._gears[self._position_servo]
        )
        for index in range(self.model.nu):
            if self.model.actuator_ctrllimited[index]:
                lo, hi = self.model.actuator_ctrlrange[index]
                control[index] = np.clip(control[index], lo, hi)
        self.data.ctrl[:] = control
        for _ in range(self._substeps):
            self.data.xfrc_applied[self._root_body] = 0.0
            if self.push_start_s <= self.data.time < self.push_end_s:
                self.data.xfrc_applied[self._root_body, 0] = self.push_newtons
            mujoco.mj_step(self.model, self.data)
        self._elapsed += self._control_dt
        height = float(self.data.xpos[self._root_body, 2])
        forward_velocity = float(self.data.qvel[self._base_v])
        fallen = height < self.fall_height_m or not np.isfinite(self.data.qpos).all()
        # Dense training reward. This is a proposed curriculum, not a benchmark score.
        velocity_reward = float(np.exp(-4 * (forward_velocity - self.command_velocity_m_s) ** 2))
        upright_reward = float(np.clip(-self._observe()[-2], -1.0, 1.0))
        effort_penalty = float(np.mean(np.square(control))) * 1e-5
        reward = 1.5 * velocity_reward + 0.5 * upright_reward - effort_penalty
        if fallen:
            reward -= 5.0
        terminated = bool(fallen)
        truncated = bool(self._elapsed >= self.episode_seconds)
        info = {
            "base_height_m": height,
            "forward_velocity_m_s": forward_velocity,
            "fallen": bool(fallen),
            "elapsed_s": self._elapsed,
            "push_newtons": self.push_newtons,
        }
        return self._observe(), float(reward), terminated, truncated, info

    def close(self):
        pass
