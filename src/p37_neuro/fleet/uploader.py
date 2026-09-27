"""Idempotent fleet-event upload pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.request import Request, urlopen

from p37_neuro.fleet.logger import FleetEvent
from p37_neuro.fleet.spool import FleetSpool


class FleetTransport(Protocol):
    def send(self, event: FleetEvent, *, idempotency_key: str) -> None: ...


@dataclass(slots=True)
class HTTPFleetTransport:
    """Small standard-library HTTP transport with runtime-injected credentials."""

    endpoint: str
    bearer_token: str | None = None
    timeout_s: float = 10.0

    def send(self, event: FleetEvent, *, idempotency_key: str) -> None:
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        request = Request(
            self.endpoint,
            data=json.dumps(asdict(event), separators=(",", ":"), sort_keys=True).encode(),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_s) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"fleet upload failed with HTTP {response.status}")


@dataclass(frozen=True, slots=True)
class FlushResult:
    sent: int
    failed: int


class FleetUploader:
    def __init__(self, spool: FleetSpool, transport: FleetTransport) -> None:
        self.spool = spool
        self.transport = transport

    def flush(self, limit: int = 100) -> FlushResult:
        sent = 0
        failed = 0
        for item in self.spool.pending(limit):
            try:
                self.transport.send(item.event, idempotency_key=item.event.event_id)
            except Exception as error:
                self.spool.mark_failed(item.event.event_id, str(error))
                failed += 1
            else:
                self.spool.mark_sent(item.event.event_id)
                sent += 1
        return FlushResult(sent=sent, failed=failed)
