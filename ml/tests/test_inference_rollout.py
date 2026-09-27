from dataclasses import dataclass

from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.data.schema import Action, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec
from p37_neuro_ml.inference import InferenceSession
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.rollout import collect_episode


@dataclass
class FakeSimulator:
    embodiment: EmbodimentSpec
    position: float = 0.0
    timestamp: float = 0.0

    def reset(self, seed: int) -> Observation:
        self.position = 0.0
        self.timestamp = 0.0
        return Observation(0.0, {"j": 0.0}, {"j": 0.0})

    def step(self, action: Action) -> Observation:
        self.timestamp += 0.1
        target = action.joint_commands["j"]
        velocity = target - self.position
        self.position = target
        return Observation(self.timestamp, {"j": self.position}, {"j": velocity})

    def close(self) -> None:
        pass


def _body() -> EmbodimentSpec:
    return EmbodimentSpec(
        "fake",
        "arm",
        (
            JointSpec(
                "j",
                JointType.REVOLUTE,
                ControlMode.POSITION,
                NumericRange(-1.0, 1.0),
                2.0,
                10.0,
            ),
        ),
    )


def test_stateful_inference_produces_safe_physical_action() -> None:
    body = _body()
    model = P37Neuro(NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8))
    session = InferenceSession(model, body)
    action = session.act(Observation(0.0, {"j": 0.0}, {"j": 0.0}))
    assert -1.0 <= action.joint_commands["j"] <= 1.0
    assert session._memory is not None


def test_rollout_collects_canonical_episode() -> None:
    body = _body()
    simulator = FakeSimulator(body)
    model = P37Neuro(NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8))
    session = InferenceSession(model, body)
    episode = collect_episode(
        simulator,
        session,
        episode_id="rollout-1",
        task_id="hold",
        seed=4,
        max_steps=3,
        reward=lambda _before, _action, after: -abs(after.joint_position["j"]),
    )
    assert len(episode.steps) == 3
    assert episode.source == "p37-policy-rollout"
