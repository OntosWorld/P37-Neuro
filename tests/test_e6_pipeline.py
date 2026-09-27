from pathlib import Path

from p37_neuro.data.quality import QualityDecision, score_episode
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.fleet.logger import FleetEvent
from p37_neuro.fleet.review import ReviewItem, ReviewQueue, ReviewStatus
from p37_neuro.fleet.spool import FleetSpool
from p37_neuro.fleet.uploader import FleetUploader


class FakeTransport:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.keys: list[str] = []

    def send(self, event: FleetEvent, *, idempotency_key: str) -> None:
        if self.fail:
            raise OSError("offline")
        self.keys.append(idempotency_key)


def _episode(*, intervention: bool = False, terminal: bool = True) -> Episode:
    observation = Observation(0.0, {"j": 0.0}, {"j": 0.0})
    action = Action(0.0, {"j": 0.1})
    return Episode(
        "episode",
        "robot",
        "task",
        (
            EpisodeStep(
                observation,
                action,
                reward=1.0,
                terminal=terminal,
                intervention=intervention,
            ),
        ),
        "fleet",
    )


def test_spool_is_idempotent_and_retries(tmp_path: Path) -> None:
    spool = FleetSpool(tmp_path / "spool.db")
    event = FleetEvent("e1", "r1", "m1", 1.0, "episode", {"score": 1.0})
    spool.enqueue(event)
    spool.enqueue(event)
    assert len(spool.pending()) == 1

    failed = FleetUploader(spool, FakeTransport(fail=True)).flush()
    assert failed.failed == 1
    assert spool.pending()[0].attempts == 1

    transport = FakeTransport()
    result = FleetUploader(spool, transport).flush()
    assert result.sent == 1
    assert transport.keys == ["e1"]
    assert not spool.pending()


def test_quality_triage_and_review_queue(tmp_path: Path) -> None:
    accepted = score_episode(_episode())
    assert accepted.decision is QualityDecision.ACCEPT

    review = score_episode(_episode(intervention=True, terminal=False))
    assert review.decision is QualityDecision.REVIEW

    queue = ReviewQueue(tmp_path / "review.db")
    queue.enqueue(ReviewItem("episode", "intervention", 10))
    assert queue.pending()[0].episode_id == "episode"
    queue.decide("episode", ReviewStatus.ACCEPTED)
    assert not queue.pending()
