"""Goal-conditioned behavior-cloning experiment for the MuJoCo reach task."""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, replace
from math import cos, hypot, sin
from pathlib import Path
from statistics import mean

import torch
from p37_neuro.data.schema import Episode, EpisodeStep, Observation
from p37_neuro.data.storage import write_episode
from p37_neuro.integration.manifest import load_robot_manifest, resolve_description
from p37_neuro.simulation.randomization import DomainRandomization
from p37_neuro_ml.checkpoint import load_checkpoint, save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.inference import InferenceSession
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer, BrainBatch

from p37_neuro_sim.mujoco_adapter import MuJoCoAdapter
from p37_neuro_sim.reach_benchmark import generate_expert_episode


@dataclass(frozen=True, slots=True)
class ReachEvaluation:
    target_x_m: float
    target_y_m: float
    learned_success: bool
    baseline_success: bool
    learned_final_distance_m: float
    baseline_final_distance_m: float
    learned_steps: int
    baseline_steps: int
    safety_clamp_count: int
    inference_mean_ms: float


@dataclass(frozen=True, slots=True)
class RandomizedReachEvaluation:
    target_x_m: float
    target_y_m: float
    mass_scale: float
    friction_scale: float
    motor_strength_scale: float
    learned_success: bool
    baseline_success: bool
    learned_final_distance_m: float
    baseline_final_distance_m: float
    safety_clamp_count: int


@dataclass(frozen=True, slots=True)
class LearnedReachResult:
    seed: int
    training_targets: int
    validation_targets: int
    evaluation_targets: int
    candidate_count: int
    selected_candidate_seed: int
    selected_validation_success_rate: float
    selected_validation_mean_distance_m: float
    epochs: int
    initial_action_loss: float
    final_action_loss: float
    learned_success_rate: float
    baseline_success_rate: float
    learned_mean_final_distance_m: float
    baseline_mean_final_distance_m: float
    safety_clamp_count: int
    inference_mean_ms: float
    inference_p95_ms: float
    qualification_success_rate: float
    nominal_qualified: bool
    dynamics_randomization_unlocked: bool
    randomized_success_rate: float | None
    randomized_baseline_success_rate: float | None
    randomized_mean_final_distance_m: float | None
    dynamics_randomization_passed: bool | None
    checkpoint_dir: str
    demonstrations_dir: str
    evaluations_path: str
    metrics_path: str
    randomized_evaluations_path: str | None
    candidate_metrics_path: str


@dataclass(frozen=True, slots=True)
class LearnedReachSuiteResult:
    seeds: tuple[int, ...]
    runs: int
    total_heldout_trials: int
    aggregate_success_rate: float
    aggregate_success_ci95_low: float
    aggregate_success_ci95_high: float
    worst_seed_success_rate: float
    best_seed_success_rate: float
    baseline_success_rate: float
    total_safety_clamps: int
    qualified_runs: int
    randomized_qualified_runs: int
    qualification_success_rate: float
    suite_qualified: bool
    morphology_evaluation_unlocked: bool
    metrics_path: str


@dataclass(frozen=True, slots=True)
class HeldoutMorphologyResult:
    robot_id: str
    checkpoint_dir: str
    seed: int
    evaluation_targets: int
    learned_success_rate: float
    baseline_success_rate: float
    learned_mean_final_distance_m: float
    baseline_mean_final_distance_m: float
    safety_clamp_count: int
    qualification_success_rate: float
    qualified: bool
    evaluations_path: str
    metrics_path: str


def _sample_targets(seed: int, count: int) -> tuple[tuple[float, float], ...]:
    generator = random.Random(seed)
    targets: list[tuple[float, float]] = []
    for _ in range(count):
        # The geometric inner workspace starts at 0.04 m, but the declared
        # elbow limit of 2 radians raises the safe inner radius to about 0.22 m.
        radius = generator.uniform(0.23, 0.36)
        angle = generator.uniform(-0.35, 1.35)
        targets.append((radius * cos(angle), radius * sin(angle)))
    return tuple(targets)


def _task_features(targets: tuple[tuple[float, float], ...]) -> torch.Tensor:
    return torch.tensor(
        [[[x / 0.4, y / 0.4, hypot(x, y) / 0.4, 1.0]] for x, y in targets],
        dtype=torch.float32,
    )


