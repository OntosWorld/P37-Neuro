"""Developer-facing CLI for validation and repository operations."""

from __future__ import annotations

import argparse
from pathlib import Path

from p37_neuro import __version__
from p37_neuro.config import load_config
from p37_neuro.data.storage import read_episode
from p37_neuro.deployment import (
    DeploymentTarget,
    RolloutPlan,
    build_rollback_plan,
    load_rollout_plan,
    write_rollout_plan,
)
from p37_neuro.embodiment.importers import load_mjcf, load_urdf
from p37_neuro.integration import (
    create_robot_manifest_template,
    run_mujoco_preflight,
    validate_robot_integration,
)
from p37_neuro.qualification import (
    build_qualification_report,
    load_qualification_evidence,
    write_qualification_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="p37")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="print package and program information")

    config = subparsers.add_parser("validate-config", help="validate a P37 YAML/JSON config")
    config.add_argument("path", type=Path)

    robot_description = subparsers.add_parser(
        "validate-robot",
        help="normalize and validate a URDF/MJCF robot description",
    )
    robot_description.add_argument("path", type=Path)

    replay = subparsers.add_parser("inspect-episode", help="verify and summarize an episode")
    replay.add_argument("path", type=Path)

    robot_group = subparsers.add_parser("robot", help="create and validate robot integrations")
    robot_commands = robot_group.add_subparsers(dest="robot_command", required=True)
    robot_init = robot_commands.add_parser("init", help="create a robot integration manifest")
    robot_init.add_argument("name")
    robot_init.add_argument("--output", type=Path, default=Path("robots"))
    robot_validate = robot_commands.add_parser("validate", help="validate a robot integration")
    robot_validate.add_argument("path", type=Path)

    simulate = subparsers.add_parser("simulate", help="run a simulator integration preflight")
    simulate.add_argument("--robot", type=Path, required=True)
    simulate.add_argument("--backend", choices=("mujoco",), default="mujoco")
    simulate.add_argument("--steps", type=int, default=10)
    simulate.add_argument("--seed", type=int, default=0)

    qualify = subparsers.add_parser("qualify", help="generate a release qualification report")
    qualify.add_argument("--evidence", type=Path, required=True)
    qualify.add_argument("--robot", type=Path)
    qualify.add_argument("--output", type=Path, default=Path("artifacts/qualification"))

    deploy = subparsers.add_parser("deploy", help="create a qualified fleet rollout plan")
    deploy.add_argument("--artifact", required=True)
    deploy.add_argument("--previous", required=True)
    deploy.add_argument("--organization", required=True)
    deploy.add_argument("--site", required=True)
    deploy.add_argument("--fleet", required=True)
    deploy.add_argument("--robots", required=True, help="comma-separated robot IDs")
    deploy.add_argument("--qualification-report", required=True)
    deploy.add_argument("--canary-count", type=int, default=1)
    deploy.add_argument("--batch-size", type=int, default=10)
    deploy.add_argument("--max-unhealthy-fraction", type=float, default=0.10)
    deploy.add_argument("--output", type=Path, default=Path("artifacts/rollout.json"))

    status = subparsers.add_parser("status", help="inspect a fleet rollout plan")
    status.add_argument("--plan", type=Path, required=True)

    rollback = subparsers.add_parser("rollback", help="create a rollback plan")
    rollback.add_argument("--plan", type=Path, required=True)
    rollback.add_argument("--output", type=Path, default=Path("artifacts/rollback.json"))
    return parser


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
        if result.warnings:
            print("warnings: " + "; ".join(result.warnings))
    elif args.command == "simulate":
        result = run_mujoco_preflight(args.robot, steps=args.steps, seed=args.seed)
        print(f"simulation preflight: {result.robot_id}")
        print(f"backend: {result.backend}")
        print(f"steps: {result.steps}")
        print(f"controllable joints: {result.action_dimension}")
        print(f"final simulation time: {result.final_time_s:.6f} s")
    elif args.command == "qualify":
        evidence = load_qualification_evidence(args.evidence)
        report = build_qualification_report(evidence, robot_manifest=args.robot)
        json_path, md_path = write_qualification_report(report, args.output)
        print(f"qualification result: {report.status.value}")
        print(f"json: {json_path}")
        print(f"report: {md_path}")
    elif args.command == "deploy":
        robot_ids = tuple(item.strip() for item in args.robots.split(",") if item.strip())
        plan = RolloutPlan(
            schema_version=1,
            artifact_id=args.artifact,
            previous_artifact_id=args.previous,
            target=DeploymentTarget(args.organization, args.site, args.fleet, robot_ids),
            qualification_report_uri=args.qualification_report,
            canary_count=args.canary_count,
            batch_size=args.batch_size,
            maximum_unhealthy_fraction=args.max_unhealthy_fraction,
        )
        path = write_rollout_plan(plan, args.output)
        print(f"created rollout plan: {path}")
        print(f"batches: {len(plan.batches())}")
    elif args.command == "status":
        plan = load_rollout_plan(args.plan)
        target = plan.target
        print(f"artifact: {plan.artifact_id}")
        print(f"target: {target.organization_id}/{target.site_id}/{target.fleet_id}")
        print(f"robots: {len(target.robot_ids)}")
        print(f"batches: {len(plan.batches())}")
    elif args.command == "rollback":
        plan = load_rollout_plan(args.plan)
        rollback_plan = build_rollback_plan(plan)
        path = write_rollout_plan(rollback_plan, args.output)
        print(f"created rollback plan: {path}")
        print(f"target artifact: {rollback_plan.artifact_id}")


if __name__ == "__main__":
    main()
