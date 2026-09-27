from p37_neuro.benchmarks.manipulation import ManipulationTrial, transfer_metrics
from p37_neuro.data.adapters.rlds import from_records


def test_rlds_record_adapter() -> None:
    episode = from_records(
        episode_id="e",
        embodiment_id="arm",
        task_id="pick",
        source="rlds:test",
        records=[
            {
                "timestamp_s": 0.0,
                "observation": {
                    "joint_position": {"j": 0.0},
                    "joint_velocity": {"j": 0.0},
                },
                "action": {"j": 0.2},
                "reward": 1.0,
            }
        ],
    )
    assert episode.steps[0].action.joint_commands["j"] == 0.2


def test_manipulation_metrics() -> None:
    metrics = transfer_metrics(
        (
            ManipulationTrial("a", "pick", True, 0, 2.0),
            ManipulationTrial("b", "pick", False, 1, 4.0),
        )
    )
    assert metrics["success_rate"] == 0.5
