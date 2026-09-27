"""LeRobot v3 dataset adapter into canonical P37 episodes."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec


class LeRobotAdapterError(ValueError):
    """Raised when a LeRobot frame cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class LeRobotMapping:
    """Explicit feature mapping for one LeRobot dataset family."""

    episode_index_key: str = "episode_index"
    timestamp_key: str = "timestamp"
    position_key: str = "observation.state"
    velocity_key: str | None = None
    action_key: str = "action"
    task_key: str = "task"
    reward_key: str | None = None
    terminal_key: str | None = None


def _vector(value: Any, *, label: str) -> tuple[float, ...]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise LeRobotAdapterError(f"{label} must be a vector")
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise LeRobotAdapterError(f"{label} contains non-numeric values") from exc


def _joint_map(
    values: tuple[float, ...],
    embodiment: EmbodimentSpec,
    *,
    label: str,
) -> dict[str, float]:
    if len(values) != len(embodiment.joints):
        raise LeRobotAdapterError(
            f"{label} length {len(values)} does not match "
            f"{len(embodiment.joints)} controllable joints"
        )
    return {
        joint.name: values[index]
        for index, joint in enumerate(embodiment.joints)
    }


def from_frames(
    frames: Iterable[Mapping[str, Any]],
    *,
    embodiment: EmbodimentSpec,
    source: str,
    mapping: LeRobotMapping | None = None,
) -> tuple[Episode, ...]:
    """Normalize LeRobot frame dictionaries into P37 episodes.

    Frames may come from LeRobotDataset, StreamingLeRobotDataset or an already
    decoded cache. The mapping is explicit because public datasets differ in
    how robot state vectors are constructed.
    """
    resolved_mapping = mapping or LeRobotMapping()
    grouped: OrderedDict[int, list[Mapping[str, Any]]] = OrderedDict()
    for frame_index, frame in enumerate(frames):
        try:
            episode_index = int(frame[resolved_mapping.episode_index_key])
        except (KeyError, TypeError, ValueError) as exc:
            raise LeRobotAdapterError(
                f"frame {frame_index} has no valid episode index"
            ) from exc
        grouped.setdefault(episode_index, []).append(frame)

    episodes: list[Episode] = []
    for episode_index, rows in grouped.items():
        steps: list[EpisodeStep] = []
        task_id = "unknown"

        for step_index, row in enumerate(rows):
            try:
                timestamp = float(row[resolved_mapping.timestamp_key])
                positions = _joint_map(
                    _vector(
                        row[resolved_mapping.position_key],
                        label=resolved_mapping.position_key,
                    ),
                    embodiment,
                    label="position",
                )
                actions = _joint_map(
                    _vector(
                        row[resolved_mapping.action_key],
                        label=resolved_mapping.action_key,
                    ),
                    embodiment,
                    label="action",
                )
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, LeRobotAdapterError):
                    raise
                raise LeRobotAdapterError(
                    f"invalid frame {step_index} in episode {episode_index}"
                ) from exc

            velocities: dict[str, float] = {}
            if (
                resolved_mapping.velocity_key is not None
                and resolved_mapping.velocity_key in row
            ):
                velocities = _joint_map(
                    _vector(
                        row[resolved_mapping.velocity_key],
                        label=resolved_mapping.velocity_key,
                    ),
                    embodiment,
                    label="velocity",
                )

            if (
                resolved_mapping.task_key in row
                and str(row[resolved_mapping.task_key]).strip()
            ):
                task_id = str(row[resolved_mapping.task_key]).strip()

            reward = None
            if (
                resolved_mapping.reward_key is not None
                and resolved_mapping.reward_key in row
            ):
                reward = float(row[resolved_mapping.reward_key])

            terminal = step_index == len(rows) - 1
            if (
                resolved_mapping.terminal_key is not None
                and resolved_mapping.terminal_key in row
            ):
                terminal = bool(row[resolved_mapping.terminal_key])

            steps.append(
                EpisodeStep(
                    observation=Observation(
                        timestamp_s=timestamp,
                        joint_position=positions,
                        joint_velocity=velocities,
                    ),
                    action=Action(
                        timestamp_s=timestamp,
                        joint_commands=actions,
                    ),
                    reward=reward,
                    terminal=terminal,
                )
            )

        if not steps:
            continue
        episodes.append(
            Episode(
                episode_id=f"{source}:{episode_index}",
                embodiment_id=embodiment.embodiment_id,
                task_id=task_id,
                steps=tuple(steps),
                source=source,
                metadata={
                    "adapter": "lerobot-v3",
                    "episode_index": str(episode_index),
                },
            )
        )
    return tuple(episodes)


def load_dataset(
    repo_id: str,
    *,
    embodiment: EmbodimentSpec,
    episodes: list[int] | None = None,
    root: str | Path | None = None,
    revision: str | None = None,
    mapping: LeRobotMapping | None = None,
) -> tuple[Episode, ...]:
    """Load a LeRobot dataset lazily and normalize selected episodes."""
    try:
        from lerobot.datasets import LeRobotDataset
    except ImportError as exc:
        raise RuntimeError(
            "LeRobot support is optional; install p37-neuro[data]"
        ) from exc

    dataset = LeRobotDataset(
        repo_id,
        root=root,
        episodes=episodes,
        revision=revision,
        download_videos=False,
    )
    return from_frames(
        (dataset[index] for index in range(len(dataset))),
        embodiment=embodiment,
        source=f"lerobot:{repo_id}",
        mapping=mapping,
    )
