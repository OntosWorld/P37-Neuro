"""Integrity-checked model checkpoint persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import torch

from p37_neuro_ml.model import NeuroConfig, P37Neuro


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_checkpoint(
    directory: str | Path,
    model: P37Neuro,
    *,
    metadata: dict[str, str | int | float] | None = None,
) -> str:
    """Save weights plus a JSON manifest and return the weights digest."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    weights = root / "model.pt"
    temporary = root / "model.pt.tmp"
    torch.save(model.state_dict(), temporary)
    temporary.replace(weights)
    digest = _sha256(weights)
    manifest = {
        "schema_version": 1,
        "sha256": digest,
        "config": asdict(model.config),
        "metadata": metadata or {},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return digest


def load_checkpoint(
    directory: str | Path, *, map_location: str = "cpu"
) -> tuple[P37Neuro, dict[str, Any]]:
    """Verify and load a checkpoint directory."""
    root = Path(directory)
    manifest: dict[str, Any] = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    weights = root / "model.pt"
    actual = _sha256(weights)
    if actual != manifest["sha256"]:
        raise ValueError("checkpoint integrity verification failed")
    model = P37Neuro(NeuroConfig(**manifest["config"]))
    state = torch.load(weights, map_location=map_location, weights_only=True)
    model.load_state_dict(state)
    return model, manifest
