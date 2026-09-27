"""CPU-only E4 long-horizon recovery-memory smoke experiment."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.simulation.morphology import MorphologyRange, generate_morphology

from p37_neuro_ml.checkpoint import save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.model import NeuroConfig, P37Neuro


@dataclass(frozen=True, slots=True)
class E4SmokeResult:
    seed: int
    epochs: int
    train_joint_counts: tuple[int, ...]
    heldout_joint_count: int
    recovery_mse_with_memory: float
    recovery_mse_after_memory_reset: float
    memory_advantage: float
    checkpoint_dir: str


def _body(seed: int, joints: int):
    return generate_morphology(
        seed,
        MorphologyRange(min_joints=joints, max_joints=joints),
    )


def _episode(body, cue: int, variant: int) -> Episode:
    if cue not in {-1, 1}:
        raise ValueError("cue must be -1 or 1")

    steps: list[EpisodeStep] = []
    for step in range(8):
        positions = {joint.name: 0.0 for joint in body.joints}
        velocities = {joint.name: 0.0 for joint in body.joints}

        if step == 0:
            for joint in body.joints:
                assert joint.position is not None
                positions[joint.name] = cue * 0.55 * joint.position.maximum
        if step == 4:
            velocities[body.joints[0].name] = 0.5

        commands: dict[str, float] = {}
        for joint_index, joint in enumerate(body.joints):
            assert joint.position is not None
            midpoint = (joint.position.minimum + joint.position.maximum) / 2.0
            half_range = (joint.position.maximum - joint.position.minimum) / 2.0
            recovery_pattern = 0.65 - 0.06 * (joint_index % 3)
            target_norm = cue * recovery_pattern if step >= 5 else 0.0
            commands[joint.name] = midpoint + target_norm * half_range

        steps.append(
            EpisodeStep(
                observation=Observation(
                    timestamp_s=step * 0.1,
                    joint_position=positions,
                    joint_velocity=velocities,
                ),
                action=Action(
                    timestamp_s=step * 0.1,
                    joint_commands=commands,
                ),
                reward=1.0 if step >= 5 else 0.1,
                terminal=step == 7,
                failure_code="simulated_disturbance" if step == 4 else None,
            )
        )

    return Episode(
        episode_id=f"{body.embodiment_id}-recovery-{cue}-{variant}",
        embodiment_id=body.embodiment_id,
        task_id=f"recover-after-disturbance-{cue}",
        steps=tuple(steps),
        source="p37-e4-cpu-smoke",
        metadata={"capability_evidence": "false", "memory_required": "true"},
    )


def _examples(seed: int, joint_counts: tuple[int, ...]) -> tuple[EpisodeExample, ...]:
    rows: list[EpisodeExample] = []
    for body_index, joints in enumerate(joint_counts):
        body = _body(seed + body_index * 313, joints)
        for cue in (-1, 1):
            for variant in range(3):
                rows.append(EpisodeExample(_episode(body, cue, variant), body))
    return tuple(rows)


def _recovery_mse(
    model: P37Neuro,
    examples: tuple[EpisodeExample, ...],
    *,
    preserve_memory: bool,
) -> float:
    batch = collate_episodes(examples)
    model.eval()
    with torch.no_grad():
        first = model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state[:, :4],
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask[:, :4],
        )
        second = model(
            joint_features=batch.joint_features,
            joint_state=batch.joint_state[:, 4:],
            joint_mask=batch.joint_mask,
            time_mask=batch.time_mask[:, 4:],
            memory=first.memory if preserve_memory else None,
        )

    prediction = second.action_mean[:, 1:, :]
    target = batch.target_actions[:, 5:, :]
    valid = batch.joint_mask[:, None, :].expand_as(target)
    squared = (prediction - target).square().masked_fill(~valid, 0.0)
    return float(squared.sum() / valid.sum().clamp_min(1))


def run_e4_recovery_smoke(
    output_dir: str | Path,
    *,
    seed: int = 151,
    epochs: int = 200,
) -> E4SmokeResult:
    """Train recovery memory and compare preserved-memory vs reset inference."""
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    torch.manual_seed(seed)

    train_joint_counts = (3, 4, 5)
    heldout_joint_count = 6
    train_examples = _examples(seed, train_joint_counts)
    heldout_examples = _examples(seed + 2000, (heldout_joint_count,))
    train_batch = collate_episodes(train_examples)

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
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.0)
    recovery_mask = train_batch.joint_mask[:, None, :].expand_as(
        train_batch.target_actions[:, 5:, :]
    )
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        output = model(
            joint_features=train_batch.joint_features,
            joint_state=train_batch.joint_state,
            joint_mask=train_batch.joint_mask,
            time_mask=train_batch.time_mask,
        )
        error = (
            output.action_mean[:, 5:, :] - train_batch.target_actions[:, 5:, :]
        ).square()
        loss = error.masked_fill(~recovery_mask, 0.0).sum() / recovery_mask.sum().clamp_min(1)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()

    with_memory = _recovery_mse(model, heldout_examples, preserve_memory=True)
    reset_memory = _recovery_mse(model, heldout_examples, preserve_memory=False)

    root = Path(output_dir)
    checkpoint_dir = root / "checkpoint"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "experiment": "e4-recovery-smoke",
            "seed": seed,
            "epochs": epochs,
            "capability_evidence": "false",
        },
    )
    result = E4SmokeResult(
        seed=seed,
        epochs=epochs,
        train_joint_counts=train_joint_counts,
        heldout_joint_count=heldout_joint_count,
        recovery_mse_with_memory=with_memory,
        recovery_mse_after_memory_reset=reset_memory,
        memory_advantage=reset_memory - with_memory,
        checkpoint_dir=str(checkpoint_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    (root / "metrics.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e4-recovery-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e4-recovery-smoke"))
    parser.add_argument("--seed", type=int, default=151)
    parser.add_argument("--epochs", type=int, default=200)
    args = parser.parse_args()
    result = run_e4_recovery_smoke(args.output, seed=args.seed, epochs=args.epochs)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
