"""Small real-physics training environment tests (no pretrained checkpoint needed)."""

import importlib
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("gymnasium")
G1LocomotionEnv = importlib.import_module("p37_neuro_sim.g1_locomotion_env").G1LocomotionEnv

XML = """
<mujoco model="g1_training_fixture">
<option timestep="0.002" gravity="0 0 -9.81"/>
<worldbody>
<geom name="floor" type="plane" size="2 2 .1"/>
<body name="torso" pos="0 0 .8">
<freejoint/>
<geom type="box" size=".1 .08 .15" mass="6"/>
<body name="leg" pos="0 0 -.15">
<joint name="hip" type="hinge" axis="0 1 0" range="-1 1" damping=".2"/>
<geom type="capsule" fromto="0 0 0 0 0 -.35" size=".035" mass="1"/>
</body></body></worldbody>
<actuator>
<motor name="hip_motor" joint="hip" gear="1" ctrllimited="true" ctrlrange="-30 30"/>
</actuator>
<keyframe><key name="stand" qpos="0 0 .8 1 0 0 0 0"/></keyframe>
</mujoco>
"""


def test_real_mujoco_gym_step(tmp_path: Path) -> None:
    path = tmp_path / "mini.xml"
    path.write_text(XML, encoding="utf-8")
    env = G1LocomotionEnv(path, episode_seconds=0.10, fall_height_m=0.05)
    try:
        obs, info = env.reset(seed=42)
        assert obs.shape == env.observation_space.shape
        assert info["seed"] == 42
        assert np.isfinite(obs).all()
        state, reward, terminated, truncated, outcome = env.step(np.zeros(env.action_space.shape))
        assert state.shape == obs.shape and np.isfinite(state).all()
        assert np.isfinite(reward)
        assert isinstance(terminated, bool) and isinstance(truncated, bool)
        assert "base_height_m" in outcome
        with pytest.raises(ValueError, match="invalid locomotion action"):
            env.step(np.array([float("nan")]))
    finally:
        env.close()


def test_bad_control_period(tmp_path: Path) -> None:
    path = tmp_path / "mini.xml"
    path.write_text(XML, encoding="utf-8")
    with pytest.raises(ValueError, match="integer multiple"):
        G1LocomotionEnv(path, control_dt=0.003)
