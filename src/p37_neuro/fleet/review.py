"""Durable human-review queue for ambiguous fleet episodes."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ReviewItem:
    episode_id: str
    reason: str
    priority: int
    status: ReviewStatus = ReviewStatus.PENDING


class ReviewQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue (
                    episode_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10.0)

    def enqueue(self, item: ReviewItem) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO review_queue(episode_id, reason, priority, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(episode_id) DO NOTHING
                """,
                (item.episode_id, item.reason, item.priority, item.status.value),
            )

    def pending(self, limit: int = 100) -> tuple[ReviewItem, ...]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT episode_id, reason, priority, status
                FROM review_queue
                WHERE status='pending'
                ORDER BY priority DESC, rowid
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(ReviewItem(row[0], row[1], row[2], ReviewStatus(row[3])) for row in rows)

    def decide(self, episode_id: str, status: ReviewStatus) -> None:
        if status is ReviewStatus.PENDING:
            raise ValueError("decision must be accepted or rejected")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE review_queue SET status=? WHERE episode_id=?",
                (status.value, episode_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(episode_id)
