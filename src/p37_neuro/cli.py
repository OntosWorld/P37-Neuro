"""Developer-facing CLI for validation and repository operations."""

from __future__ import annotations

import argparse
from pathlib import Path

from p37_neuro import __version__
from p37_neuro.config import load_config
from p37_neuro.data.storage import read_episode
from p37_neuro.embodiment.importers import load_mjcf, load_urdf


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


if __name__ == "__main__":
    main()
