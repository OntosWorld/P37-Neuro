from pathlib import Path

import pytest
from p37_neuro.data.schema import Action

from p37_neuro_sim.mujoco_adapter import MuJoCoAdapter, MuJoCoConfigurationError

XML = """
<mujoco model="one_joint">
  <compiler angle="radian"/>
  <option timestep="0.002"/>
  <worldbody>
    <body name="link" pos="0 0 0">
      <joint name="j1" type="hinge" range="-1 1" damping="0.1"/>
      <geom type="capsule" size="0.03 0.2" pos="0 0 0.2" mass="1"/>
    </body>
  </worldbody>
  <actuator>
    <position name="j1_position" joint="j1" kp="20" ctrlrange="-1 1" ctrllimited="true"/>
  </actuator>
</mujoco>
"""


def _model(tmp_path: Path) -> Path:
    path = tmp_path / "model.xml"
    path.write_text(XML, encoding="utf-8")
    return path


def test_reset_and_step(tmp_path: Path) -> None:
    adapter = MuJoCoAdapter(_model(tmp_path), control_period_s=0.01)
    initial = adapter.reset(seed=1)
    assert set(initial.joint_position) == {"j1"}
    after = adapter.step(Action(initial.timestamp_s, {"j1": 0.5}))
    assert after.timestamp_s > initial.timestamp_s
    assert -1.0 <= after.joint_position["j1"] <= 1.0
    adapter.close()


def test_partial_action_is_rejected(tmp_path: Path) -> None:
    adapter = MuJoCoAdapter(_model(tmp_path))
    with pytest.raises(ValueError, match="command every joint"):
        adapter.step(Action(0.0, {}))


def test_bad_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(MuJoCoConfigurationError, match="unsupported actuator"):
        MuJoCoAdapter(_model(tmp_path), joint_to_actuator={"j1": "missing"})
