"""CPU-only E2 cross-embodiment manipulation smoke experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import cos, sin
from pathlib import Path

import torch
from p37_neuro.benchmarks.manipulation import ManipulationTrial, transfer_metrics
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.simulation.morphology import MorphologyRange, generate_morphology

from p37_neuro_ml.checkpoint import save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.losses import imitation_loss
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer, BrainBatch


@dataclass(frozen=True, slots=True)
class ManipulationExample:
    example: EpisodeExample
    target_xyz: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class E2SmokeResult:
    seed: int
    epochs: int
    train_joint_counts: tuple[int, ...]
    heldout_joint_counts: tuple[int, ...]
    initial_train_action_mse: float
    final_train_action_mse: float
    initial_heldout_action_mse: float
    final_heldout_action_mse: float
    heldout_success_rate: float
    checkpoint_dir: str


def _body(seed: int, joints: int):
    return generate_morphology(
        seed,
        MorphologyRange(min_joints=joints, max_joints=joints),
    )


def _task_vectors(offset: int, count: int) -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (
            0.75 * sin((index + offset) * 0.71),
            0.65 * cos((index + offset) * 0.53),
            0.55 * sin((index + offset) * 0.37 + 0.4),
        )
        for index in range(count)
    )


def _episode(body, target_xyz: tuple[float, float, float], task_index: int) -> Episode:
    x, y, z = target_xyz
    rows: list[EpisodeStep] = []
    for step in range(5):
        positions: dict[str, float] = {}
        velocities: dict[str, float] = {}
        commands: dict[str, float] = {}
        for joint_index, joint in enumerate(body.joints):
            assert joint.position is not None
            midpoint = (joint.position.minimum + joint.position.maximum) / 2.0
            half_range = (joint.position.maximum - joint.position.minimum) / 2.0
            phase = 0.31 * task_index + 0.19 * joint_index
            position_norm = 0.25 * sin(0.45 * step + phase)
            velocity_norm = 0.15 * cos(0.45 * step + phase)
            joint_phase = joint_index + 1
            target_norm = (
                0.45 * x * sin(joint_phase * 0.71)
                + 0.35 * y * cos(joint_phase * 0.47)
                + 0.25 * z * sin(joint_phase * 0.29 + 0.3)
                - 0.15 * position_norm
            )
            target_norm = max(-0.9, min(0.9, target_norm))

            positions[joint.name] = midpoint + position_norm * half_range
            velocities[joint.name] = velocity_norm * (joint.velocity_limit or 1.0)
            commands[joint.name] = midpoint + target_norm * half_range

        rows.append(
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
                terminal=step == 4,
            )
        )

    return Episode(
        episode_id=f"{body.embodiment_id}-manip-{task_index}",
        embodiment_id=body.embodiment_id,
        task_id=f"cartesian-{task_index}",
        steps=tuple(rows),
        source="p37-e2-cpu-smoke",
        metadata={
            "target_x": str(x),
            "target_y": str(y),
            "target_z": str(z),
            "capability_evidence": "false",
        },
    )


def _examples(
    seed: int,
    joint_counts: tuple[int, ...],
    task_vectors: tuple[tuple[float, float, float], ...],
) -> tuple[ManipulationExample, ...]:
    rows: list[ManipulationExample] = []
    for body_index, joints in enumerate(joint_counts):
        body = _body(seed + body_index * 101, joints)
        for task_index, target in enumerate(task_vectors):
            rows.append(
                ManipulationExample(
                    EpisodeExample(_episode(body, target, task_index), body),
                    target,
                )
            )
    return tuple(rows)


def _batch(rows: tuple[ManipulationExample, ...]) -> BrainBatch:
    base = collate_episodes(tuple(row.example for row in rows))
    task_features = torch.zeros(len(rows), 1, 8)
    for index, row in enumerate(rows):
        task_features[index, 0, :3] = torch.tensor(row.target_xyz)
    return BrainBatch(
        joint_features=base.joint_features,
        joint_state=base.joint_state,
        joint_mask=base.joint_mask,
        time_mask=base.time_mask,
        target_actions=base.target_actions,
        target_values=base.target_values,
        task_features=task_features,
    )


def _mse(model: P37Neuro, batch: BrainBatch) -> float:
    model.eval()
    with torch.no_grad():
        output = model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
            task_features=batch.task_features,
        )
        loss = imitation_loss(
            output,
            target_actions=batch.target_actions,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
        )
    return float(loss.action)


def _heldout_success_rate(
    model: P37Neuro,
    rows: tuple[ManipulationExample, ...],
    threshold: float = 0.04,
) -> float:
    trials: list[ManipulationTrial] = []
    for row in rows:
        loss = _mse(model, _batch((row,)))
        trials.append(
            ManipulationTrial(
                embodiment_id=row.example.embodiment.embodiment_id,
                task_id=row.example.episode.task_id,
                success=loss <= threshold,
                intervention_count=0,
                duration_s=float(len(row.example.episode.steps)) * 0.05,
            )
        )
    return transfer_metrics(tuple(trials))["success_rate"]


def run_e2_cpu_smoke(
    output_dir: str | Path,
    *,
    seed: int = 73,
    epochs: int = 60,
) -> E2SmokeResult:
    """Train manipulation conditioning on 3/4/5-DOF arms and hold out 6/7 DOF."""
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    torch.manual_seed(seed)

    train_joint_counts = (3, 4, 5)
    heldout_joint_counts = (6, 7)
    train_rows = _examples(seed, train_joint_counts, _task_vectors(1, 10))
    heldout_rows = _examples(seed + 1000, heldout_joint_counts, _task_vectors(31, 5))
    train_batch = _batch(train_rows)
    heldout_batch = _batch(heldout_rows)

    model = P37Neuro(
        NeuroConfig(
            model_dim=32,
            task_feature_dim=8,
            high_level_dim=8,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=8,
            dropout=0.0,
        )
    )
    trainer = BehaviorCloningTrainer(
        model,
        learning_rate=2e-3,
        weight_decay=0.0,
        max_gradient_norm=5.0,
    )

    initial_train = _mse(model, train_batch)
    initial_heldout = _mse(model, heldout_batch)
    for _ in range(epochs):
        trainer.step(train_batch)
    final_train = _mse(model, train_batch)
    final_heldout = _mse(model, heldout_batch)
    success_rate = _heldout_success_rate(model, heldout_rows)

    root = Path(output_dir)
    checkpoint_dir = root / "checkpoint"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "e2-manipulation-smoke",
            "seed": seed,
            "epochs": epochs,
            "capability_evidence": "false",
        },
    )
    result = E2SmokeResult(
        seed=seed,
        epochs=epochs,
        train_joint_counts=train_joint_counts,
        heldout_joint_counts=heldout_joint_counts,
        initial_train_action_mse=initial_train,
        final_train_action_mse=final_train,
        initial_heldout_action_mse=initial_heldout,
        final_heldout_action_mse=final_heldout,
        heldout_success_rate=success_rate,
        checkpoint_dir=str(checkpoint_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "metrics.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e2-manipulation-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e2-manipulation-smoke"))
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--epochs", type=int, default=60)
    args = parser.parse_args()
    result = run_e2_cpu_smoke(args.output, seed=args.seed, epochs=args.epochs)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
