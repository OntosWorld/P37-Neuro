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


if __name__ == "__main__":
    main()
