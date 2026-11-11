"""Convert two or more official MimicGen HDF5 demos into the P37 trace viewer format.

Example:
    python scripts/mimicgen_to_p37.py \
      --source panda=/data/robot/square_d0_panda.hdf5 \
      --source sawyer=/data/robot/square_d0_sawyer.hdf5 \
      --task square_d0 --demo demo_0 --control-hz 20 --output artifacts/mimicgen.json

The --control-hz value must be checked against source environment metadata.
MimicGen playback is not a trained P37 checkpoint or new closed-loop evaluation.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from p37_neuro.data.mimicgen_import import MimicGenSelection, list_demos, read_mimicgen_episode
from p37_neuro.data.trace_export import TraceProvenance, export_comparison, write_comparison


def _revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="ROBOT=FILE")
    parser.add_argument("--demo", required=True, help="HDF5 demo ID, e.g. demo_0")
    parser.add_argument("--task", required=True, help="Original task name, e.g. square_d0")
    parser.add_argument(
        "--control-hz", type=float, required=True, help="Verified source action sampling rate"
    )
    parser.add_argument("--max-steps", type=int, default=1500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(args.source) < 2:
        parser.error("select two or more source robot datasets")
    selections: list[MimicGenSelection] = []
    for source in args.source:
        if "=" not in source:
            parser.error("--source expects ROBOT=FILE")
        robot, path = source.split("=", 1)
        selections.append(
            MimicGenSelection(
                path=Path(path).expanduser(),
                demo_id=args.demo,
                embodiment_id=robot,
                task_id=args.task,
                control_hz=args.control_hz,
            )
        )
    if len({source.embodiment_id for source in selections}) != len(selections):
        parser.error("each source robot ID must be different")
    revision = _revision()
    episodes = []
    provenances = []
    for selection in selections:
        if selection.demo_id not in list_demos(selection.path):
            parser.error("missing demo " + selection.demo_id + " in " + str(selection.path))
        episodes.append(read_mimicgen_episode(selection, max_steps=args.max_steps))
        provenances.append(
            TraceProvenance(
                checkpoint_sha256="",
                code_commit=revision,
                simulator="MimicGen / robosuite recording (offline only)",
                simulator_version="not verified by this converter",
                robot_description_sha256="not provided by this conversion",
                adapter_version="p37-mimicgen-hdf5-v1",
                seed=0,
                training_membership="unknown",
                evidence_level="T1",
                policy_attached=False,
                evaluation_protocol="docs/interactive-lab/steel/README.md",
                outcome="unverified",
            )
        )
    artifact = export_comparison(
        episodes, provenances, title="MimicGen recorded demonstrations — " + args.task
    )
    write_comparison(args.output, artifact)
    print("Wrote", len(episodes), "source demonstrations to", args.output)
    print("These are MimicGen recordings, not P37-trained policy rollouts.")


if __name__ == "__main__":
    main()
