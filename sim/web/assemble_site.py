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
    """Assemble a self-contained native MuJoCo experience at the site root."""
    dist = STEEL / "dist"
    if not (dist / "index.html").is_file():
        raise FileNotFoundError("Build docs/interactive-lab/steel before publishing")
    output = output.resolve()
    if output in (ROOT, STEEL, dist) or ROOT not in output.parents:
        raise ValueError("Output must be a separate build folder inside repository")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(dist, output)
    # Keep only native, manufacturer-derived robot geometry in the published
    # website. The former Steel reference URDFs / unused assets are excluded.
    for legacy in ("robots", "vendor"):
        unused = output / legacy
        if unused.is_dir():
            shutil.rmtree(unused)
    # MuJoCo viewer is an internal runtime asset of this one-page application.
    # Users stay on /P37-Neuro/ while changing the 10 manufacturer models.
    simulator = ROOT / "sim" / "web" / "dist"
    if not (simulator / "manifest.json").is_file():
        raise FileNotFoundError("Build manufacturer-derived MuJoCo scenes first")
    shutil.copytree(simulator, output / "simulator")
    # Source-attributed MimicGen episodes are published as recorded DATA,
    # not driven through an unrelated physical robot controller.
    recorded = ROOT / "docs" / "interactive-lab" / "compare"
    sample = recorded / "samples" / "mimicgen-square-source.json"
    if not (recorded / "index.html").is_file() or not sample.is_file():
        raise FileNotFoundError("Verified source recording viewer is unavailable")
    publication = json.loads(sample.read_text(encoding="utf-8")).get("publication", {})
    if (
        publication.get("source") != "amandlek/mimicgen_datasets"
        or publication.get("learned_policy_attached") is not False
    ):
        raise RuntimeError("Recorded task data failed source/learning integrity checks")
    shutil.copytree(recorded, output / "recorded")
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
    motions = json.loads(
        (output / "simulator" / "motion_data" / "index.json").read_text(encoding="utf-8")
    )
    if motions.get("kind") != "p37_model_derived_motions":
        raise RuntimeError("Expected real model-derived per-robot motion datasets")
    for robot in ROBOTS:
        clips = motions.get("motions", {}).get(robot.id, [])
        if {clip.get("id") for clip in clips} != {"articulation", "motion_cycle", "hold"}:
            raise RuntimeError(f"Missing movement clips for {robot.id}")
        scene = next(
            scene
            for project in manifest["projects"]
            for scene in project["scenes"]
            if scene["id"] == robot.id
        )
        policy_ids = {policy.get("id") for policy in scene.get("policies", [])}
        if not {"motor_articulation", "movement_cycle", "hold_position"} <= policy_ids:
            raise RuntimeError(f"Motion playback not physically attached to {robot.id}")
        for clip in clips:
            if clip["is_learned_p37_policy"] or clip["is_qualified_locomotion"]:
                raise RuntimeError("Motion dataset cannot be mislabeled as P37 intelligence")
            if not (output / "simulator" / "motion_data" / clip["dataset_file"]).is_file():
                raise FileNotFoundError(f"Missing actual trajectory for {robot.id}")
    g1_scene = next(
        scene
        for project in manifest["projects"]
        for scene in project["scenes"]
        if scene["id"] == "unitree_g1"
    )
    g1_policies = g1_scene.get("policies", [])
    if not g1_policies:
        raise RuntimeError("Native G1 scene has no compiled P37 browser controller")
    if not any("p37" in json.dumps(policy).lower() for policy in g1_policies):
        raise RuntimeError("The actual P37 learned policy is not registered in native G1")
    cross = json.loads((output / "p37-cross-body-evidence.json").read_text(encoding="utf-8"))
    metadata = {
        "schema_version": 1,
        "site_entry": "/P37-Neuro/",
        "experience": "native-real-robot-P37-browser-policy",
        "physics_engine": "MuJoCo WebAssembly",
        "controllers": "experimental-P37-recurrent-ONNX-G1; passive-physics-other-bodies",
        "manufacturer_robots": sorted(robot.id for robot in ROBOTS),
        "motion_dataset_source": "MuJoCo Menagerie model-derived actuator targets",
        "motion_dataset_modes_per_robot": 3,
        "all_robot_motion_playback": True,
        "physical_task_scene_version": 2,
        "task_experiences": [
            "live_assisted_physics",
            "source_recorded_replay",
            "experimental_p37_policy",
        ],
        "recorded_task_source": "amandlek/mimicgen_datasets; CC BY 4.0",
        "panda_loader": "native-MuJoCo-Menagerie-scene",
        "trained_p37_policy_attached": True,
        "experimental_policy_robot": "unitree_g1",
        "p37_checkpoint_sha256": cross["checkpoint_sha256"],
        "qualified_cross_body_transfer": False,
        "notes": (
            "G1 runs real experimental P37 ONNX inference in native MuJoCo. "
            "All bodies have model-derived motion playback; these are not learned skills. "
            "P37 locomotion, recovery and cross-body transfer are unqualified."
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