def _distance(observation: Observation, target: tuple[float, float]) -> float:
    return hypot(
        observation.state["end_effector_x_m"] - target[0],
        observation.state["end_effector_y_m"] - target[1],
    )


def _augment_observation(
    observation: Observation,
    end_effector: tuple[float, float, float],
    target: tuple[float, float],
) -> Observation:
    return Observation(
        timestamp_s=observation.timestamp_s,
        joint_position=observation.joint_position,
        joint_velocity=observation.joint_velocity,
        state={
            "end_effector_x_m": end_effector[0],
            "end_effector_y_m": end_effector[1],
            "end_effector_z_m": end_effector[2],
            "goal_x_m": target[0],
            "goal_y_m": target[1],
        },
    )


def _evaluate_learned(
    model: P37Neuro,
    manifest_path: str | Path,
    *,
    target: tuple[float, float],
    seed: int,
    steps: int,
    success_threshold_m: float,
    dynamics: dict[str, float] | None = None,
) -> tuple[Episode, float, int, tuple[float, ...]]:
    manifest = load_robot_manifest(manifest_path)
    description = resolve_description(manifest, manifest_path=manifest_path)
    adapter = MuJoCoAdapter(
        description,
        control_period_s=1.0 / manifest.runtime.control_frequency_hz,
    )
    if dynamics is not None:
        adapter.apply_dynamics_randomization(dynamics)
    session = InferenceSession(
        model,
        adapter.embodiment,
        task_features=_task_features((target,)),
    )
    observation = adapter.reset(seed)
    rows: list[EpisodeStep] = []
    latencies_ms: list[float] = []
    clamp_count = 0
    final_distance = float("inf")
    try:
        for step_index in range(steps):
            task_observation = _augment_observation(
                observation, adapter.body_position("end_effector"), target
            )
            final_distance = _distance(task_observation, target)
            # Reach is a reactive goal-conditioned task. Resetting recurrent
            # memory prevents an untrained long-horizon state from changing the
            # desired joint target while preserving the standard inference path.
            session.reset()
            started = time.perf_counter_ns()
            action = session.act(task_observation)
            latencies_ms.append((time.perf_counter_ns() - started) / 1_000_000.0)
            clamp_count += len(session.last_clamped_joints)
            terminal = final_distance <= success_threshold_m or step_index == steps - 1
            rows.append(
                EpisodeStep(
                    observation=task_observation,
                    action=action,
                    reward=-final_distance,
                    terminal=terminal,
                    failure_code=(
                        "reach_timeout"
                        if terminal and final_distance > success_threshold_m
                        else None
                    ),
                )
            )
            if final_distance <= success_threshold_m:
                break
            observation = adapter.step(action)
    finally:
        adapter.close()
    return (
        Episode(
            episode_id=f"learned-reach-{seed}",
            embodiment_id=manifest.robot_id,
            task_id="goal-conditioned-cartesian-reach",
            steps=tuple(rows),
            source="p37-mujoco-learned-policy",
            metadata={
                "target_x_m": str(target[0]),
                "target_y_m": str(target[1]),
                "capability_evidence": "held-out-simulation",
                "dynamics": json.dumps(dynamics or {}, sort_keys=True),
            },
        ),
        final_distance,
        clamp_count,
        tuple(latencies_ms),
    )


def _percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, int(0.95 * len(ordered)) - 1)]


