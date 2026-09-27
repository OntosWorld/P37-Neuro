"""Small RLDS-compatible record normalizer without a TensorFlow dependency."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation


class RLDSAdapterError(ValueError):
    pass


def from_records(
    *,
    episode_id: str,
    embodiment_id: str,
    task_id: str,
    source: str,
    records: list[Mapping[str, Any]],
) -> Episode:
    """Normalize decoded RLDS-like step records into a P37 Episode."""
    steps: list[EpisodeStep] = []
    for index, record in enumerate(records):
        try:
            observation_raw = record["observation"]
            action_raw = record["action"]
            timestamp = float(record.get("timestamp_s", index))
        except (KeyError, TypeError, ValueError) as exc:
            raise RLDSAdapterError(f"invalid record at index {index}") from exc
        if not isinstance(observation_raw, Mapping) or not isinstance(action_raw, Mapping):
            raise RLDSAdapterError(f"record {index} observation/action must be mappings")
        steps.append(
            EpisodeStep(
                observation=Observation(
                    timestamp_s=timestamp,
                    joint_position=dict(observation_raw.get("joint_position", {})),
                    joint_velocity=dict(observation_raw.get("joint_velocity", {})),
                    sensor_refs=dict(observation_raw.get("sensor_refs", {})),
                ),
                action=Action(timestamp_s=timestamp, joint_commands=dict(action_raw)),
                reward=float(record["reward"]) if "reward" in record else None,
                terminal=bool(record.get("is_terminal", False)),
                intervention=bool(record.get("intervention", False)),
            )
        )
    return Episode(
        episode_id=episode_id,
        embodiment_id=embodiment_id,
        task_id=task_id,
        steps=tuple(steps),
        source=source,
    )
