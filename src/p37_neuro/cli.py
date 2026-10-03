"""Developer-facing CLI for validation and repository operations."""

from __future__ import annotations

import argparse
from pathlib import Path

from p37_neuro import __version__\nfrom p37_neuro.deployment import (\n    DeploymentTarget,\n    RolloutPlan,\n    build_rollback_plan,\n    load_rollout_plan,\n    write_rollout_plan,\n)\nfrom p37_neuro.config import load_config
from p37_neuro.data.storage import read_episode
from p37_neuro.embodiment.importers import load_mjcf, load_urdf
from p37_neuro.integration import create_robot_manifest_template, validate_robot_integration\nfrom p37_neuro.qualification import (\n    build_qualification_report,\n    load_qualification_evidence,\n    write_qualification_report,\n)\n

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="p37-neuro")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="print package and program information")

    config = subparsers.add_parser("validate-config", help="validate a P37 YAML/JSON config")
    config.add_argument("path", type=Path)

    robot = subparsers.add_parser("validate-robot", help="normalize and validate URDF/MJCF")
    robot.add_argument("path", type=Path)

    replay = subparsers.add_parser("inspect-episode", help="verify and summarize an episode")
    replay.add_argument("path", type=Path)

    robot_group = subparsers.add_parser("robot", help="create and validate robot integrations")
    robot_commands = robot_group.add_subparsers(dest="robot_command", required=True)
    robot_init = robot_commands.add_parser("init", help="create a robot integration manifest")
    robot_init.add_argument("name")
    robot_init.add_argument("--output", type=Path, default=Path("robots"))
    robot_validate = robot_commands.add_parser("validate", help="validate a robot integration")
    robot_validate.add_argument("path", type=Path)\n\n    qualify = subparsers.add_parser("qualify", help="generate a release qualification report")\n    qualify.add_argument("--evidence", type=Path, required=True)\n    qualify.add_argument("--robot", type=Path)\n    qualify.add_argument("--output", type=Path, default=Path("artifacts/qualification"))\n    return parser\n

def main() -> None:
    """Run the P37 Neuro command-line interface."""
    args = _build_parser().parse_args()
    if args.command == "info":
        print(f"P37 Neuro {__version__}")
        print("Ontos World general-purpose robot intelligence program")
    elif args.command == "validate-config":
        config = load_config(args.path)
        print(f"valid config: {config.project} [{config.mode}]")
    elif args.command == "validate-robot":
        body = load_urdf(args.path) if args.path.suffix.lower() == ".urdf" else load_mjcf(args.path)
        print(f"valid embodiment: {body.embodiment_id} ({body.action_dimension} joints)")
    elif args.command == "inspect-episode":
        episode = read_episode(args.path)
        print(f"valid episode: {episode.episode_id} ({len(episode.steps)} steps)")
    elif args.command == "robot" and args.robot_command == "init":
        path = create_robot_manifest_template(args.name, args.output / args.name)
        print(f"created robot manifest: {path}")
        print("set description.path to the real URDF/MJCF/USD file, then run:")
        print(f"p37 robot validate {path}")
    elif args.command == "robot" and args.robot_command == "validate":
        result = validate_robot_integration(args.path)
        print(f"qualified integration contract: {result.robot_id}")
        print(f"controllable joints: {result.action_dimension}")
        print(f"control frequency: {result.control_frequency_hz:g} Hz")
        if result.warnings:\n            print("warnings: " + "; ".join(result.warnings))\n    elif args.command == "qualify":\n        evidence = load_qualification_evidence(args.evidence)\n        report = build_qualification_report(evidence, robot_manifest=args.robot)\n        json_path, md_path = write_qualification_report(report, args.output)\n        print(f"qualification result: {report.status.value}")\n        print(f"json: {json_path}")\n        print(f"report: {md_path}")\n

if __name__ == "__main__":
    main()
