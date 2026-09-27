from p37_neuro.benchmarks.locomotion import LocomotionResult, aggregate
from p37_neuro.simulation.morphology import MorphologyRange, generate_morphology
from p37_neuro.simulation.randomization import DomainRandomization


def test_morphology_generation_is_deterministic() -> None:
    a = generate_morphology(42)
    b = generate_morphology(42)
    assert a == b


def test_morphology_generation_respects_range() -> None:
    body = generate_morphology(4, MorphologyRange(min_joints=3, max_joints=3))
    assert body.action_dimension == 3


def test_domain_randomization_is_seeded() -> None:
    randomization = DomainRandomization()
    assert randomization.sample(1) == randomization.sample(1)


def test_locomotion_aggregate() -> None:
    metrics = aggregate(
        (
            LocomotionResult("a", 5.0, 0, 0, True),
            LocomotionResult("b", 3.0, 1, 0, False),
        )
    )
    assert metrics["recovery_rate"] == 0.5
    assert metrics["mean_score"] > 0
