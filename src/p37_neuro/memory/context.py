"""Bounded cross-trial memory and task-progress tracking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class ContextWindow(Generic[T]):
    """Bounded memory preserving the most recent physical context."""

    capacity: int
    _items: deque[T] = field(init=False)

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        self._items = deque(maxlen=self.capacity)

    def append(self, item: T) -> None:
        self._items.append(item)

    def snapshot(self) -> tuple[T, ...]:
        return tuple(self._items)

    def clear(self) -> None:
        self._items.clear()


@dataclass(slots=True)
class TaskProgress:
    """Explicit task state for long-horizon policies."""

    stages: tuple[str, ...]
    completed: set[str] = field(default_factory=set)
    failures: list[str] = field(default_factory=list)

    def mark_complete(self, stage: str) -> None:
        if stage not in self.stages:
            raise KeyError(stage)
        self.completed.add(stage)

    def record_failure(self, code: str) -> None:
        if not code.strip():
            raise ValueError("failure code cannot be empty")
        self.failures.append(code)

    @property
    def progress(self) -> float:
        if not self.stages:
            return 1.0
        return len(self.completed) / len(self.stages)
