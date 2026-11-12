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

from catalog import ROBOTS

ROOT = Path(__file__).resolve().parents[2]
STEEL = ROOT / "docs" / "interactive-lab" / "steel"


def assemble(output: Path, *, demo_evidence: Path | None = None) -> Path:
    """Assemble a self-contained WebGPU experience at the site root."""
    dist = STEEL / "dist"
    if not (dist / "index.html").is_file():
        raise FileNotFoundError("Build docs/interactive-lab/steel before publishing")
    output = output.resolve()
    if output in (ROOT, STEEL, dist) or ROOT not in output.parents:
        raise ValueError("Output must be a separate build folder inside repository")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(dist, output)
    # Do not ship the earlier procedural URDF arms or Panda workcell assets.
    # Every displayed robot now originates from a manufacturer-derived scene.
    for old_assets in ("robots", "vendor", "samples"):
        shutil.rmtree(output / old_assets, ignore_errors=True)
    # MuJoCo viewer is an internal runtime asset of this one-page application.
    # Users stay on /P37-Neuro/ while changing the 10 manufacturer models.
    simulator = ROOT / "sim" / "web" / "dist"
    if not (simulator / "manifest.json").is_file():
        raise FileNotFoundError("Build manufacturer-derived MuJoCo scenes first")
    shutil.copytree(simulator, output / "simulator")
    # Published measurements are recorded native policy experiments.
    # They are read-only evidence files, never browser policy artifacts.
    for name in ("p37-evidence.json", "p37-cross-body-evidence.json"):
        source = ROOT / "sim" / "web" / name
        payload = json.loads(source.read_text(encoding="utf-8"))
        if name == "p37-cross-body-evidence.json":
            if (
                payload.get("qualified_for_cross_body_task_transfer") is not False
                or payload.get("browser_policy_attached") is not False
                or payload.get("same_checkpoint_used_for_all_bodies") is not True
                or payload.get("parameters_retrained_for_go2") is not False
                or set(payload.get("bodies", {})) != {"unitree_g1", "unitree_go2"}
            ):
                raise RuntimeError("P37 cross-body evidence boundary mismatch")
        else:
            if (
                payload.get("qualification") != "unqualified"
                or payload.get("qualified_for_walking") is not False
            ):
                raise RuntimeError("P37 G1 policy evidence boundary mismatch")
        shutil.copyfile(source, output / name)
    catalog = {"robots": [robot.to_public() for robot in ROBOTS]}
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((output / "simulator" / "manifest.json").read_text(encoding="utf-8"))
    ids = {scene["id"] for project in manifest["projects"] for scene in project["scenes"]}
    required = {robot.id for robot in ROBOTS}
    if not required <= ids:
        raise RuntimeError(f"MuJoCo robot scenes missing: {sorted(required - ids)}")
    policy_bodies = ("unitree_g1", "unitree_go2")
    for robot in policy_bodies:
        scene_id = robot + "_p37_experimental"
        matched = [
            scene for project in manifest["projects"]
            for scene in project["scenes"] if scene["id"] == scene_id
        ]
        if len(matched) != 1:
            raise RuntimeError(f"Live P37 experimental scene missing: {scene_id}")
        policies = matched[0].get("policies", [])
        if not any(
            p.get("id") == "p37_experimental_recurrent_ppo" for p in policies
        ):
            raise RuntimeError(f"Verified ONNX policy not attached to {scene_id}")
    metadata = {
        "schema_version": 1,
        "site_entry": "/P37-Neuro/",
        "experience": "single-root-native-mujoco-p37",
        "physics_engine": "MuJoCo WebAssembly",
        "controllers": "real-onnx-recurrent-p37-experimental-or-passive",
        "manufacturer_robots": sorted(robot.id for robot in ROBOTS),
        "panda_loader": "native-MuJoCo-Menagerie-scene",
        "trained_p37_policy_attached": True,
        "active_policy_robots": list(policy_bodies),
        "model_only_robots": sorted(required),
        "onnx_sha256": "894d33ac78e0d654b00cf85319b5dcf4accf1d0c93b1264b4e40f105670905e3",
        "qualified_cross_body_transfer": False,
        "notes": (
            "G1 and Go2 have an experimental recurrent P37 ONNX policy in browser. "
            "Unqualified for walking or task transfer. Other scenes are passive."
        ),
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
