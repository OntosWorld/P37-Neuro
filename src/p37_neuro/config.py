"""Versioned configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Raised when a P37 configuration is invalid."""


@dataclass(frozen=True, slots=True)
class P37Config:
    """Validated top-level experiment/runtime configuration."""

    schema_version: int
    project: str
    seed: int
    embodiment: str
    mode: str
    parameters: dict[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ConfigurationError(f"unsupported schema_version: {self.schema_version}")
        if not self.project.strip():
            raise ConfigurationError("project cannot be empty")
        if self.seed < 0:
            raise ConfigurationError("seed must be non-negative")
        if not self.embodiment.strip():
            raise ConfigurationError("embodiment cannot be empty")
        if self.mode not in {"train", "evaluate", "deploy", "replay"}:
            raise ConfigurationError(f"unsupported mode: {self.mode}")


def load_config(path: str | Path) -> P37Config:
    """Load JSON or YAML into a strict P37Config."""
    source = Path(path)
    if not source.is_file():
        raise ConfigurationError(f"configuration does not exist: {source}")

    suffix = source.suffix.lower()
    text = source.read_text(encoding="utf-8")
    if suffix == ".json":
        raw = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    else:
        raise ConfigurationError(f"unsupported configuration format: {suffix}")

    if not isinstance(raw, dict):
        raise ConfigurationError("top-level configuration must be a mapping")

    required = {"schema_version", "project", "seed", "embodiment", "mode"}
    missing = sorted(required - raw.keys())
    if missing:
        raise ConfigurationError(f"missing required keys: {missing}")

    parameters = raw.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ConfigurationError("parameters must be a mapping")

    return P37Config(
        schema_version=int(raw["schema_version"]),
        project=str(raw["project"]),
        seed=int(raw["seed"]),
        embodiment=str(raw["embodiment"]),
        mode=str(raw["mode"]),
        parameters=parameters,
    )
