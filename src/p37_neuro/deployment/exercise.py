"""Executable simulated E6 fleet-to-release lifecycle.

The exercise uses only local resources and deterministic synthetic data. It
validates the control-plane sequence without claiming a production fleet test.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from p37_neuro.data.lineage import DatasetVersion
from p37_neuro.data.quality import QualityDecision, score_episode
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.storage import write_episode
from p37_neuro.deployment.manager import DeploymentRecord, ReleaseChannel
from p37_neuro.deployment.release import ReleaseManifest, ReleaseSigner, verify_release
from p37_neuro.deployment.store import FilesystemArtifactStore
from p37_neuro.fleet.logger import FleetEvent, FleetLogger
from p37_neuro.fleet.review import ReviewItem, ReviewQueue, ReviewStatus
from p37_neuro.fleet.spool import FleetSpool
from p37_neuro.fleet.uploader import FleetUploader
from p37_neuro.registry import ArtifactRecord, ArtifactRegistry


@dataclass(frozen=True, slots=True)
class E6LifecycleReport:
    feedback_events_sent: int
    episode_quality_score: float
    initial_quality_decision: str
    human_review_completed: bool
    dataset_version: str
    artifact_id: str
    artifact_sha256: str
    release_signature_verified: bool
    reached_staging: bool
    reached_production: bool
    rollback_target: str
    final_channel: str


class _MemoryTransport:
    def __init__(self) -> None:
        self.received: list[tuple[str, str]] = []

    def send(self, event: FleetEvent, *, idempotency_key: str) -> None:
        self.received.append((event.event_id, idempotency_key))


def _feedback_episode() -> Episode:
    steps: list[EpisodeStep] = []
    for index in range(4):
        steps.append(
            EpisodeStep(
                observation=Observation(
                    timestamp_s=index * 0.1,
                    joint_position={"joint_1": 0.1 * index},
                    joint_velocity={"joint_1": 0.05},
                ),
                action=Action(
                    timestamp_s=index * 0.1,
                    joint_commands={"joint_1": 0.2 * index},
                ),
                reward=1.0,
                terminal=index == 3,
                intervention=index == 1,
            )
        )
    return Episode(
        episode_id="sim-feedback-001",
        embodiment_id="sim-arm",
        task_id="sim-pick",
        steps=tuple(steps),
        source="e6-lifecycle-smoke",
        metadata={"capability_evidence": "false"},
    )


def run_e6_lifecycle(output_dir: str | Path) -> E6LifecycleReport:
    """Exercise fleet feedback through release promotion and rollback."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    episode = _feedback_episode()
    episode_path = root / "feedback" / "episode.jsonl"
    episode_sha = write_episode(episode_path, episode)

    event = FleetEvent(
        event_id="sim-event-001",
        robot_id="sim-robot-001",
        model_id="p37-stable-v0",
        timestamp_s=1.0,
        kind="episode_ready",
        payload={"episode_id": episode.episode_id, "sha256": episode_sha},
    )
    logger = FleetLogger(root / "fleet" / "events.jsonl")
    logger.append(event)

    spool = FleetSpool(root / "fleet" / "spool.sqlite3")
    spool.enqueue(event)
    transport = _MemoryTransport()
    flush = FleetUploader(spool, transport).flush()
    if flush.sent != 1 or flush.failed != 0:
        raise RuntimeError("simulated fleet feedback upload failed")

    quality = score_episode(episode)
    review_completed = False
    if quality.decision is QualityDecision.REVIEW:
        queue = ReviewQueue(root / "fleet" / "review.sqlite3")
        queue.enqueue(
            ReviewItem(
                episode_id=episode.episode_id,
                reason=",".join(quality.reasons),
                priority=50,
            )
        )
        queue.decide(episode.episode_id, ReviewStatus.ACCEPTED)
        review_completed = not queue.pending()
    elif quality.decision is QualityDecision.REJECT:
        raise RuntimeError("synthetic lifecycle episode was rejected unexpectedly")

    dataset = DatasetVersion(
        dataset_id="fleet-feedback",
        version="sim-v1",
        sha256=episode_sha,
        parent="fleet-feedback:stable",
        episode_count=1,
    )

    candidate_file = root / "candidate" / "p37-candidate.bin"
    candidate_file.parent.mkdir(parents=True, exist_ok=True)
    candidate_file.write_bytes(b"P37 simulated candidate artifact\n")
    stored = FilesystemArtifactStore(root / "artifacts").put(candidate_file)

    artifact_id = "p37-sim-candidate-v1"
    registry = ArtifactRegistry(root / "registry")
    registry.register(
        ArtifactRecord(
            artifact_id=artifact_id,
            stage="E6",
            path=str(stored.path),
            sha256=stored.sha256,
            config_id="e6-lifecycle-smoke",
            dataset_id=f"{dataset.dataset_id}:{dataset.version}",
            metrics={"episode_quality": quality.score},
        )
    )

    manifest = ReleaseManifest(
        schema_version=1,
        artifact_id=artifact_id,
        artifact_sha256=stored.sha256,
        config_id="e6-lifecycle-smoke",
        dataset_id=f"{dataset.dataset_id}:{dataset.version}",
        stage="E6",
        metrics={"episode_quality": quality.score},
    )
    signer = ReleaseSigner.generate()
    release = signer.sign(manifest)
    verify_release(release, signer.public_key)
    (root / "candidate" / "release.json").write_text(release.to_json(), encoding="utf-8")

    deployment = DeploymentRecord(artifact_id)
    deployment.promote_to_staging()
    reached_staging = deployment.channel is ReleaseChannel.STAGING
    deployment.promote_to_production("p37-stable-v0")
    reached_production = deployment.channel is ReleaseChannel.PRODUCTION
    rollback_target = deployment.rollback()

    report = E6LifecycleReport(
        feedback_events_sent=flush.sent,
        episode_quality_score=quality.score,
        initial_quality_decision=quality.decision.value,
        human_review_completed=review_completed,
        dataset_version=f"{dataset.dataset_id}:{dataset.version}",
        artifact_id=artifact_id,
        artifact_sha256=stored.sha256,
        release_signature_verified=True,
        reached_staging=reached_staging,
        reached_production=reached_production,
        rollback_target=rollback_target,
        final_channel=deployment.channel.value,
    )
    (root / "report.json").write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(prog="p37-e6-lifecycle-smoke")
    parser.add_argument("--output", type=Path, default=Path("artifacts/e6-lifecycle-smoke"))
    args = parser.parse_args()
    report = run_e6_lifecycle(args.output)
    print(json.dumps(asdict(report), sort_keys=True))


if __name__ == "__main__":
    main()
