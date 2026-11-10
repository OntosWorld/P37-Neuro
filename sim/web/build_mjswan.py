"""Build the P37 browser physics viewer from actual MuJoCo Menagerie models.

Generate a self-contained mjswan site. No trained P37 policy is bundled.
Run from the repository root:
  python sim/web/build_mjswan.py --menagerie /path/to/mujoco_menagerie
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import mjswan
import mujoco

ROOT = Path(__file__).resolve().parent
ROBOTS = (
    ("Unitree G1", "unitree_g1", "scene.xml", (0.0, 0.0, 0.85), 3.5),
    ("Unitree Go2", "unitree_go2", "scene.xml", (0.0, 0.0, 0.40), 2.8),
    ("Franka Panda", "franka_emika_panda", "scene.xml", (0.0, 0.0, 0.45), 2.1),
)


def build(menagerie: Path, base_path: str = "/simulator/") -> Path:
    menagerie = menagerie.resolve()
    if not menagerie.is_dir():
        raise FileNotFoundError(f"MuJoCo Menagerie checkout missing: {menagerie}")
    if not base_path.startswith("/") or not base_path.endswith("/"):
        raise ValueError("base_path must begin and end with '/'")

    builder = mjswan.Builder(
        base_path=base_path,
        license="Apache-2.0",
        copyright="2026 Ontos",
    )
    project = builder.add_project(name="P37 Robot Models", default=True)
    project.set_notice(
        "These are third-party robot simulation models from MuJoCo Menagerie. "
        "Physics and model exploration are not evidence of a trained P37 policy. "
        "Check scene credits and original model licenses before redistribution."
    )

    for name, directory, filename, lookat, distance in ROBOTS:
        path = menagerie / directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing robot scene: {path}")
        spec = mujoco.MjSpec.from_file(str(path))
        scene = project.add_scene(spec=spec, name=name)
        scene.set_viewer(
            mjswan.ViewerConfig(
                lookat=lookat,
                distance=distance,
                elevation=-20.0,
                azimuth=-135.0,
                origin_type=mjswan.ViewerConfig.OriginType.WORLD,
            )
        )

    old_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        builder.build()
    finally:
        os.chdir(old_cwd)

    output = ROOT / "dist"
    manifest = output / "manifest.json"
    if not manifest.is_file():
        raise RuntimeError(f"mjswan build produced no manifest at {manifest}")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if not metadata.get("projects"):
        raise RuntimeError("mjswan manifest contains no projects")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--base-path", default="/simulator/")
    args = parser.parse_args()
    print(build(args.menagerie, args.base_path))


if __name__ == "__main__":
    main()
