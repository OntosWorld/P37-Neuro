"""Small developer-facing CLI for repository introspection."""

from __future__ import annotations

import argparse

from p37_neuro import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="p37-neuro")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("info", help="print package and program information")
    return parser


def main() -> None:
    """Run the P37 Neuro command-line interface."""
    args = _build_parser().parse_args()
    if args.command == "info":
        print(f"P37 Neuro {__version__}")
        print("Ontos World general-purpose robot intelligence program")


if __name__ == "__main__":
    main()
