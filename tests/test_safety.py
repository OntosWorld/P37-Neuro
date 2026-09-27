import pytest

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.data.schema import Action
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec
from p37_neuro.runtime.safety import JointSafetyEnvelope, UnsafeCommandError


def _body(mode: ControlMode) -> EmbodimentSpec:
    return EmbodimentSpec(
        embodiment_id="test-body",
        family="test",
        joints=(
            JointSpec(
                name="joint_1",
                joint_type=JointType.REVOLUTE,
                control_mode=mode,
                position=NumericRange(-1.0, 1.0) if mode is ControlMode.POSITION else None,
                velocity_limit=2.0 if mode is ControlMode.VELOCITY else None,
                effort_limit=4.0 if mode is ControlMode.EFFORT else None,
            ),
        ),
    )


def test_position_command_is_clamped_and_reported() -> None:
    result = JointSafetyEnvelope().apply(
        Action(timestamp_s=1.0, joint_commands={"joint_1": 3.0}),
        _body(ControlMode.POSITION),
    )
    assert result.action.joint_commands["joint_1"] == 1.0
    assert result.clamped_joints == ("joint_1",)


def test_velocity_command_over_limit_fails_closed() -> None:
    with pytest.raises(UnsafeCommandError, match="exceeds"):
        JointSafetyEnvelope().apply(
            Action(timestamp_s=1.0, joint_commands={"joint_1": 2.1}),
            _body(ControlMode.VELOCITY),
        )


def test_unknown_joint_is_rejected() -> None:
    with pytest.raises(UnsafeCommandError, match="unknown joints"):
        JointSafetyEnvelope().apply(
            Action(timestamp_s=1.0, joint_commands={"ghost": 0.0}),
            _body(ControlMode.POSITION),
        )
