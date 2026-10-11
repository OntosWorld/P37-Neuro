"""Command-line lifecycle for training, evaluating and exporting P37 Neuro."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from p37_neuro_ml.experiment import evaluate_checkpoint, train_behavior_cloning
from p37_neuro_ml.export import export_onnx


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="p37-neuro-ml")
    commands = parser.add_subparsers(dest="command", required=True)

    train = commands.add_parser("train-bc", help="train behavior cloning from a manifest")
    train.add_argument("manifest", type=Path)

    evaluate = commands.add_parser("evaluate", help="evaluate a checkpoint on a manifest")
    evaluate.add_argument("manifest", type=Path)
    evaluate.add_argument("checkpoint", type=Path)

    export = commands.add_parser("export-onnx", help="export a checkpoint for deployment")
    export.add_argument("checkpoint", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--joints", type=int, required=True)
    export.add_argument("--image-height", type=int, default=64)
    export.add_argument("--image-width", type=int, default=64)
    export.add_argument("--demonstration-frames", type=int, default=1)
    export.add_argument("--task-tokens", type=int, default=1)

    reach = commands.add_parser(
        "reach-sim", help="train and evaluate a goal-conditioned MuJoCo reach policy"
    )
    reach.add_argument("--robot", type=Path, required=True)
    reach.add_argument("--output", type=Path, required=True)
    reach.add_argument("--seed", type=int, default=317)
    reach.add_argument("--train-targets", type=int, default=64)
    reach.add_argument("--eval-targets", type=int, default=20)
    reach.add_argument("--epochs", type=int, default=200)
    reach.add_argument("--steps", type=int, default=100)
    reach.add_argument("--success-threshold", type=float, default=0.025)
    reach.add_argument("--qualification-rate", type=float, default=0.90)

    reach_suite = commands.add_parser(
        "reach-sim-suite", help="run multi-seed MuJoCo reach qualification"
    )
    reach_suite.add_argument("--robot", type=Path, required=True)
    reach_suite.add_argument("--output", type=Path, required=True)
    reach_suite.add_argument("--seeds", default="317,401,503,607,719")
    reach_suite.add_argument("--train-targets", type=int, default=64)
    reach_suite.add_argument("--eval-targets", type=int, default=100)
    reach_suite.add_argument("--epochs", type=int, default=200)
    reach_suite.add_argument("--steps", type=int, default=100)
    reach_suite.add_argument("--success-threshold", type=float, default=0.025)
    reach_suite.add_argument("--qualification-rate", type=float, default=0.90)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "train-bc":
        result = train_behavior_cloning(args.manifest)
        print(
            json.dumps(
                {
                    "checkpoint": str(result.checkpoint_dir),
                    "examples": result.examples,
                    "epochs": result.epochs,
                    "final_loss": result.final_loss,
                },
                sort_keys=True,
            )
        )
    elif args.command == "evaluate":
        print(
            json.dumps(
                evaluate_checkpoint(args.manifest, args.checkpoint),
                sort_keys=True,
            )
        )
    elif args.command == "export-onnx":
        output = export_onnx(
            args.checkpoint,
            args.output,
            joints=args.joints,
            image_height=args.image_height,
            image_width=args.image_width,
            demonstration_frames=args.demonstration_frames,
            task_tokens=args.task_tokens,
        )
        print(output)
    elif args.command == "reach-sim":
        try:
            from p37_neuro_sim.learned_reach import run_learned_reach_experiment
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "reach-sim requires the simulation extra; run `uv sync --extra sim`"
            ) from exc
        result = run_learned_reach_experiment(
            args.robot,
            output_dir=args.output,
            seed=args.seed,
            train_target_count=args.train_targets,
            evaluation_target_count=args.eval_targets,
            epochs=args.epochs,
            evaluation_steps=args.steps,
            success_threshold_m=args.success_threshold,
            qualification_success_rate=args.qualification_rate,
        )
        print(json.dumps(result, sort_keys=True))
    elif args.command == "reach-sim-suite":
        try:
            from p37_neuro_sim.learned_reach import run_learned_reach_suite
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "reach-sim-suite requires the simulation extra; run `uv sync --extra sim`"
            ) from exc
        try:
            seeds = tuple(int(value.strip()) for value in args.seeds.split(",") if value.strip())
        except ValueError as exc:
            raise SystemExit("--seeds must be a comma-separated list of integers") from exc
        result = run_learned_reach_suite(
            args.robot,
            output_dir=args.output,
            seeds=seeds,
            train_target_count=args.train_targets,
            evaluation_target_count=args.eval_targets,
            epochs=args.epochs,
            evaluation_steps=args.steps,
            success_threshold_m=args.success_threshold,
            qualification_success_rate=args.qualification_rate,
        )
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
