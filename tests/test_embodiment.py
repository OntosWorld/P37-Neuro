import pytest

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


def test_embodiment_rejects_duplicate_joint_names() -> None:
    joint = JointSpec(
        name="shoulder",
        joint_type=JointType.REVOLUTE,
        control_mode=ControlMode.POSITION,
        position=NumericRange(-1.0, 1.0),
    )
    with pytest.raises(ValueError, match="unique"):
        EmbodimentSpec(embodiment_id="arm-a", family="arm", joints=(joint, joint))


def test_action_dimension_matches_controllable_joint_count() -> None:
    joints = tuple(
        JointSpec(
            name=f"joint_{index}",
            joint_type=JointType.REVOLUTE,
            control_mode=ControlMode.POSITION,
            position=NumericRange(-3.14, 3.14),
        )
        for index in range(6)
    )
    body = EmbodimentSpec(embodiment_id="arm-6dof", family="arm", joints=joints)
    assert body.action_dimension == 6
