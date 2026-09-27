import pytest

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.data.adapters.lerobot import (
    LeRobotAdapterError,
    LeRobotMapping,
    from_frames,
)
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec


def _body() -> EmbodimentSpec:
    joints = tuple(
        JointSpec(
            name=f"j{index}",
            joint_type=JointType.REVOLUTE,
            control_mode=ControlMode.POSITION,
            position=NumericRange(-1.0, 1.0),
        )
        for index in range(2)
    )
    return EmbodimentSpec("arm", "arm", joints)


def test_lerobot_frames_group_into_canonical_episodes() -> None:
    frames = [
        {
            "episode_index": 0,
            "timestamp": 0.0,
            "observation.state": [0.0, 0.1],
            "action": [0.2, 0.3],
            "task": "pick",
        },
        {
            "episode_index": 0,
            "timestamp": 0.1,
            "observation.state": [0.1, 0.2],
            "action": [0.3, 0.4],
            "task": "pick",
        },
        {
            "episode_index": 1,
            "timestamp": 0.0,
            "observation.state": [0.0, 0.0],
            "action": [0.0, 0.0],
            "task": "place",
        },
    ]

    episodes = from_frames(frames, embodiment=_body(), source="test")
    assert len(episodes) == 2
    assert episodes[0].task_id == "pick"
    assert episodes[0].steps[-1].terminal
    assert episodes[1].episode_id == "test:1"


def test_lerobot_mapping_can_use_velocity_and_reward() -> None:
    frames = [
        {
            "episode_index": 2,
            "timestamp": 1.0,
            "observation.state": [0.0, 0.0],
            "observation.velocity": [1.0, 2.0],
            "action": [0.2, 0.2],
            "reward": 3.0,
        }
    ]
    mapping = LeRobotMapping(
        velocity_key="observation.velocity",
        reward_key="reward",
    )
    episode = from_frames(
        frames,
        embodiment=_body(),
        source="test",
        mapping=mapping,
    )[0]
    assert episode.steps[0].observation.joint_velocity["j1"] == 2.0
    assert episode.steps[0].reward == 3.0


def test_lerobot_adapter_rejects_unknown_vector_shape() -> None:
    with pytest.raises(LeRobotAdapterError, match="does not match"):
        from_frames(
            [
                {
                    "episode_index": 0,
                    "timestamp": 0.0,
                    "observation.state": [0.0],
                    "action": [0.0, 0.0],
                }
            ],
            embodiment=_body(),
            source="test",
        )
