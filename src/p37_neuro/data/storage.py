"""Portable JSONL episode serialization with checksums."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation


def _canonical_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def episode_to_dict(episode: Episode) -> dict[str, Any]:
    """Convert an episode into a JSON-safe canonical representation."""
    return asdict(episode)


def episode_digest(episode: Episode) -> str:
    """Return a stable sha256 digest for episode content."""
    payload = _canonical_json(episode_to_dict(episode)).encode()
    return hashlib.sha256(payload).hexdigest()


def write_episode(path: str | Path, episode: Episode) -> str:
    """Write one checksummed episode to disk atomically."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = episode_to_dict(episode)
    record["sha256"] = episode_digest(episode)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(_canonical_json(record) + "
", encoding="utf-8")
    temporary.replace(destination)
    return str(record["sha256"])


def read_episode(path: str | Path) -> Episode:
    """Read and verify a checksummed episode."""
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    expected = str(raw.pop("sha256"))
    steps = []
    for step in raw["steps"]:
        observation = Observation(**step["observation"])
        action = Action(**step["action"])
        steps.append(
            EpisodeStep(
                observation=observation,
                action=action,
                reward=step.get("reward"),
                terminal=step.get("terminal", False),
                failure_code=step.get("failure_code"),
                intervention=step.get("intervention", False),
            )
        )
    episode = Episode(
        episode_id=raw["episode_id"],
        embodiment_id=raw["embodiment_id"],
        task_id=raw["task_id"],
        steps=tuple(steps),
        source=raw["source"],
        metadata=raw.get("metadata", {}),
    )
    if episode_digest(episode) != expected:
        raise ValueError("episode checksum mismatch")
    return episode
