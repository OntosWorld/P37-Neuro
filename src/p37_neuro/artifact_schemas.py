"""Access to versioned machine-readable P37 artifact schemas."""

from __future__ import annotations

import shutil
from importlib.resources import files
from pathlib import Path

_SCHEMA_FILES = {
    "qualification-report-v1": "qualification-report-v1.schema.json",
    "robot-manifest-v2": "robot-manifest-v2.schema.json",
    "rollout-plan-v1": "rollout-plan-v1.schema.json",
    "runtime-metrics-v1": "runtime-metrics-v1.schema.json",
}


def schema_names() -> tuple[str, ...]:
    return tuple(sorted(_SCHEMA_FILES))


def export_schemas(destination: str | Path) -> tuple[Path, ...]:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    root = files("p37_neuro").joinpath("schema_defs")
    written: list[Path] = []
    for name in schema_names():
        source = root.joinpath(_SCHEMA_FILES[name])
        output = target / _SCHEMA_FILES[name]
        with source.open("rb") as src, output.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        written.append(output)
    return tuple(written)
