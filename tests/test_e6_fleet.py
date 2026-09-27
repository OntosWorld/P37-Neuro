from pathlib import Path

from p37_neuro.data.lineage import DatasetVersion
from p37_neuro.deployment.manager import DeploymentRecord, ReleaseChannel
from p37_neuro.fleet.logger import FleetEvent, FleetLogger


def test_fleet_logger_round_trip(tmp_path: Path) -> None:
    logger = FleetLogger(tmp_path / "events.jsonl")
    logger.append(FleetEvent("e1", "r1", "m1", 1.0, "success", {"task": "pick"}))
    assert logger.read()[0].kind == "success"


def test_dataset_lineage_validation() -> None:
    version = DatasetVersion("fleet", "v1", "abc", episode_count=3)
    assert version.episode_count == 3


def test_deployment_promotion_and_rollback() -> None:
    record = DeploymentRecord("m2")
    record.promote_to_staging()
    record.promote_to_production("m1")
    assert record.channel is ReleaseChannel.PRODUCTION
    assert record.rollback() == "m1"
