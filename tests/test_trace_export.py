"""Trace export contract tests: evidence must remain measured and attributable."""

from __future__ import annotations

import json

import pytest

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.trace_export import (
    TraceProvenance,
    export_comparison,
    export_episode,
    write_comparison,
)


def provenance(*, checkpoint: str = "checkpoint-abc") -> TraceProvenance:
    return TraceProvenance(
        checkpoint_sha256=checkpoint,
        code_commit="commit-123",
        simulator="MuJoCo",
        simulator_version="3.3",
        robot_description_sha256="robot-123",
        adapter_version="adapter-1",
        seed=42,
        training_membership="held-out",
        evidence_level="T2",
        policy_attached=True,
        evaluation_protocol="docs/testing.md",
        outcome="unverified",
    )


def episode(embodiment: str, episode_id: str = "episode-1") -> Episode:
    return Episode(
        episode_id=episode_id,
        embodiment_id=embodiment,
        task_id="target-reach",
        source="mujoco-recorded",
        steps=[
            EpisodeStep(
                observation=Observation(
                    timestamp_s=0.0,
                    joint_position={"joint_1": 0.1},
                    joint_velocity={"joint_1": 0.0},
                    state={"energy": 2.0},
                ),
                action=Action(timestamp_s=0.02, joint_commands={"joint_1": 0.2}),
                reward=0.0,
            ),
            EpisodeStep(
                observation=Observation(
                    timestamp_s=0.1,
                    joint_position={"joint_1": 0.3},
                    joint_velocity={"joint_1": 0.1},
                ),
                action=Action(timestamp_s=0.12, joint_commands={"joint_1": 0.5}),
                reward=1.0,
                intervention=True,
                terminal=True,
                failure_code="reached-joint-limit",
            ),
        ],
    )


def test_export_preserves_recorded_frames_and_provenance() -> None:
    result = export_episode(episode("arm6"), provenance())
    assert result["schema_version"] == "p37-trace-v1"
    assert result["frames"][1]["t"] == 0.1
    assert result["frames"][1]["intervention"] is True
    assert result["frames"][1]["failure_code"] == "reached-joint-limit"
    assert result["provenance"]["checkpoint_sha256"] == "checkpoint-abc"


def test_comparison_maintains_two_distinct_embodiments(tmp_path: object) -> None:
    first = episode("arm6", "episode-1")
    second = episode("arm7", "episode-2")
    artifact = export_comparison([first, second], [provenance(), provenance()], title="Reach")
    assert len(artifact["traces"]) == 2
    assert artifact["traces"][0]["embodiment_id"] != artifact["traces"][1]["embodiment_id"]
    assert artifact["traces"][0]["provenance"]["checkpoint_sha256"] == "checkpoint-abc"


def test_mismatched_tasks_rejected() -> None:
    first = episode("arm6", "episode-1")
    second = Episode(
        episode_id="episode-2",
        embodiment_id="arm7",
        task_id="different-task",
        source="recorded",
        steps=first.steps,
    )
    with pytest.raises(ValueError, match="same task"):
        export_comparison([first, second], [provenance(), provenance()], title="invalid")


def test_repeated_timestamps_rejected() -> None:
    original = episode("arm6")
    second_step = EpisodeStep(
        observation=Observation(
            timestamp_s=0.0,
            joint_position={"joint_1": 0.2},
            joint_velocity={},
        ),
        action=Action(timestamp_s=0.02, joint_commands={"joint_1": 0.2}),
    )
    invalid = Episode(
        episode_id="bad",
        embodiment_id="arm6",
        task_id="target-reach",
        source="recorded",
        steps=[original.steps[0], second_step],
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        export_episode(invalid, provenance())


def test_policy_requires_checkpoint() -> None:
    with pytest.raises(ValueError, match="checkpoint"):
        provenance(checkpoint="")


def test_json_output_is_strict_and_deterministic(tmp_path: object) -> None:
    from pathlib import Path

    destination = Path(str(tmp_path)) / "experiment.json"
    artifact = export_comparison(
        [episode("arm6", "a"), episode("arm7", "b")],
        [provenance(), provenance()],
        title="Reach",
    )
    write_comparison(destination, artifact)
    loaded = json.loads(destination.read_text(encoding="utf-8"))
    assert loaded == artifact
