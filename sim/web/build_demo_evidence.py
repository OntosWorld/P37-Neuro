"""Produce source-verified P37 demo metadata from the real MuJoCo robot models.

This is a physics/architecture demo, not a trained cross-embodiment benchmark.
The source experiments are preserved unmodified with explicit limitations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mujoco
from catalog import ROBOTS

ROOT = Path(__file__).resolve().parent


def build_evidence(menagerie: Path, forces: Path, output: Path) -> Path:
    if not forces.is_file():
        raise FileNotFoundError(f"Measured disturbance evidence unavailable: {forces}")
    force_data = json.loads(forces.read_text(encoding="utf-8"))
    p37 = json.loads((ROOT / "p37-evidence.json").read_text(encoding="utf-8"))
    if p37["qualification"] != "unqualified" or p37["qualified_for_walking"] is not False:
        raise ValueError("Unexpected public P37 policy qualification state")

    bodies = {}
    for robot in ROBOTS:
        model_file = menagerie / robot.model / "scene.xml"
        model = mujoco.MjModel.from_xml_path(str(model_file.resolve()))
        bodies[robot.id] = {
            "id": robot.id,
            "name": robot.name,
            "kind": robot.kind,
            "joints": int(model.njnt),
            "actuators": int(model.nu),
            "bodies": int(model.nbody),
            "position_coordinates": int(model.nq),
            "velocity_coordinates": int(model.nv),
            "source": "google-deepmind/mujoco_menagerie",
            "model_path": f"{robot.model}/scene.xml",
            "controller": "model_only",
            "neural_policy_qualified": False,
        }

    force_trials = {}
    for robot_id, force_n in (("unitree_g1", 90.0), ("unitree_go2", 40.0)):
        trial = force_data.get(robot_id)
        if (
            trial is None
            or trial["force_newtons"] != force_n
            or trial["repeat_deterministic"] is not True
            or trial["controller"] != "none"
            or trial["p37_recovery_claimed"] is not False
            or not trial["displacement_vs_control_m"] > 0
        ):
            raise ValueError(f"Invalid or missing measured force trial: {robot_id}")
        force_trials[robot_id] = {
            "force_newtons": trial["force_newtons"],
            "displacement_vs_control_m": trial["displacement_vs_control_m"],
            "push_start_s": trial["push_start_s"],
            "push_end_s": trial["push_end_s"],
            "duration_s": trial["pushed"]["simulated_seconds"],
            "repeat_deterministic": True,
            "controller": "none",
            "scope": "native MuJoCo disturbance-versus-control experiment",
        }

    if len(p37["evaluation"]["seeds"]) != 3:
        raise ValueError("Expected three evidenced P37 G1 policy smoke trials")
    result = {
        "schema_version": 1,
        "title": "P37 Brain Lab — reproducible experiment data",
        "simulation_engine": "MuJoCo",
        "bodies": bodies,
        "force_trials": force_trials,
        "p37_g1": {
            "model": p37["model"],
            "robot": p37["robot"],
            "training_updates": p37["training_updates"],
            "qualification": p37["qualification"],
            "qualified_for_walking": False,
            "browser_policy_attached": False,
            "evaluation": p37["evaluation"],
            "onnx": p37["onnx"],
            "provenance": p37["provenance"],
        },
        "cross_embodiment": {
            "status": "not_yet_qualified",
            "same_checkpoint_control_verified_on_two_bodies": False,
            "different_models_share_a_physics_browser": True,
            "scope": (
                "Ten physical robot scene contracts and a side-by-side viewer. "
                "No trained P37 policy transfer is claimed."
            ),
            "required_evidence": (
                "Identical P37 checkpoint evaluated on at least two materially different "
                "robot embodiments with actuator mapping, fixed seeds, "
                "task success criteria, baselines, and published failures."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menagerie", type=Path, required=True)
    parser.add_argument("--forces", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_evidence(args.menagerie, args.forces, args.output))


if __name__ == "__main__":
    main()
