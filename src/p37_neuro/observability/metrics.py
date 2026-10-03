"""Dependency-light runtime observability contracts for P37."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeMetricSnapshot:
    robot_id: str
    artifact_id: str
    timestamp_s: float
    control_loop_hz: float
    inference_p50_ms: float
    inference_p95_ms: float
    inference_p99_ms: float
    observation_age_p95_ms: float
    rejected_commands: int
    watchdog_events: int
    interventions: int
    runtime_restarts: int
    gpu_memory_mb: float | None = None

    def __post_init__(self) -> None:
        if not self.robot_id.strip() or not self.artifact_id.strip():
            raise ValueError("robot_id and artifact_id are required")
        if self.timestamp_s < 0 or self.control_loop_hz < 0:
            raise ValueError("timestamp and control_loop_hz must be non-negative")
        for value in (
            self.inference_p50_ms,
            self.inference_p95_ms,
            self.inference_p99_ms,
            self.observation_age_p95_ms,
        ):
            if value < 0:
                raise ValueError("latency metrics must be non-negative")
        for value in (
            self.rejected_commands,
            self.watchdog_events,
            self.interventions,
            self.runtime_restarts,
        ):
            if value < 0:
                raise ValueError("runtime counters must be non-negative")


class RuntimeMetrics:
    """Bounded in-process metrics collector for the non-real-time telemetry path."""

    def __init__(self, *, max_samples: int = 2048) -> None:
        if max_samples <= 0:
            raise ValueError("max_samples must be positive")
        self.max_samples = max_samples
        self._inference_ms: list[float] = []
        self._observation_age_ms: list[float] = []
        self.rejected_commands = 0
        self.watchdog_events = 0
        self.interventions = 0
        self.runtime_restarts = 0

    def _append(self, values: list[float], value: float) -> None:
        if value < 0:
            raise ValueError("metric samples must be non-negative")
        values.append(float(value))
        if len(values) > self.max_samples:
            del values[: len(values) - self.max_samples]

    def observe_inference_ms(self, value: float) -> None:
        self._append(self._inference_ms, value)

    def observe_observation_age_ms(self, value: float) -> None:
        self._append(self._observation_age_ms, value)

    def increment_rejected_commands(self) -> None:
        self.rejected_commands += 1

    def increment_watchdog_events(self) -> None:
        self.watchdog_events += 1

    def increment_interventions(self) -> None:
        self.interventions += 1

    def increment_runtime_restarts(self) -> None:
        self.runtime_restarts += 1

    def snapshot(
        self,
        *,
        robot_id: str,
        artifact_id: str,
        timestamp_s: float,
        control_loop_hz: float,
        gpu_memory_mb: float | None = None,
    ) -> RuntimeMetricSnapshot:
        return RuntimeMetricSnapshot(
            robot_id=robot_id,
            artifact_id=artifact_id,
            timestamp_s=timestamp_s,
            control_loop_hz=control_loop_hz,
            inference_p50_ms=_percentile(self._inference_ms, 0.50),
            inference_p95_ms=_percentile(self._inference_ms, 0.95),
            inference_p99_ms=_percentile(self._inference_ms, 0.99),
            observation_age_p95_ms=_percentile(self._observation_age_ms, 0.95),
            rejected_commands=self.rejected_commands,
            watchdog_events=self.watchdog_events,
            interventions=self.interventions,
            runtime_restarts=self.runtime_restarts,
            gpu_memory_mb=gpu_memory_mb,
        )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def prometheus_text(snapshot: RuntimeMetricSnapshot) -> str:
    """Render a snapshot using Prometheus exposition format without runtime dependencies."""
    labels = f'robot_id="{snapshot.robot_id}",artifact_id="{snapshot.artifact_id}"'
    fields = {
        "p37_control_loop_hz": snapshot.control_loop_hz,
        "p37_inference_p50_ms": snapshot.inference_p50_ms,
        "p37_inference_p95_ms": snapshot.inference_p95_ms,
        "p37_inference_p99_ms": snapshot.inference_p99_ms,
        "p37_observation_age_p95_ms": snapshot.observation_age_p95_ms,
        "p37_rejected_commands_total": snapshot.rejected_commands,
        "p37_watchdog_events_total": snapshot.watchdog_events,
        "p37_interventions_total": snapshot.interventions,
        "p37_runtime_restarts_total": snapshot.runtime_restarts,
    }
    if snapshot.gpu_memory_mb is not None:
        fields["p37_gpu_memory_mb"] = snapshot.gpu_memory_mb
    return "\n".join(f"{name}{{{labels}}} {value}" for name, value in fields.items()) + "\n"


class JsonlMetricExporter:
    """Append-only exporter suitable for agents or log collectors."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, snapshot: RuntimeMetricSnapshot) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(snapshot), sort_keys=True) + "\n")
