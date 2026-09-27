"""CPU-only E3 one-shot demonstration-conditioning smoke experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import cos, sin
from pathlib import Path

import torch
from p37_neuro.benchmarks.demonstration import OneShotTrial, one_shot_metrics
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.simulation.morphology import MorphologyRange, generate_morphology

from p37_neuro_ml.checkpoint import save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.losses import imitation_loss
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer, BrainBatch


@dataclass(frozen=True, slots=True)
class DemonstrationExample:
    example: EpisodeExample
    target_xyz: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class E3SmokeResult:
    seed: int
    epochs: int
    training_tasks: int
    heldout_tasks: int
    heldout_embodiment_joints: int
    initial_train_action_mse: float
    final_train_action_mse: float
    initial_heldout_action_mse: float
    final_heldout_action_mse: float
    one_shot_success_rate: float
    qualifying_trials: int
    checkpoint_dir: str


def _body(seed: int, joints: int):
    return generate_morphology(
        seed,
        MorphologyRange(min_joints=joints, max_joints=joints),
    )


def _targets(offset: int, count: int) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (
            0.8 * sin((index + offset) * 0.43),
            0.7 * cos((index + offset) * 0.61),
            0.6 * sin((index + offset) * 0.29 + 0.8),
        )
        for index in range(count)
    )


def _demo_image(target: tuple[float, float, float]) -> torch.Tensor:
    image = torch.zeros(3, 16, 16)
    for channel, value in enumerate(target):
        image[channel].fill_((value + 1.0) / 2.0)
    image[:, 4:12, 4:12] = image[:, 4:12, 4:12] * 0.75 + 0.1
    return image.clamp(0.0, 1.0)


def _episode(body, target: tuple[float, float, float], task_index: int) -> Episode:
    x, y, z = target
    steps: list[EpisodeStep] = []
    for step in range(4):
        positions: dict[str, float] = {}
        velocities: dict[str, float] = {}
        commands: dict[str, float] = {}

        for joint_index, joint in enumerate(body.joints):
            assert joint.position is not None
            midpoint = (joint.position.minimum + joint.position.maximum) / 2.0
            half_range = (joint.position.maximum - joint.position.minimum) / 2.0
            phase = 0.17 * task_index + 0.13 * joint_index
            position_norm = 0.2 * sin(step * 0.5 + phase)
            velocity_norm = 0.12 * cos(step * 0.5 + phase)
            scale = float(joint_index + 1)
            target_norm = (
                0.42 * x * sin(scale * 0.59)
                + 0.33 * y * cos(scale * 0.41)
                + 0.27 * z * sin(scale * 0.23 + 0.5)
                - 0.1 * position_norm
            )
            target_norm = max(-0.9, min(0.9, target_norm))

            positions[joint.name] = midpoint + position_norm * half_range
            velocities[joint.name] = velocity_norm * (joint.velocity_limit or 1.0)
            commands[joint.name] = midpoint + target_norm * half_range

        steps.append(
            EpisodeStep(
                observation=Observation(
                    timestamp_s=step * 0.05,
                    joint_position=positions,
                    joint_velocity=velocities,
                ),
                action=Action(
                    timestamp_s=step * 0.05,
                    joint_commands=commands,
                ),
                reward=1.0,
                terminal=step == 3,
            )
        )

    return Episode(
        episode_id=f"{body.embodiment_id}-demo-{task_index}",
        embodiment_id=body.embodiment_id,
        task_id=f"demo-task-{task_index}",
        steps=tuple(steps),
        source="p37-e3-cpu-smoke",
        metadata={"capability_evidence": "false"},
    )


def _examples(
    seed: int,
    joint_counts: tuple[int, ...],
    targets: tuple[tuple[float, float, float], ...],
    *,
    task_offset: int,
) -> tuple[DemonstrationExample, ...]:
    rows: list[DemonstrationExample] = []
    for body_index, joints in enumerate(joint_counts):
        body = _body(seed + body_index * 211, joints)
        for target_index, target in enumerate(targets):
            task_index = task_offset + target_index
            rows.append(
                DemonstrationExample(
                    EpisodeExample(_episode(body, target, task_index), body),
                    target,
                )
            )
    return tuple(rows)


def _batch(rows: tuple[DemonstrationExample, ...]) -> BrainBatch:
    base = collate_episodes(tuple(row.example for row in rows))
    demos = torch.stack(tuple(_demo_image(row.target_xyz) for row in rows), dim=0)[:, None]
    return BrainBatch(
        joint_features=base.joint_features,
        joint_state=base.joint_state,
        joint_mask=base.joint_mask,
        time_mask=base.time_mask,
        target_actions=base.target_actions,
        target_values=base.target_values,
        demonstration_images=demos,
    )


def _mse(model: P37Neuro, rows: tuple[DemonstrationExample, ...]) -> float:
    batch = _batch(rows)
    model.eval()
    with torch.no_grad():
        output = model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
            demonstration_images=batch.demonstration_images,
        )
        loss = imitation_loss(
            output,
            target_actions=batch.target_actions,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
        )
    return float(loss.action)


def _one_shot_trials(
    model: P37Neuro,
    rows: tuple[DemonstrationExample, ...],
    *,
    threshold: float = 0.05,
) -> tuple[OneShotTrial, ...]:
    trials: list[OneShotTrial] = []
    for row in rows:
        error = _mse(model, (row,))
        success = error <= threshold
        trials.append(
            OneShotTrial(
                task_id=row.example.episode.task_id,
                embodiment_id=row.example.embodiment.embodiment_id,
                task_was_held_out=True,
                demonstration_count=1,
                gradient_updates=0,
                success=success,
                completed_stages=1 if success else 0,
                total_stages=1,
                duration_s=float(len(row.example.episode.steps)) * 0.05,
            )
        )
    return tuple(trials)


def run_e3_cpu_smoke(
    output_dir: str | Path,
    *,
    seed: int = 101,
    epochs: int = 80,
) -> E3SmokeResult:
    """Train demo conditioning and test unseen tasks with one demo and no updates."""
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    torch.manual_seed(seed)

    train_targets = _targets(1, 12)
    heldout_targets = _targets(101, 6)
    train_rows = _examples(seed, (4, 5), train_targets, task_offset=0)
    heldout_rows = _examples(seed + 1000, (6,), heldout_targets, task_offset=1000)
    train_batch = _batch(train_rows)

    model = P37Neuro(
        NeuroConfig(
            model_dim=32,
            task_feature_dim=8,
            high_level_dim=8,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=4,
            dropout=0.0,
        )
    )
    trainer = BehaviorCloningTrainer(
        model,
        learning_rate=2e-3,
        weight_decay=0.0,
        max_gradient_norm=5.0,
    )

    initial_train = _mse(model, train_rows)
    initial_heldout = _mse(model, heldout_rows)
    for _ in range(epochs):
        trainer.step(train_batch)
    final_train = _mse(model, train_rows)
    final_heldout = _mse(model, heldout_rows)

    trials = _one_shot_trials(model, heldout_rows)
    metrics = one_shot_metrics(trials)

    root = Path(output_dir)
    checkpoint_dir = root / "checkpoint"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "e3-one-shot-smoke",
            "seed": seed,
            "epochs": epochs,
            "demonstrations_per_eval_task": 1,
            "gradient_updates_during_eval": 0,
            "capability_evidence": "false",
        },
    )
    result = E3SmokeResult(
        seed=seed,
        epochs=epochs,
        training_tasks=len(train_targets),
        heldout_tasks=len(heldout_targets),
        heldout_embodiment_joints=6,
        initial_train_action_mse=initial_train,
        final_train_action_mse=final_train,
        initial_heldout_action_mse=initial_heldout,
        final_heldout_action_mse=final_heldout,
        one_shot_success_rate=metrics["success_rate"],
        qualifying_trials=int(metrics["trial_count"]),
        checkpoint_dir=str(checkpoint_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "metrics.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e3-one-shot-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e3-one-shot-smoke"))
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--epochs", type=int, default=80)
    args = parser.parse_args()
    result = run_e3_cpu_smoke(args.output, seed=args.seed, epochs=args.epochs)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
