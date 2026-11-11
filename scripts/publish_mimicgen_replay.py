"""Publish a small, attributed P37 replay from official MimicGen source demonstrations.

The exported traces are source demonstrations passing through P37 canonical
episode normalization. They are neither a trained P37 policy nor a rerun of
the source controller. Keep original dataset attribution and SHA-256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from p37_neuro.data.mimicgen_import import MimicGenSelection, list_demos, read_mimicgen_episode
from p37_neuro.data.trace_export import TraceProvenance, export_comparison, write_comparison

DATASET = "amandlek/mimicgen_datasets"
SOURCE_PATH = "source/square.hdf5"
SOURCE_URL = (
    "https://huggingface.co/datasets/"
    + DATASET
    + "/resolve/main/"
    + SOURCE_PATH
)
SOURCE_SHA256 = "c917e99362fd9bd11978d6e2642c1ea88272702fbf55b50367ed471febf550e2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=5
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--demos", nargs="+", default=["demo_0", "demo_1"])
    parser.add_argument("--control-hz", type=float, default=20.0)
    parser.add_argument("--max-steps", type=int, default=500)
    args = parser.parse_args()
    if len(args.demos) < 2 or len(set(args.demos)) != len(args.demos):
        parser.error("choose at least two unique source demonstrations")
    calculated_sha = sha256(args.source)
    if calculated_sha != SOURCE_SHA256:
        raise ValueError(
            "Official source dataset hash mismatch. Refuse publication: " + calculated_sha
        )
    available = set(list_demos(args.source))
    if not set(args.demos).issubset(available):
        raise ValueError("Requested demos missing from source: " + str(sorted(available)))

    episodes = []
    provenance = []
    revision = git_revision()
    for demo_id in args.demos:
        selection = MimicGenSelection(
            path=args.source,
            demo_id=demo_id,
            embodiment_id="panda-source",
            task_id="square-source-demonstration",
            control_hz=args.control_hz,
        )
        episode = read_mimicgen_episode(selection, max_steps=args.max_steps)
        # Preserve source lineage and distinguish inferred timing from verified timing.
        episode = replace(
            episode,
            metadata={
                **episode.metadata,
                "source_url": SOURCE_URL,
                "source_file_sha256": calculated_sha,
                "source_episode": demo_id,
                "data_type": "recorded-human-teleoperation",
                "control_frequency_assumption": "20 Hz supplied by conversion configuration",
                "robot_name_scope": "source robot; no trained P37 checkpoint",
            },
        )
        episodes.append(episode)
        provenance.append(
            TraceProvenance(
                checkpoint_sha256="",
                code_commit=revision,
                simulator="Original MimicGen / robosuite HDF5, offline source recording",
                simulator_version="original source environment version not verified",
                robot_description_sha256="not available in converted source",
                adapter_version="p37-mimicgen-hdf5-v1",
                seed=0,
                training_membership="unknown",
                evidence_level="T1",
                policy_attached=False,
                evaluation_protocol="docs/interactive-lab/steel/README.md",
                outcome="unverified",
            )
        )
    data = export_comparison(
        episodes, provenance, title="MimicGen Square: P37 canonical source-data replay"
    )
    data["publication"] = {
        "type": "third_party_recorded_demonstrations",
        "source": DATASET,
        "source_file": SOURCE_PATH,
        "source_sha256": calculated_sha,
        "source_url": SOURCE_URL,
        "license": "CC BY 4.0",
        "p37_use": "canonical episode ingestion and synchronized playback only",
        "learned_policy_attached": False,
        "cross_embodiment_evaluation": False,
        "original_robot_family": "Panda (source demonstration; source hardware is simulated)",
    }
    write_comparison(args.output, data)
    # Write a small, visible machine-readable source manifest for independent audit.
    manifest_path = args.output.with_name("manifest.json")
    manifest_path.write_text(
        json.dumps(
            {
                "source": SOURCE_URL,
                "source_sha256": calculated_sha,
                "license": "CC BY 4.0",
                "episode_ids": args.demos,
                "produced_by": revision,
                "policy_attached": False,
                "status": "source data replay, no learned model",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for episode in episodes:
        print(f"{episode.episode_id}: {len(episode.steps)} source observations")
    print(f"Wrote {args.output} from verified MimicGen source file {calculated_sha}")


if __name__ == "__main__":
    main()
