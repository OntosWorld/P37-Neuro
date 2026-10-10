"""Closed-loop MuJoCo reach benchmark with canonical P37 evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from math import acos, atan2, hypot, sin
from pathlib import Path

from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.storage import write_episode
from p37_neuro.integration.manifest import load_robot_manifest, resolve_description
from p37_neuro.integration.simulate import ReachBenchmarkResult
from p37_neuro.runtime.safety import JointSafetyEnvelope

from p37_neuro_sim.mujoco_adapter import MuJoCoAdapter


class ReachBenchmarkConfigurationError(ValueError):
    """Raised when the reference reach task cannot be configured safely."""


def _inverse_kinematics(target: tuple[float, float]) -> tuple[float, float]:
    """Solve the elbow-down branch for the reference two-link planar arm."""
    link_1 = 0.22
    link_2 = 0.18
    x, y = target
    cosine_elbow = (x * x + y * y - link_1 * link_1 - link_2 * link_2) / (2.0 * link_1 * link_2)
    if not -1.0 <= cosine_elbow <= 1.0:
        raise ReachBenchmarkConfigurationError(
            f"target ({x:.3f}, {y:.3f}) is outside the reference arm workspace"
        )
    elbow = acos(cosine_elbow)
    shoulder = atan2(y, x) - atan2(
        link_2 * sin(elbow),
        link_1 + link_2 * cosine_elbow,
    )
    return shoulder, elbow


def _task_observation(
    observation: Observation,
    end_effector: tuple[float, float, float],
    target: tuple[float, float],
) -> Observation:
    return Observation(
        timestamp_s=observation.timestamp_s,
        joint_position=observation.joint_position,
        joint_velocity=observation.joint_velocity,
        sensor_refs=observation.sensor_refs,
        state={
            **observation.state,
            "end_effector_x_m": end_effector[0],
            "end_effector_y_m": end_effector[1],
            "end_effector_z_m": end_effector[2],
            "goal_x_m": target[0],
            "goal_y_m": target[1],
        },
    )


def _distance(end_effector: tuple[float, float, float], target: tuple[float, float]) -> float:
    return hypot(end_effector[0] - target[0], end_effector[1] - target[1])


def _rollout(
    description: Path,
    *,
    control_period_s: float,
    target: tuple[float, float],
    steps: int,
    seed: int,
    success_threshold_m: float,
    record_episode: bool,
) -> tuple[list[EpisodeStep], list[tuple[float, ...]], list[float], int]:
    adapter = MuJoCoAdapter(description, control_period_s=control_period_s)
    try:
        joint_names = tuple(joint.name for joint in adapter.embodiment.joints)
        if joint_names != ("shoulder", "elbow"):
            raise ReachBenchmarkConfigurationError(
                "reference reach benchmark requires shoulder and elbow joints in that order"
            )
        shoulder, elbow = _inverse_kinematics(target)
        safety = JointSafetyEnvelope()
        observation = adapter.reset(seed)
        episode_steps: list[EpisodeStep] = []
        states: list[tuple[float, ...]] = []
        distances: list[float] = []
        clamp_count = 0

        for step_index in range(steps):
            end_effector = adapter.body_position("end_effector")
            distance = _distance(end_effector, target)
            task_observation = _task_observation(observation, end_effector, target)
            requested = Action(
                timestamp_s=observation.timestamp_s,
                joint_commands={"shoulder": shoulder, "elbow": elbow},
            )
            safe = safety.apply(requested, adapter.embodiment)
            clamp_count += len(safe.clamped_joints)
            terminal = distance <= success_threshold_m or step_index == steps - 1
            if record_episode:
                episode_steps.append(
                    EpisodeStep(
                        observation=task_observation,
                        action=safe.action,
                        reward=-distance,
                        terminal=terminal,
                        failure_code=(
                            "reach_timeout" if terminal and distance > success_threshold_m else None
                        ),
                    )
                )
            states.append(tuple(observation.joint_position[name] for name in joint_names))
            distances.append(distance)
            if distance <= success_threshold_m:
                break
            observation = adapter.step(safe.action)

        return episode_steps, states, distances, clamp_count
    finally:
        adapter.close()


def run_reach_benchmark(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    steps: int,
    seed: int,
    target: tuple[float, float],
    success_threshold_m: float,
) -> ReachBenchmarkResult:
    """Run and replay one deterministic reach trial, then persist evidence."""
    manifest = load_robot_manifest(manifest_path)
    description = resolve_description(manifest, manifest_path=manifest_path)
    rollout_args = {
        "control_period_s": 1.0 / manifest.runtime.control_frequency_hz,
        "target": target,
        "steps": steps,
        "seed": seed,
        "success_threshold_m": success_threshold_m,
    }
    episode_steps, states, distances, clamp_count = _rollout(
        description, **rollout_args, record_episode=True
    )
    _, replay_states, replay_distances, _ = _rollout(
        description, **rollout_args, record_episode=False
    )
    if len(states) != len(replay_states):
        raise RuntimeError("deterministic replay produced a different rollout length")
    replay_error = max(
        (
            abs(value - replay_value)
            for state, replay_state in zip(states, replay_states, strict=True)
            for value, replay_value in zip(state, replay_state, strict=True)
        ),
        default=0.0,
    )
    replay_distance_error = max(
        (
            abs(value - replay_value)
            for value, replay_value in zip(distances, replay_distances, strict=True)
        ),
        default=0.0,
    )
    replay_error = max(replay_error, replay_distance_error)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    episode_path = output / "reach-episode.jsonl"
    metrics_path = output / "reach-metrics.json"
    episode = Episode(
        episode_id=f"reach-seed-{seed}",
        embodiment_id=manifest.robot_id,
        task_id="cartesian-reach",
        steps=tuple(episode_steps),
        source="p37-mujoco-reach-benchmark",
        metadata={
            "controller": "analytic-ik-baseline",
            "target_x_m": str(target[0]),
            "target_y_m": str(target[1]),
            "capability_evidence": "baseline-only",
        },
    )
    write_episode(episode_path, episode)
    result = ReachBenchmarkResult(
        robot_id=manifest.robot_id,
        seed=seed,
        steps=len(episode_steps),
        success=distances[-1] <= success_threshold_m,
        initial_distance_m=distances[0],
        final_distance_m=distances[-1],
        minimum_distance_m=min(distances),
        success_threshold_m=success_threshold_m,
        safety_clamp_count=clamp_count,
        replay_max_joint_error=replay_error,
        episode_path=str(episode_path),
        metrics_path=str(metrics_path),
    )
    metrics_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    return result
