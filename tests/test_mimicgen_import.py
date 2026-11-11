"""Validate the adapter with a deterministic minimal robomimic-style HDF5 fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from p37_neuro.data.mimicgen_import import MimicGenSelection, list_demos, read_mimicgen_episode
from p37_neuro.data.trace_export import TraceProvenance, export_comparison, write_comparison

h5py = pytest.importorskip("h5py")
np = pytest.importorskip("numpy")


@pytest.fixture
def demo_file(tmp_path: Path) -> Path:
    path = tmp_path / "square_d0_panda.hdf5"
    with h5py.File(path, "w") as file:
        group = file.create_group("data/demo_0")
        group.create_dataset(
            "actions",
            data=np.array([[0.1, -0.2, 0.5], [0.3, 0.4, 0.2], [-0.1, 0.2, 0.8]]),
        )
        obs = group.create_group("obs")
        obs.create_dataset(
            "robot0_joint_pos",
            data=np.array([[0.0, 0.2], [0.1, 0.4], [0.3, 0.6]]),
        )
        obs.create_dataset(
            "robot0_joint_vel",
            data=np.array([[0.0, 0.0], [0.1, 0.2], [0.2, 0.3]]),
        )
        obs.create_dataset(
            "robot0_eef_pos",
            data=np.array([[0.35, 0.1, 0.8], [0.36, 0.12, 0.81], [0.39, 0.14, 0.82]]),
        )
    return path


def _selection(path: Path, robot: str = "panda") -> MimicGenSelection:
    return MimicGenSelection(
        path=path,
        demo_id="demo_0",
        embodiment_id=robot,
        task_id="square_d0",
        control_hz=20.0,
    )


def test_list_demos(demo_file: Path) -> None:
    assert list_demos(demo_file) == ["demo_0"]


def test_preserves_original_action_semantics(demo_file: Path) -> None:
    episode = read_mimicgen_episode(_selection(demo_file))
    assert episode.embodiment_id == "panda"
    assert len(episode.steps) == 3
    assert episode.steps[1].observation.timestamp_s == 0.05
    assert episode.steps[0].observation.joint_position["joint_1"] == 0.2
    assert episode.steps[2].observation.state["source_action_2"] == 0.8
    assert episode.steps[2].observation.state["eef_position_2"] == 0.82
    assert episode.steps[2].action.joint_commands == {}
    assert episode.steps[2].terminal
    assert episode.metadata["policy_attached"] == "false"


def test_rejects_missing_source_joint_data(demo_file: Path) -> None:
    with h5py.File(demo_file, "a") as file:
        del file["data/demo_0/obs/robot0_joint_pos"]
    with pytest.raises(ValueError, match="robot0_joint_pos"):
        read_mimicgen_episode(_selection(demo_file))


def test_requires_explicit_source_control_frequency(demo_file: Path) -> None:
    with pytest.raises(ValueError, match="control_hz"):
        _selection(demo_file).__class__(
            path=demo_file,
            demo_id="demo_0",
            embodiment_id="panda",
            task_id="square_d0",
            control_hz=0,
        )


def test_exports_two_distinct_offline_datasets(demo_file: Path, tmp_path: Path) -> None:
    episodes = [
        read_mimicgen_episode(_selection(demo_file, robot)) for robot in ("panda", "sawyer")
    ]
    provenance = TraceProvenance(
        checkpoint_sha256="",
        code_commit="fixture",
        simulator="MimicGen recorded only",
        simulator_version="source metadata not checked",
        robot_description_sha256="not available",
        adapter_version="mimicgen-hdf5-v1",
        seed=0,
        training_membership="unknown",
        evidence_level="T1",
        policy_attached=False,
        evaluation_protocol="offline-data-import",
        outcome="unverified",
    )
    artifact = export_comparison(episodes, [provenance, provenance], title="Offline fixture")
    path = tmp_path / "comparison.json"
    write_comparison(path, artifact)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["traces"][0]["frames"][0]["state"]["source_action_0"] == 0.1
    assert written["traces"][1]["provenance"]["policy_attached"] is False