def _wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    """Return the 95% Wilson score interval for a binomial success rate."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Wilson interval requires 0 <= successes <= positive trials")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    margin = (
        z
        * ((proportion * (1.0 - proportion) + z * z / (4.0 * trials)) / trials) ** 0.5
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _new_reach_model() -> P37Neuro:
    return P37Neuro(
        NeuroConfig(
            task_feature_dim=4,
            model_dim=32,
            high_level_dim=8,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=4,
            dropout=0.0,
        )
    )


def _train_candidate(
    batch: BrainBatch,
    *,
    candidate_seed: int,
    epochs: int,
) -> tuple[P37Neuro, float, float]:
    torch.manual_seed(candidate_seed)
    model = _new_reach_model()
    trainer = BehaviorCloningTrainer(
        model,
        learning_rate=2e-3,
        weight_decay=0.0,
        max_gradient_norm=5.0,
    )
    initial_loss = trainer.step(batch).action_loss
    final_loss = initial_loss
    for _ in range(epochs - 1):
        final_loss = trainer.step(batch).action_loss
    return model, initial_loss, final_loss


def _score_candidate(
    model: P37Neuro,
    manifest_path: str | Path,
    *,
    targets: tuple[tuple[float, float], ...],
    seed: int,
    evaluation_steps: int,
    success_threshold_m: float,
) -> tuple[float, float]:
    distances: list[float] = []
    for index, target in enumerate(targets):
        _, distance, _, _ = _evaluate_learned(
            model,
            manifest_path,
            target=target,
            seed=seed + index,
            steps=evaluation_steps,
            success_threshold_m=success_threshold_m,
        )
        distances.append(distance)
    success_rate = mean(float(distance <= success_threshold_m) for distance in distances)
    return success_rate, mean(distances)


def run_learned_reach_experiment(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    seed: int = 317,
    train_target_count: int = 64,
    validation_target_count: int = 32,
    evaluation_target_count: int = 20,
    candidate_count: int = 3,
    epochs: int = 200,
    evaluation_steps: int = 100,
    success_threshold_m: float = 0.025,
    qualification_success_rate: float = 0.90,
) -> dict[str, object]:
    """Generate expert data, train once, and evaluate on untouched targets."""
    if (
        min(
            train_target_count,
            validation_target_count,
            evaluation_target_count,
            candidate_count,
            epochs,
            evaluation_steps,
        )
        <= 0
    ):
        raise ValueError("target counts, epochs and evaluation steps must be positive")
    if not 0.0 <= qualification_success_rate <= 1.0:
        raise ValueError("qualification_success_rate must be in [0, 1]")

    output = Path(output_dir)
    demonstrations_dir = output / "demonstrations"
    learned_episodes_dir = output / "learned-evaluations"
    checkpoint_dir = output / "checkpoint"
    demonstrations_dir.mkdir(parents=True, exist_ok=True)
    learned_episodes_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_robot_manifest(manifest_path)
    adapter = MuJoCoAdapter(resolve_description(manifest, manifest_path=manifest_path))
    embodiment = replace(adapter.embodiment, embodiment_id=manifest.robot_id)
    adapter.close()

    all_targets = _sample_targets(
        seed, train_target_count + validation_target_count + evaluation_target_count
    )
    train_targets = all_targets[:train_target_count]
    validation_targets = all_targets[
        train_target_count : train_target_count + validation_target_count
    ]
    evaluation_targets = all_targets[train_target_count + validation_target_count :]
    demonstrations: list[Episode] = []
    for index, target in enumerate(train_targets):
        episode = generate_expert_episode(
            manifest_path,
            target=target,
            steps=evaluation_steps,
            seed=seed + index,
            success_threshold_m=success_threshold_m,
        )
        demonstrations.append(episode)
        write_episode(demonstrations_dir / f"train-{index:04d}.jsonl", episode)

    # Train on the decision made from the reset state. Later expert states are
    # highly correlated with the target joint command and let a model minimize
    # loss by copying proprioception while ignoring the Cartesian goal.
    training_examples = tuple(
        EpisodeExample(replace(episode, steps=(episode.steps[0],)), embodiment)
        for episode in demonstrations
    )
    batch = collate_episodes(training_examples)
    batch.task_features = _task_features(train_targets)
    batch.target_values = None
    candidate_rows: list[dict[str, float | int]] = []
    candidates: list[tuple[P37Neuro, float, float, float, float, int]] = []
    for candidate_index in range(candidate_count):
        candidate_seed = seed + candidate_index * 1_000_003
        candidate, initial_loss, final_loss = _train_candidate(
            batch,
            candidate_seed=candidate_seed,
            epochs=epochs,
        )
        validation_rate, validation_distance = _score_candidate(
            candidate,
            manifest_path,
            targets=validation_targets,
            seed=seed + 5_000 + candidate_index * validation_target_count,
            evaluation_steps=evaluation_steps,
            success_threshold_m=success_threshold_m,
        )
        candidates.append(
            (
                candidate,
                initial_loss,
                final_loss,
                validation_rate,
                validation_distance,
                candidate_seed,
            )
        )
        candidate_rows.append(
            {
                "candidate_seed": candidate_seed,
                "initial_action_loss": initial_loss,
                "final_action_loss": final_loss,
                "validation_success_rate": validation_rate,
                "validation_mean_distance_m": validation_distance,
            }
        )
    (
        model,
        initial_action_loss,
        final_action_loss,
        validation_rate,
        validation_distance,
        selected_seed,
    ) = max(
        candidates,
        key=lambda item: (item[3], -item[4], -item[2]),
    )
    candidate_metrics_path = output / "candidate-metrics.json"
    candidate_metrics_path.write_text(
        json.dumps(candidate_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "goal-conditioned-mujoco-reach",
            "seed": seed,
            "selected_candidate_seed": selected_seed,
            "training_targets": train_target_count,
            "validation_targets": validation_target_count,
            "heldout_evaluation_targets": evaluation_target_count,
        },
    )

    evaluations: list[ReachEvaluation] = []
    all_latencies: list[float] = []
    for index, target in enumerate(evaluation_targets):
        evaluation_seed = seed + 10_000 + index
        learned_episode, learned_distance, clamps, latencies = _evaluate_learned(
            model,
            manifest_path,
            target=target,
            seed=evaluation_seed,
            steps=evaluation_steps,
            success_threshold_m=success_threshold_m,
        )
        write_episode(learned_episodes_dir / f"heldout-{index:04d}.jsonl", learned_episode)
        baseline_episode = generate_expert_episode(
            manifest_path,
            target=target,
            steps=evaluation_steps,
            seed=evaluation_seed,
            success_threshold_m=success_threshold_m,
        )
        baseline_distance = _distance(baseline_episode.steps[-1].observation, target)
        all_latencies.extend(latencies)
        evaluations.append(
            ReachEvaluation(
                target_x_m=target[0],
                target_y_m=target[1],
                learned_success=learned_distance <= success_threshold_m,
                baseline_success=baseline_distance <= success_threshold_m,
                learned_final_distance_m=learned_distance,
                baseline_final_distance_m=baseline_distance,
                learned_steps=len(learned_episode.steps),
                baseline_steps=len(baseline_episode.steps),
                safety_clamp_count=clamps,
                inference_mean_ms=mean(latencies),
            )
        )

    learned_success_rate = mean(float(item.learned_success) for item in evaluations)
    baseline_success_rate = mean(float(item.baseline_success) for item in evaluations)
    total_clamps = sum(item.safety_clamp_count for item in evaluations)
    qualified = learned_success_rate >= qualification_success_rate and total_clamps == 0
    evaluations_path = output / "heldout-evaluations.json"
    metrics_path = output / "metrics.json"
    evaluations_path.write_text(
        json.dumps([asdict(item) for item in evaluations], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    randomized_success_rate: float | None = None
    randomized_baseline_success_rate: float | None = None
    randomized_mean_distance: float | None = None
    randomized_passed: bool | None = None
    randomized_evaluations_path: Path | None = None
    if qualified:
        randomization = DomainRandomization(
            sensor_noise_std=(0.0, 0.0),
            latency_s=(0.0, 0.0),
        )
        randomized_rows: list[RandomizedReachEvaluation] = []
        randomized_episodes_dir = output / "randomized-evaluations"
        randomized_episodes_dir.mkdir(parents=True, exist_ok=True)
        for index, target in enumerate(evaluation_targets):
            evaluation_seed = seed + 20_000 + index
            sampled = randomization.sample(evaluation_seed)
            dynamics = {
                name: sampled[name]
                for name in ("mass_scale", "friction_scale", "motor_strength_scale")
            }
            learned_episode, learned_distance, clamps, _ = _evaluate_learned(
                model,
                manifest_path,
                target=target,
                seed=evaluation_seed,
                steps=evaluation_steps,
                success_threshold_m=success_threshold_m,
                dynamics=dynamics,
            )
            write_episode(randomized_episodes_dir / f"heldout-{index:04d}.jsonl", learned_episode)
            baseline_episode = generate_expert_episode(
                manifest_path,
                target=target,
                steps=evaluation_steps,
                seed=evaluation_seed,
                success_threshold_m=success_threshold_m,
                dynamics=dynamics,
            )
            baseline_distance = _distance(baseline_episode.steps[-1].observation, target)
            randomized_rows.append(
                RandomizedReachEvaluation(
                    target_x_m=target[0],
                    target_y_m=target[1],
                    mass_scale=dynamics["mass_scale"],
                    friction_scale=dynamics["friction_scale"],
                    motor_strength_scale=dynamics["motor_strength_scale"],
                    learned_success=learned_distance <= success_threshold_m,
                    baseline_success=baseline_distance <= success_threshold_m,
                    learned_final_distance_m=learned_distance,
                    baseline_final_distance_m=baseline_distance,
                    safety_clamp_count=clamps,
                )
            )
        randomized_success_rate = mean(float(item.learned_success) for item in randomized_rows)
        randomized_baseline_success_rate = mean(
            float(item.baseline_success) for item in randomized_rows
        )
        randomized_mean_distance = mean(item.learned_final_distance_m for item in randomized_rows)
        randomized_clamps = sum(item.safety_clamp_count for item in randomized_rows)
        randomized_passed = (
            randomized_success_rate >= qualification_success_rate and randomized_clamps == 0
        )
        randomized_evaluations_path = output / "randomized-evaluations.json"
        randomized_evaluations_path.write_text(
            json.dumps([asdict(item) for item in randomized_rows], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    result = LearnedReachResult(
        seed=seed,
        training_targets=train_target_count,
        validation_targets=validation_target_count,
        evaluation_targets=evaluation_target_count,
        candidate_count=candidate_count,
        selected_candidate_seed=selected_seed,
        selected_validation_success_rate=validation_rate,
        selected_validation_mean_distance_m=validation_distance,
        epochs=epochs,
        initial_action_loss=initial_action_loss,
        final_action_loss=final_action_loss,
        learned_success_rate=learned_success_rate,
        baseline_success_rate=baseline_success_rate,
        learned_mean_final_distance_m=mean(item.learned_final_distance_m for item in evaluations),
        baseline_mean_final_distance_m=mean(item.baseline_final_distance_m for item in evaluations),
        safety_clamp_count=total_clamps,
        inference_mean_ms=mean(all_latencies),
        inference_p95_ms=_percentile_95(all_latencies),
        qualification_success_rate=qualification_success_rate,
        nominal_qualified=qualified,
        dynamics_randomization_unlocked=qualified,
        randomized_success_rate=randomized_success_rate,
        randomized_baseline_success_rate=randomized_baseline_success_rate,
        randomized_mean_final_distance_m=randomized_mean_distance,
        dynamics_randomization_passed=randomized_passed,
        checkpoint_dir=str(checkpoint_dir),
        demonstrations_dir=str(demonstrations_dir),
        evaluations_path=str(evaluations_path),
        metrics_path=str(metrics_path),
        randomized_evaluations_path=(
            str(randomized_evaluations_path) if randomized_evaluations_path is not None else None
        ),
        candidate_metrics_path=str(candidate_metrics_path),
    )
    payload = asdict(result)
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def run_learned_reach_suite(
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    seeds: tuple[int, ...] = (317, 401, 503, 607, 719),
    train_target_count: int = 64,
    validation_target_count: int = 32,
    evaluation_target_count: int = 100,
    candidate_count: int = 3,
    epochs: int = 200,
    evaluation_steps: int = 100,
    success_threshold_m: float = 0.025,
    qualification_success_rate: float = 0.90,
) -> dict[str, object]:
    """Repeat complete training runs and gate morphology work on worst-seed results."""
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("suite seeds must be non-empty and unique")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    run_results: list[dict[str, object]] = []
    for seed in seeds:
        run_results.append(
            run_learned_reach_experiment(
                manifest_path,
                output_dir=output / f"seed-{seed}",
                seed=seed,
                train_target_count=train_target_count,
                validation_target_count=validation_target_count,
                evaluation_target_count=evaluation_target_count,
                candidate_count=candidate_count,
                epochs=epochs,
                evaluation_steps=evaluation_steps,
                success_threshold_m=success_threshold_m,
                qualification_success_rate=qualification_success_rate,
            )
        )

    rates = [float(run["learned_success_rate"]) for run in run_results]
    baseline_rates = [float(run["baseline_success_rate"]) for run in run_results]
    total_trials = len(seeds) * evaluation_target_count
    total_successes = sum(round(rate * evaluation_target_count) for rate in rates)
    interval_low, interval_high = _wilson_interval(total_successes, total_trials)
    total_clamps = sum(int(run["safety_clamp_count"]) for run in run_results)
    qualified_runs = sum(bool(run["nominal_qualified"]) for run in run_results)
    randomized_qualified_runs = sum(
        run["dynamics_randomization_passed"] is True for run in run_results
    )
    aggregate_rate = total_successes / total_trials
    suite_qualified = (
        aggregate_rate >= qualification_success_rate
        and min(rates) >= qualification_success_rate
        and min(baseline_rates) == 1.0
        and total_clamps == 0
    )
    metrics_path = output / "suite-metrics.json"
    result = LearnedReachSuiteResult(
        seeds=seeds,
        runs=len(seeds),
        total_heldout_trials=total_trials,
        aggregate_success_rate=aggregate_rate,
        aggregate_success_ci95_low=interval_low,
        aggregate_success_ci95_high=interval_high,
        worst_seed_success_rate=min(rates),
        best_seed_success_rate=max(rates),
        baseline_success_rate=mean(baseline_rates),
        total_safety_clamps=total_clamps,
        qualified_runs=qualified_runs,
        randomized_qualified_runs=randomized_qualified_runs,
        qualification_success_rate=qualification_success_rate,
        suite_qualified=suite_qualified,
        morphology_evaluation_unlocked=suite_qualified,
        metrics_path=str(metrics_path),
    )
    payload = {**asdict(result), "run_results": run_results}
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def run_heldout_morphology_evaluation(
    checkpoint_dir: str | Path,
    manifest_path: str | Path,
    *,
    output_dir: str | Path,
    seed: int = 911,
    evaluation_target_count: int = 100,
    evaluation_steps: int = 100,
    success_threshold_m: float = 0.025,
    qualification_success_rate: float = 0.90,
) -> dict[str, object]:
    """Evaluate one frozen checkpoint on an arm absent from training and selection."""
    if min(evaluation_target_count, evaluation_steps) <= 0:
        raise ValueError("evaluation target count and steps must be positive")
    if not 0.0 <= qualification_success_rate <= 1.0:
        raise ValueError("qualification_success_rate must be in [0, 1]")
    model, _ = load_checkpoint(checkpoint_dir)
    manifest = load_robot_manifest(manifest_path)
    output = Path(output_dir)
    episodes_dir = output / "heldout-morphology-episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    targets = _sample_targets(seed, evaluation_target_count)
    rows: list[ReachEvaluation] = []
    for index, target in enumerate(targets):
        evaluation_seed = seed + 30_000 + index
        learned_episode, learned_distance, clamps, latencies = _evaluate_learned(
            model,
            manifest_path,
            target=target,
            seed=evaluation_seed,
            steps=evaluation_steps,
            success_threshold_m=success_threshold_m,
        )
        write_episode(episodes_dir / f"heldout-{index:04d}.jsonl", learned_episode)
        baseline_episode = generate_expert_episode(
            manifest_path,
            target=target,
            steps=evaluation_steps,
            seed=evaluation_seed,
            success_threshold_m=success_threshold_m,
        )
        baseline_distance = _distance(baseline_episode.steps[-1].observation, target)
        rows.append(
            ReachEvaluation(
                target_x_m=target[0],
                target_y_m=target[1],
                learned_success=learned_distance <= success_threshold_m,
                baseline_success=baseline_distance <= success_threshold_m,
                learned_final_distance_m=learned_distance,
                baseline_final_distance_m=baseline_distance,
                learned_steps=len(learned_episode.steps),
                baseline_steps=len(baseline_episode.steps),
                safety_clamp_count=clamps,
                inference_mean_ms=mean(latencies),
            )
        )
    learned_rate = mean(float(row.learned_success) for row in rows)
    baseline_rate = mean(float(row.baseline_success) for row in rows)
    clamps = sum(row.safety_clamp_count for row in rows)
    qualified = learned_rate >= qualification_success_rate and baseline_rate == 1.0 and clamps == 0
    evaluations_path = output / "heldout-morphology-evaluations.json"
    metrics_path = output / "heldout-morphology-metrics.json"
    evaluations_path.write_text(
        json.dumps([asdict(row) for row in rows], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = HeldoutMorphologyResult(
        robot_id=manifest.robot_id,
        checkpoint_dir=str(checkpoint_dir),
        seed=seed,
        evaluation_targets=evaluation_target_count,
        learned_success_rate=learned_rate,
        baseline_success_rate=baseline_rate,
        learned_mean_final_distance_m=mean(row.learned_final_distance_m for row in rows),
        baseline_mean_final_distance_m=mean(row.baseline_final_distance_m for row in rows),
        safety_clamp_count=clamps,
        qualification_success_rate=qualification_success_rate,
        qualified=qualified,
        evaluations_path=str(evaluations_path),
        metrics_path=str(metrics_path),
    )
    payload = asdict(result)
    metrics_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload
