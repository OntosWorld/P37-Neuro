"""Publish one canonical public P37-Neuro experience.

GitHub Pages exposes the live Steel workcell at /P37-Neuro/. Previous demos,
labs, and test routes are intentionally not published; evidence and controls
are integrated into the workcell instead of multiplying public URLs.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEEL = ROOT / "docs" / "interactive-lab" / "steel"


def assemble(output: Path, *, demo_evidence: Path | None = None) -> Path:
    """Assemble a self-contained WebGPU experience at the site root."""
    dist = STEEL / "dist"
    if not (dist / "index.html").is_file():
        raise FileNotFoundError("Build docs/interactive-lab/steel before publishing")
    if not (dist / "robots" / "compact.urdf").is_file():
        raise FileNotFoundError("Physical reference robot missing from Steel assets")
    output = output.resolve()
    if output in (ROOT, STEEL, dist) or ROOT not in output.parents:
        raise ValueError("Output must be a separate build folder inside repository")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(dist, output)
    metadata = {
        "schema_version": 1,
        "site_entry": "/P37-Neuro/",
        "experience": "single-root-steel-webgpu",
        "physics_engine": "Steel WebGPU",
        "controllers": "deterministic-reference",
        "trained_p37_policy_attached": False,
        "qualified_cross_body_transfer": False,
        "notes": "Measured tabletop contact and reference motions are not learned-policy qualifications",
    }
    (output / "build-info.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # demo_evidence remains an accepted CLI argument for older build callers.
    # It is deliberately not exposed as a separate public page.
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "_pages")
    parser.add_argument("--demo-evidence", type=Path)
    args = parser.parse_args()
    print(assemble(args.output, demo_evidence=args.demo_evidence))


if __name__ == "__main__":
    main()
