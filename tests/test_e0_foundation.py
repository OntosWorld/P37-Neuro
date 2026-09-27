from pathlib import Path

import pytest

from p37_neuro.config import ConfigurationError, load_config
from p37_neuro.data.replay import EpisodeReplay
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.storage import read_episode, write_episode
from p37_neuro.embodiment.importers import load_mjcf, load_urdf
from p37_neuro.registry import ArtifactRecord, ArtifactRegistry


def test_load_config_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "schema_version: 1\nproject: demo\nseed: 7\nembodiment: arm\nmode: train\n",
        encoding="utf-8",
    )
    assert load_config(path).seed == 7


def test_invalid_config_mode_fails(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        '{"schema_version":1,"project":"x","seed":1,"embodiment":"r","mode":"oops"}',
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError):
        load_config(path)


def test_urdf_importer(tmp_path: Path) -> None:
    path = tmp_path / "arm.urdf"
    path.write_text(
        '<robot name="arm"><joint name="j1" type="revolute">'
        '<limit lower="-1" upper="1" velocity="2" effort="3"/>'
        "</joint></robot>",
        encoding="utf-8",
    )
    body = load_urdf(path)
    assert body.embodiment_id == "arm"
    assert body.joints[0].velocity_limit == 2.0


def test_mjcf_importer(tmp_path: Path) -> None:
    path = tmp_path / "arm.xml"
    path.write_text(
        '<mujoco model="arm"><worldbody><body><joint name="j1" type="hinge" range="-1 1"/>'
        "</body></worldbody></mujoco>",
        encoding="utf-8",
    )
    assert load_mjcf(path).action_dimension == 1


def _episode() -> Episode:
    observation = Observation(
        timestamp_s=0.0,
        joint_position={"j1": 0.0},
        joint_velocity={"j1": 0.0},
    )
    action = Action(timestamp_s=0.0, joint_commands={"j1": 0.1})
    return Episode(
        episode_id="e1",
        embodiment_id="arm",
        task_id="reach",
        steps=(EpisodeStep(observation=observation, action=action, reward=1.0),),
        source="test",
    )


def test_episode_round_trip_and_replay(tmp_path: Path) -> None:
    path = tmp_path / "episode.jsonl"
    write_episode(path, _episode())
    loaded = read_episode(path)
    assert loaded.episode_id == "e1"
    assert next(iter(EpisodeReplay(loaded))).reward == 1.0


def test_artifact_registry_is_append_only(tmp_path: Path) -> None:
    registry = ArtifactRegistry(tmp_path)
    record = ArtifactRecord("m1", "E1", "m.pt", "abc", "cfg", "ds", {"score": 0.5})
    registry.register(record)
    assert registry.list()[0].artifact_id == "m1"
    with pytest.raises(ValueError):
        registry.register(record)


def test_urdf_continuous_joint_uses_velocity_control(tmp_path: Path) -> None:
    path = tmp_path / "wheel.urdf"
    path.write_text(
        '<robot name="wheel"><joint name="spin" type="continuous">'
        '<limit velocity="4" effort="5"/>'
        "</joint></robot>",
        encoding="utf-8",
    )
    body = load_urdf(path)
    assert body.joints[0].control_mode.value == "velocity"
    assert body.joints[0].position is None
