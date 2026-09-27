"""Executable behavior-cloning experiment lifecycle."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import yaml
from p37_neuro.data.storage import read_episode
from p37_neuro.embodiment.importers import load_mjcf, load_urdf

from p37_neuro_ml.checkpoint import load_checkpoint, save_checkpoint
from p37_neuro_ml.dataset import EpisodeExample, collate_episodes
from p37_neuro_ml.losses import imitation_loss
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer


@dataclass(frozen=True, slots=True)
class TrainingSource:
    robot: Path
    episodes: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class BCExperimentConfig:
    seed: int
    epochs: int
    batch_size: int
    learning_rate: float
    weight_decay: float
    output_dir: Path
    device: str
    model: dict[str, Any]
    sources: tuple[TrainingSource, ...]

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.epochs <= 0 or self.batch_size <= 0:
            raise ValueError("epochs and batch_size must be positive")
        if self.learning_rate <= 0 or self.weight_decay < 0:
            raise ValueError("invalid optimizer configuration")
        if not self.sources:
            raise ValueError("at least one training source is required")


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    checkpoint_dir: Path
    examples: int
    epochs: int
    final_loss: float


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def load_experiment(path: str | Path) -> BCExperimentConfig:
    """Load a versioned YAML experiment manifest."""
    source = Path(path).resolve()
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("experiment manifest must be a mapping")
    if int(raw.get("schema_version", 0)) != 1:
        raise ValueError("unsupported experiment schema_version")

    root = source.parent
    source_rows = raw.get("sources")
    if not isinstance(source_rows, list) or not source_rows:
        raise ValueError("sources must be a non-empty list")

    sources: list[TrainingSource] = []
    for row in source_rows:
        if not isinstance(row, dict):
            raise ValueError("each source must be a mapping")
        episodes = row.get("episodes")
        if not isinstance(episodes, list) or not episodes:
            raise ValueError("source episodes must be a non-empty list")
        sources.append(
            TrainingSource(
                robot=_resolve(root, str(row["robot"])),
                episodes=tuple(_resolve(root, str(item)) for item in episodes),
            )
        )

    return BCExperimentConfig(
        seed=int(raw.get("seed", 0)),
        epochs=int(raw.get("epochs", 1)),
        batch_size=int(raw.get("batch_size", 8)),
        learning_rate=float(raw.get("learning_rate", 3e-4)),
        weight_decay=float(raw.get("weight_decay", 1e-4)),
        output_dir=_resolve(root, str(raw.get("output_dir", "runs/default"))),
        device=str(raw.get("device", "cpu")),
        model=dict(raw.get("model", {})),
        sources=tuple(sources),
    )


def _load_body(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".urdf":
        return load_urdf(path)
    if suffix in {".xml", ".mjcf"}:
        return load_mjcf(path)
    raise ValueError(f"unsupported robot description for training: {path}")


def load_examples(config: BCExperimentConfig) -> tuple[EpisodeExample, ...]:
    """Load and validate all canonical examples declared by a manifest."""
    examples: list[EpisodeExample] = []
    for source in config.sources:
        body = _load_body(source.robot)
        for episode_path in source.episodes:
            examples.append(EpisodeExample(read_episode(episode_path), body))
    return tuple(examples)


def _batch_indices(count: int, batch_size: int, *, seed: int) -> tuple[tuple[int, ...], ...]:
    indices = list(range(count))
    random.Random(seed).shuffle(indices)
    return tuple(
        tuple(indices[start : start + batch_size]) for start in range(0, len(indices), batch_size)
    )


def _device(name: str) -> torch.device:
    device = torch.device(name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return device


def train_behavior_cloning(config_path: str | Path) -> ExperimentResult:
    """Train a P37 checkpoint from canonical multi-embodiment episodes."""
    config = load_experiment(config_path)
    examples = load_examples(config)
    device = _device(config.device)

    random.seed(config.seed)
    torch.manual_seed(config.seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(config.seed)

    model = P37Neuro(NeuroConfig(**config.model)).to(device)
    trainer = BehaviorCloningTrainer(
        model,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    final_loss = float("nan")
    for epoch in range(config.epochs):
        for batch_ids in _batch_indices(
            len(examples),
            config.batch_size,
            seed=config.seed + epoch,
        ):
            batch = collate_episodes(
                tuple(examples[index] for index in batch_ids),
                device=device,
            )
            metrics = trainer.step(batch)
            final_loss = metrics.loss

    checkpoint_dir = config.output_dir / "final"
    save_checkpoint(
        checkpoint_dir,
        model,
        metadata={
            "seed": config.seed,
            "epochs": config.epochs,
            "examples": len(examples),
            "final_loss": final_loss,
        },
    )
    return ExperimentResult(checkpoint_dir, len(examples), config.epochs, final_loss)


def evaluate_checkpoint(
    config_path: str | Path,
    checkpoint_dir: str | Path,
) -> dict[str, float]:
    """Evaluate action/value imitation losses on the manifest dataset."""
    config = load_experiment(config_path)
    examples = load_examples(config)
    device = _device(config.device)
    model, _ = load_checkpoint(checkpoint_dir, map_location=str(device))
    model.to(device)
    model.eval()

    action_total = 0.0
    value_total = 0.0
    batches = 0
    with torch.no_grad():
        for batch_ids in _batch_indices(len(examples), config.batch_size, seed=config.seed):
            batch = collate_episodes(
                tuple(examples[index] for index in batch_ids),
                device=device,
            )
            output = model(
                joint_features=batch.joint_features,
                joint_state=batch.joint_state,
                joint_mask=batch.joint_mask,
                time_mask=batch.time_mask,
            )
            losses = imitation_loss(
                output,
                target_actions=batch.target_actions,
                target_values=batch.target_values,
                joint_mask=batch.joint_mask,
                time_mask=batch.time_mask,
            )
            action_total += float(losses.action)
            value_total += float(losses.value)
            batches += 1

    return {
        "action_mse": action_total / batches,
        "value_mse": value_total / batches,
        "examples": float(len(examples)),
    }
