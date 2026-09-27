"""CPU-only E1 cross-morphology training smoke experiment.

This experiment is intentionally small enough for normal CI. It proves that one
P37 checkpoint can be optimized over heterogeneous joint counts and evaluated on
held-out morphologies. It is not a capability benchmark and must not be reported
as evidence of general robot intelligence.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from math import cos, sin
from pathlib import Path

import torch
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.simulation.morphology import MorphologyRange, generate_morphology

from p37_neuro_ml.checkpoint import save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.losses import imitation_loss
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer


@dataclass(frozen=True, slots=True)
class E1SmokeResult:
    seed: int
    epochs: int
    train_bodies: int
    heldout_bodies: int
    train_joint_counts: tuple[int, ...]
    heldout_joint_counts: tuple[int, ...]
    initial_train_action_mse: float
    final_train_action_mse: float
    initial_heldout_action_mse: float
    final_heldout_action_mse: float
    checkpoint_dir: str


def _body(seed: int, joints: int):
    return generate_morphology(
        seed,
        MorphologyRange(min_joints=joints, max_joints=joints),
    )


def _episode(body, *, episode_seed: int, steps: int = 8) -> Episode:
    rows: list[EpisodeStep] = []
    for step in range(steps):
        positions: dict[str, float] = {}
        velocities: dict[str, float] = {}
        commands: dict[str, float] = {}

        for joint_index, joint in enumerate(body.joints):
            assert joint.position is not None
            midpoint = (joint.position.minimum + joint.position.maximum) / 2.0
            half_range = (joint.position.maximum - joint.position.minimum) / 2.0
            phase = 0.37 * episode_seed + 0.23 * joint_index
            angle = 0.5 * step + phase
            position_norm = 0.65 * sin(angle)
            velocity_norm = 0.35 * cos(angle)
            target_norm = max(-0.9, min(0.9, -0.7 * position_norm - 0.2 * velocity_norm))

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
                reward=1.0 - 0.02 * step,
                terminal=step == steps - 1,
            )
        )

    return Episode(
        episode_id=f"{body.embodiment_id}-episode-{episode_seed}",
        embodiment_id=body.embodiment_id,
        task_id="synthetic-stabilize",
        steps=tuple(rows),
        source="p37-e1-cpu-smoke",
        metadata={"capability_evidence": "false"},
    )


def _examples(seed: int, joint_counts: tuple[int, ...]) -> tuple[EpisodeExample, ...]:
    examples: list[EpisodeExample] = []
    for index, joints in enumerate(joint_counts):
        body = _body(seed + index * 17, joints)
        for episode_index in range(2):
            examples.append(
                EpisodeExample(
                    _episode(body, episode_seed=seed + index * 31 + episode_index),
                    body,
                )
            )
    return tuple(examples)


def _action_mse(model: P37Neuro, examples: tuple[EpisodeExample, ...]) -> float:
    batch = collate_episodes(examples)
    model.eval()
    with torch.no_grad():
        output = model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
        )
        losses = imitation_loss(
            output,
            target_actions=batch.target_actions,
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask,
        )
    return float(losses.action)


def run_e1_cpu_smoke(
    output_dir: str | Path,
    *,
    seed: int = 37,
    epochs: int = 40,
) -> E1SmokeResult:
    """Train on four morphologies and evaluate two completely held-out bodies."""
    if epochs <= 0:
        raise ValueError("epochs must be positive")

    torch.manual_seed(seed)
    train_joint_counts = (2, 3, 4, 5)
    heldout_joint_counts = (6, 7)
    train_examples = _examples(seed, train_joint_counts)
    heldout_examples = _examples(seed + 1000, heldout_joint_counts)

    model = P37Neuro(
        NeuroConfig(
            model_dim=32,
            task_feature_dim=16,
            high_level_dim=8,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=16,
            dropout=0.0,
        )
    )
    trainer = BehaviorCloningTrainer(
        model,
        learning_rate=2e-3,
        weight_decay=0.0,
        max_gradient_norm=5.0,
    )
    train_batch = collate_episodes(train_examples)

    initial_train = _action_mse(model, train_examples)
    initial_heldout = _action_mse(model, heldout_examples)
    for _ in range(epochs):
        trainer.step(train_batch)

    final_train = _action_mse(model, train_examples)
    final_heldout = _action_mse(model, heldout_examples)

    root = Path(output_dir)
    checkpoint_dir = root / "checkpoint"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "e1-cpu-smoke",
            "seed": seed,
            "epochs": epochs,
            "capability_evidence": "false",
            "heldout_body_count": len(heldout_joint_counts),
        },
    )
    result = E1SmokeResult(
        seed=seed,
        epochs=epochs,
        train_bodies=len(train_joint_counts),
        heldout_bodies=len(heldout_joint_counts),
        train_joint_counts=train_joint_counts,
        heldout_joint_counts=heldout_joint_counts,
        initial_train_action_mse=initial_train,
        final_train_action_mse=final_train,
        initial_heldout_action_mse=initial_heldout,
        final_heldout_action_mse=final_heldout,
        checkpoint_dir=str(checkpoint_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "metrics.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e1-cpu-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e1-cpu-smoke"))
    parser.add_argument("--seed", type=int, default=37)
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()

    result = run_e1_cpu_smoke(args.output, seed=args.seed, epochs=args.epochs)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
