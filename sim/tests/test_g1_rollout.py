from pathlib import Path
import mujoco
import numpy as np
import pytest
from p37_neuro_sim.g1_rollout import Trial, clamp, direct_motor_mapping, run

XML = """<mujoco><option timestep="0.002"/><worldbody>
<geom type="plane" size="1 1 .1"/>
<body name="base" pos="0 0 .7"><freejoint/><geom type="sphere" size=".1" mass="5"/>
<body name="link" pos="0 0 .15"><joint name="hinge" type="hinge" axis="0 1 0" range="-1 1"/>
<geom type="capsule" size=".04 .1" mass="1"/></body></body></worldbody>
<actuator><motor joint="hinge" ctrlrange="-20 20" ctrllimited="true"/></actuator></mujoco>"""

def test_validation():
    Trial().validate()
    with pytest.raises(ValueError):
        Trial(seconds=1, push_start=2).validate()

def test_real_physics_rollout(tmp_path: Path):
    path = tmp_path / "scene.xml"
    path.write_text(XML)
    model = mujoco.MjModel.from_xml_path(str(path))
    assert len(direct_motor_mapping(model)) == 1
    bounded, rejected = clamp(model, np.array([100.0]))
    assert rejected == 1 and bounded.tolist() == [20.0]
    with pytest.raises(ValueError):
        clamp(model, np.array([float("nan")]))
    out = tmp_path / "out"
    result = run(path, out, Trial(seconds=0.1, push_start=0.02, push_duration=0.02,
                                 push_newtons=1, fall_drop_m=1))
    assert result["level"] == "simulation_only"
    assert result["controller"] == "PD_hold_not_locomotion"
    for name in ("timeseries.csv", "trajectory.json", "summary.json"):
        assert (out / name).is_file()
