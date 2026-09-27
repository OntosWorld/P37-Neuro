import pytest

from p37_neuro.demonstration.context import DemonstrationContext, DemonstrationReference
from p37_neuro.demonstration.sampling import uniform_timestamps


def test_demo_context_requires_signal() -> None:
    with pytest.raises(ValueError):
        DemonstrationContext(task_id="x", demonstrations=())


def test_uniform_timestamp_sampling_includes_boundaries() -> None:
    assert uniform_timestamps(0.0, 2.0, 3) == (0.0, 1.0, 2.0)


def test_demo_reference_validation() -> None:
    with pytest.raises(ValueError):
        DemonstrationReference(uri="x", start_s=2, end_s=1)
