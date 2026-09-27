import pytest

from p37_neuro.training.curriculum import (
    disturbance_curriculum,
    recovery_curriculum,
)


def test_recovery_curriculum_advances_only_after_gate() -> None:
    curriculum = recovery_curriculum()
    assert curriculum.current.name == "retry"
    curriculum.observe(0.80)
    assert curriculum.current.name == "retry"
    curriculum.observe(0.95)
    assert curriculum.current.name == "recover"


def test_disturbance_curriculum_reaches_adversarial_stage() -> None:
    curriculum = disturbance_curriculum()
    curriculum.observe(0.95)
    assert curriculum.current.name == "randomized"
    curriculum.observe(0.90)
    assert curriculum.current.name == "adversarial"
    assert curriculum.current.parameters["external_impulse"] > 0.0


def test_curriculum_rejects_invalid_rate() -> None:
    with pytest.raises(ValueError):
        recovery_curriculum().observe(1.1)
