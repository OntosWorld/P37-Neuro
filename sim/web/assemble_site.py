"""Assemble the public static P37 Brain Lab site after mjswan asset compilation."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def assemble(output: Path) -> Path:
    viewer = ROOT / "dist"
    if not (viewer / "index.html").is_file():
        raise FileNotFoundError("Run build_mjswan.py before assembling the public site")
    manifest_path = viewer / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    projects = manifest.get("projects", [])
    if not isinstance(projects, list) or not projects:
        raise ValueError("mjswan build has no projects")
    expected = {"unitree_g1", "unitree_go2", "franka_panda"}
    scenes = {
        scene.get("id")
        for project in projects
        if isinstance(project, dict)
        for scene in project.get("scenes", [])
        if isinstance(scene, dict)
    }
    if not expected.issubset(scenes):
        raise ValueError(f"missing generated physical robot models: {sorted(expected - scenes)}")
    output = output.resolve()
    if output in (ROOT, viewer):
        raise ValueError("output must be separate from source and mjswan dist")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copy2(ROOT / "index.html", output / "index.html")
    shutil.copytree(viewer, output / "simulator")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    print(assemble(args.output))


if __name__ == "__main__":
    main()
