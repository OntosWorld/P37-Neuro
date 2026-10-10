"""Simulation preflight for a validated P37 robot integration."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from p37_neuro.data.schema import Action
from p37_neuro.integration.manifest import (
    RobotDescriptionFormat,
    load_robot_manifest,
    resolve_description,
)


class SimulationPreflightError(RuntimeError):
    """Raised when the requested integration cannot run in the selected backend."""


@dataclass(frozen=True, slots=True)
class SimulationPreflightResult:
    robot_id: str
    backend: str
    steps: int
    action_dimension: int
    final_time_s: float


@dataclass(frozen=True, slots=True)
class ReachBenchmarkResult:
    """Metrics and evidence emitted by a closed-loop MuJoCo reach run."""

    robot_id: str
    seed: int
    steps: int
    success: bool
    initial_distance_m: float
    final_distance_m: float
    minimum_distance_m: float
    success_threshold_m: float
    safety_clamp_count: int
    replay_max_joint_error: float
    episode_path: str
    metrics_path: str


def run_mujoco_preflight(
    manifest_path: str | Path,
    *,
    steps: int = 10,
    seed: int = 0,
) -> SimulationPreflightResult:
    if steps <= 0:
        raise ValueError("steps must be positive")

    manifest = load_robot_manifest(manifest_path)
    if manifest.description.format is not RobotDescriptionFormat.MJCF:
        raise SimulationPreflightError(
            "MuJoCo preflight requires an MJCF robot manifest; "
            "use an MJCF integration or the Isaac Lab integration path"
        )

    try:
        module: Any = import_module("p37_neuro_sim")
    except ModuleNotFoundError as exc:
        raise SimulationPreflightError(
            "MuJoCo preflight requires the p37-neuro-sim package; "
            "run from the sim/ environment or install the simulation package"
        ) from exc

    description = resolve_description(manifest, manifest_path=manifest_path)
    adapter = module.MuJoCoAdapter(
        description,
        control_period_s=1.0 / manifest.runtime.control_frequency_hz,
    )
    try:
        observation = adapter.reset(seed)
        for _ in range(steps):
            commands = {joint.name: 0.0 for joint in adapter.embodiment.joints}
            observation = adapter.step(Action(observation.timestamp_s, commands))
        return SimulationPreflightResult(
            robot_id=manifest.robot_id,
            backend="mujoco",
            steps=steps,
            action_dimension=adapter.embodiment.action_dimension,
            final_time_s=observation.timestamp_s,
        )
    finally:
        adapter.close()


def run_mujoco_reach_benchmark(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    steps: int = 200,
    seed: int = 0,
    target_x: float = 0.22,
    target_y: float = 0.22,
    success_threshold_m: float = 0.025,
) -> ReachBenchmarkResult:
    """Run the simulator package's closed-loop reach benchmark."""
    if steps <= 0:
        raise ValueError("steps must be positive")
    if success_threshold_m <= 0:
        raise ValueError("success_threshold_m must be positive")
    try:
        module: Any = import_module("p37_neuro_sim")
    except ModuleNotFoundError as exc:
        raise SimulationPreflightError(
            "MuJoCo reach benchmark requires the p37-neuro-sim package; "
            "run from the sim/ environment or install the simulation package"
        ) from exc
    result: ReachBenchmarkResult = module.run_reach_benchmark(
        manifest_path,
        output_dir=output_dir,
        steps=steps,
        seed=seed,
        target=(target_x, target_y),
        success_threshold_m=success_threshold_m,
    )
    return result
