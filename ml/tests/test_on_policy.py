import torch

from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.on_policy import OnPolicyCollector, PolicyState, RolloutConfig


class FakeVectorEnv:
    def __init__(self) -> None:
        self.step_index = 0
        self.features = torch.zeros(2, 3, 10)
        self.mask = torch.ones(2, 3, dtype=torch.bool)

    def _state(self) -> PolicyState:
        state = torch.full((2, 3, 2), float(self.step_index))
        return PolicyState(self.features, state, self.mask)

    def reset(self, seed: int) -> PolicyState:
        self.step_index = seed * 0
        return self._state()

    def step(self, actions: torch.Tensor) -> tuple[PolicyState, torch.Tensor, torch.Tensor]:
        assert actions.shape == (2, 3)
        self.step_index += 1
        reward = torch.ones(2)
        done = torch.tensor([self.step_index == 2, False])
        return self._state(), reward, done


def test_on_policy_collector_builds_ppo_batch() -> None:
    model = P37Neuro(
        NeuroConfig(
            model_dim=16,
            task_feature_dim=8,
            high_level_dim=4,
            transformer_heads=4,
            transformer_layers=1,
            temporal_layers=1,
            context_length=8,
            dropout=0.0,
        )
    )
    collector = OnPolicyCollector(
        model,
        FakeVectorEnv(),
        RolloutConfig(horizon=4, gamma=0.9),
    )
    batch = collector.collect(seed=5)

    assert batch.joint_state.shape == (2, 4, 3, 2)
    assert batch.actions.shape == (2, 4, 3)
    assert batch.old_log_prob.shape == (2, 4)
    assert batch.returns.shape == (2, 4)
    assert torch.isfinite(batch.advantages).all()
