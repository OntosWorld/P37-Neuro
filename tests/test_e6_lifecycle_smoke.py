from pathlib import Path

from p37_neuro.deployment.exercise import run_e6_lifecycle


def test_simulated_e6_lifecycle_reaches_production_then_rolls_back(tmp_path: Path) -> None:
    report = run_e6_lifecycle(tmp_path)

    assert report.feedback_events_sent == 1
    assert report.initial_quality_decision == "review"
    assert report.human_review_completed
    assert report.release_signature_verified
    assert report.reached_staging
    assert report.reached_production
    assert report.rollback_target == "p37-stable-v0"
    assert report.final_channel == "rolled_back"
    assert tmp_path.joinpath("report.json").is_file()
