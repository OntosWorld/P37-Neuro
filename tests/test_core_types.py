import pytest

from p37_neuro.core.types import NumericRange


def test_numeric_range_clamps_values() -> None:
    bounds = NumericRange(-1.0, 1.0)
    assert bounds.clamp(-2.0) == -1.0
    assert bounds.clamp(0.25) == 0.25
    assert bounds.clamp(2.0) == 1.0


def test_numeric_range_rejects_invalid_order() -> None:
    with pytest.raises(ValueError, match="minimum"):
        NumericRange(1.0, -1.0)
