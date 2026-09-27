from p37_neuro.benchmarks.long_horizon import LongHorizonResult
from p37_neuro.memory.context import ContextWindow, TaskProgress


def test_context_window_is_bounded() -> None:
    memory = ContextWindow[int](capacity=2)
    memory.append(1)
    memory.append(2)
    memory.append(3)
    assert memory.snapshot() == (2, 3)


def test_task_progress_tracks_completion_and_failure() -> None:
    progress = TaskProgress(("pick", "place"))
    progress.mark_complete("pick")
    progress.record_failure("missed-grasp")
    assert progress.progress == 0.5
    assert progress.failures == ["missed-grasp"]


def test_long_horizon_result_progress() -> None:
    result = LongHorizonResult("task", 3, 4, 1, 0, False)
    assert result.progress == 0.75
