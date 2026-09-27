"""Deterministic episode replay utilities."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from p37_neuro.data.schema import Episode, EpisodeStep


@dataclass(slots=True)
class EpisodeReplay:
    """Read-only deterministic cursor over a recorded episode."""

    episode: Episode
    _index: int = 0

    def reset(self) -> None:
        self._index = 0

    def __iter__(self) -> Iterator[EpisodeStep]:
        self.reset()
        while self._index < len(self.episode.steps):
            step = self.episode.steps[self._index]
            self._index += 1
            yield step
