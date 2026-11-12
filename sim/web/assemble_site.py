"""Assemble the production P37 Brain Lab from genuine compiled MuJoCo scenes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from catalog import ROBOTS

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
LAB = REPOSITORY / "docs" / "interactive-lab"


def add_interactive_lab(output: Path) -> None:
    """Publish additive research pages, never replacing the Brain Lab root."""
    if not LAB.is_dir():
        raise FileNotFoundError("missing cross-embodiment lab source directory")
    steel_dist = LAB / "steel" / "dist"
    if not (steel_dist / "index.html").is_file():
        raise FileNotFoundError("Build the Steel WebGPU app before assembling the public site")
    lab = output / "lab"
    lab.mkdir(parents=True, exist_ok=True)
    for rel in ("index.html", "sim/index.html", "compare/index.html"):
        source = LAB / rel
        if not source.is_file():
            raise FileNotFoundError(f"missing lab page: {rel}")
        destination = lab / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    source_samples = LAB / "compare" / "samples"
    if not (source_samples / "mimicgen-square-source.json").is_file():
        raise FileNotFoundError("missing authenticated MimicGen replay artifact")
    shutil.copytree(source_samples, lab / "compare" / "samples")
    shutil.copytree(steel_dist, lab / "steel")
    public_test = LAB / "public-test" / "index.html"
    if not public_test.is_file():
        raise FileNotFoundError("missing public test entrypoint")
    test_dir = output / "test"
    test_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(public_test, test_dir / "index.html")
    # Both public demonstrations and the original robot library stay available.
    for rel in (
        "index.html",
        "sim/index.html",
        "compare/index.html",
        "compare/samples/mimicgen-square-source.json",
        "steel/index.html",
        "../test/index.html",
        "steel/samples/mimicgen-square-source.json",
    ):
        if not (lab / rel).is_file():
            raise ValueError(f"incomplete assembled lab: {rel}")


def assemble(output: Path, *, demo_evidence: Path | None = None) -> Path:
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
    for file_name in (
        "index.html",
        "studio.css",
        "studio-minimal.css",
        "studio.js",
        "p37-evidence.json",
    ):
        shutil.copy2(ROOT / file_name, output / file_name)
    catalog = {
        "schema_version": 2,
        "origin": "Google DeepMind MuJoCo Menagerie",
        "engine": "mjswan / MuJoCo WASM",
        "controller_status": "model_only",
        "robots": [robot.to_public() for robot in ROBOTS],
    }
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    # A dedicated demo gallery keeps capability claims outside the live model viewer.
    demos = output / "demos"
    demos.mkdir()
    for name in ("index.html", "demos.css", "demos.js"):
        shutil.copy2(ROOT / "demos" / name, demos / name)
    if demo_evidence is not None:
        evidence = json.loads(demo_evidence.read_text(encoding="utf-8"))
        if (
            evidence.get("schema_version") != 1
            or set(evidence.get("bodies", {})) != expected
            or evidence.get("cross_embodiment", {}).get("same_checkpoint_task_transfer_qualified")
            is not False
            or evidence.get("p37_g1", {}).get("qualified_for_walking") is not False
            or evidence.get("cross_body_p37", {}).get("qualified_for_cross_body_task_transfer")
            is not False
        ):
            raise ValueError("Demo experiment data is incomplete or overclaims capability")
        shutil.copy2(demo_evidence, demos / "evidence.json")
    shutil.copytree(viewer, output / "simulator")
    add_interactive_lab(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    parser.add_argument("--demo-evidence", type=Path)
    args = parser.parse_args()
    print(assemble(args.output, demo_evidence=args.demo_evidence))


if __name__ == "__main__":
    main()
