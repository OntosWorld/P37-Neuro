"""Assemble the production P37 Brain Lab from genuine compiled MuJoCo scenes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from catalog import ROBOTS

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
    expected = {robot.id for robot in ROBOTS}
    scenes = {
        scene.get("id")
        for project in projects
        if isinstance(project, dict)
        for scene in project.get("scenes", [])
        if isinstance(scene, dict)
    }
    if not expected.issubset(scenes):
        raise ValueError(f"missing robot physics scenes: {sorted(expected - scenes)}")

    output = output.resolve()
    if output in (ROOT, viewer):
        raise ValueError("output must be separate from source and simulator dist")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for file_name in ("index.html", "studio.css", "studio-minimal.css", "studio.js", "p37-evidence.json"):
        shutil.copy2(ROOT / file_name, output / file_name)
    catalog = {
        "schema_version": 2,
        "origin": "Google DeepMind MuJoCo Menagerie",
        "engine": "mjswan / MuJoCo WASM",
        "controller_status": "model_only",
        "robots": [robot.to_public() for robot in ROBOTS],
    }
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    shutil.copytree(viewer, output / "simulator")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    print(assemble(args.output))


if __name__ == "__main__":
    main()
