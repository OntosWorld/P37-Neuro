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
    rollout_ready,
    write_rollout_plan,
)
from p37_neuro.embodiment.importers import load_mjcf, load_urdf
from p37_neuro.integration import (
    create_robot_manifest_template,
    run_mujoco_preflight,
    validate_robot_integration,
)
from p37_neuro.qualification import (
    QualificationLevel,
    build_qualification_report,
    load_qualification_evidence,
    run_staged_qualification,
    write_qualification_report,
    write_staged_qualification_report,
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

    qualify = subparsers.add_parser("qualify", help="execute or evaluate qualification")
    qualify_mode = qualify.add_mutually_exclusive_group(required=True)
    qualify_mode.add_argument("--evidence", type=Path)
    qualify_mode.add_argument(
        "--level",
        choices=tuple(level.value for level in QualificationLevel),
    )
    qualify.add_argument("--robot", type=Path)
    qualify.add_argument("--artifact")
    qualify.add_argument("--steps", type=int, default=20)
    qualify.add_argument("--seed", type=int, default=0)
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
    deploy.add_argument("--required-approvals", type=int, default=1)
    deploy.add_argument(
        "--approval", action="append", default=[], help="approval identity; repeatable"
    )
    deploy.add_argument("--maintenance-window-utc")
    deploy.add_argument(
        "--manual-rollback",
        action="store_true",
        help="disable automatic rollback on unhealthy-fraction threshold",
    )
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
        integration_result = validate_robot_integration(args.path)
        print(f"qualified integration contract: {integration_result.robot_id}")
        print(f"controllable joints: {integration_result.action_dimension}")
        print(f"control frequency: {integration_result.control_frequency_hz:g} Hz")
        if integration_result.warnings:
            print("warnings: " + "; ".join(integration_result.warnings))
    elif args.command == "simulate":
        simulation_result = run_mujoco_preflight(args.robot, steps=args.steps, seed=args.seed)
        print(f"simulation preflight: {simulation_result.robot_id}")
        print(f"backend: {simulation_result.backend}")
        print(f"steps: {simulation_result.steps}")
        print(f"controllable joints: {simulation_result.action_dimension}")
        print(f"final simulation time: {simulation_result.final_time_s:.6f} s")
    elif args.command == "qualify":
        if args.evidence is not None:
            evidence = load_qualification_evidence(args.evidence)
            report = build_qualification_report(evidence, robot_manifest=args.robot)
            json_path, md_path = write_qualification_report(report, args.output)
            print(f"qualification result: {report.status.value}")
            print(f"json: {json_path}")
            print(f"report: {md_path}")
        else:
            if args.robot is None:
                raise SystemExit("--robot is required with --level")
            if args.artifact is None or not args.artifact.strip():
                raise SystemExit("--artifact is required with --level")
            stage_report = run_staged_qualification(
                robot_manifest=args.robot,
                artifact_id=args.artifact,
                level=QualificationLevel(args.level),
                simulation_steps=args.steps,
                simulation_seed=args.seed,
            )
            json_path, md_path = write_staged_qualification_report(stage_report, args.output)
            print(f"qualification level: {stage_report.level.value}")
            print(f"qualification result: {stage_report.status.value}")
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
            required_approvals=args.required_approvals,
            approvals=tuple(args.approval),
            maintenance_window_utc=args.maintenance_window_utc,
            automatic_rollback=not args.manual_rollback,
        )
        path = write_rollout_plan(plan, args.output)
        print(f"created rollout plan: {path}")
        print(f"batches: {len(plan.batches())}")
        print(f"approvals: {len(plan.approvals)}/{plan.required_approvals}")
        print(f"rollout ready: {str(rollout_ready(plan)).lower()}")
    elif args.command == "status":
        plan = load_rollout_plan(args.plan)
        target = plan.target
        print(f"artifact: {plan.artifact_id}")
        print(f"target: {target.organization_id}/{target.site_id}/{target.fleet_id}")
        print(f"robots: {len(target.robot_ids)}")
        print(f"batches: {len(plan.batches())}")
        print(f"approvals: {len(plan.approvals)}/{plan.required_approvals}")
        print(f"rollout ready: {str(rollout_ready(plan)).lower()}")
        if plan.maintenance_window_utc is not None:
            print(f"maintenance window: {plan.maintenance_window_utc}")
        print(f"automatic rollback: {str(plan.automatic_rollback).lower()}")
    elif args.command == "rollback":
        plan = load_rollout_plan(args.plan)
        rollback_plan = build_rollback_plan(plan)
        path = write_rollout_plan(rollback_plan, args.output)
        print(f"created rollback plan: {path}")
        print(f"target artifact: {rollback_plan.artifact_id}")


if __name__ == "__main__":
    main()
