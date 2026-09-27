"""Durable fleet-event spool for unreliable robot connectivity."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from p37_neuro.fleet.logger import FleetEvent


@dataclass(frozen=True, slots=True)
class SpoolItem:
    event: FleetEvent
    attempts: int
    last_error: str | None


class FleetSpool:
    """SQLite-backed at-least-once delivery spool with event-id idempotency."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS fleet_spool (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending', 'sent')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @staticmethod
    def _payload(event: FleetEvent) -> str:
        return json.dumps(asdict(event), separators=(",", ":"), sort_keys=True)

    def enqueue(self, event: FleetEvent) -> None:
        payload = self._payload(event)
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT payload FROM fleet_spool WHERE event_id = ?", (event.event_id,)
            ).fetchone()
            if row is not None:
                if row[0] != payload:
                    raise ValueError(f"event_id collision with different payload: {event.event_id}")
                return
            connection.execute(
                "INSERT INTO fleet_spool(event_id, payload, status) VALUES (?, ?, 'pending')",
                (event.event_id, payload),
            )

    def pending(self, limit: int = 100) -> tuple[SpoolItem, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT payload, attempts, last_error
                FROM fleet_spool
                WHERE status = 'pending'
                ORDER BY rowid
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            SpoolItem(FleetEvent(**json.loads(payload)), attempts, last_error)
            for payload, attempts, last_error in rows
        )

    def mark_sent(self, event_id: str) -> None:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE fleet_spool SET status='sent', last_error=NULL WHERE event_id=?",
                (event_id,),
            )
            if cursor.rowcount != 1:
                raise KeyError(event_id)

    def mark_failed(self, event_id: str, error: str) -> None:
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE fleet_spool
                SET attempts=attempts+1, last_error=?
                WHERE event_id=? AND status='pending'
                """,
                (error[:1000], event_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(event_id)
