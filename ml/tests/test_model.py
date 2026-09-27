from pathlib import Path

import torch

from p37_neuro_ml.checkpoint import load_checkpoint, save_checkpoint
from p37_neuro_ml.losses import imitation_loss, ppo_loss
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.trainer import BehaviorCloningTrainer, BrainBatch


def _inputs(config: NeuroConfig):
    torch.manual_seed(7)
    batch, steps, joints = 2, 3, 5
    joint_features = torch.randn(batch, joints, config.joint_feature_dim)
    joint_state = torch.randn(batch, steps, joints, config.joint_state_dim)
    joint_mask = torch.tensor([[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]], dtype=torch.bool)
    scene = torch.randn(batch, steps, config.image_channels, 32, 32)
    demos = torch.randn(batch, 2, config.image_channels, 32, 32)
    tasks = torch.randn(batch, 1, config.task_feature_dim)
    return joint_features, joint_state, joint_mask, scene, demos, tasks


def test_forward_supports_variable_morphology() -> None:
    config = NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8)
    model = P37Neuro(config).eval()
    features, state, mask, scene, demos, tasks = _inputs(config)
    with torch.no_grad():
        output = model(
            joint_features=features,
            joint_state=state,
            joint_mask=mask,
            scene_images=scene,
            demonstration_images=demos,
            task_features=tasks,
        )
    assert output.action_mean.shape == (2, 3, 5)
    assert output.high_level.shape == (2, 3, 8)
    assert output.value.shape == (2, 3)
    assert output.memory.shape == (config.temporal_layers, 2, 32)
    assert torch.all(output.action_mean[0, :, 3:] == 0)


def test_imitation_and_ppo_losses_backpropagate() -> None:
    config = NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8)
    model = P37Neuro(config)
    features, state, mask, *_ = _inputs(config)
    output = model(joint_features=features, joint_state=state, joint_mask=mask)
    targets = torch.zeros_like(output.action_mean)
    bc = imitation_loss(output, target_actions=targets, joint_mask=mask)
    bc.total.backward(retain_graph=True)
    assert torch.isfinite(bc.total)

    ppo = ppo_loss(
        output,
        actions=targets,
        joint_mask=mask,
        old_log_prob=torch.zeros_like(output.value),
        advantages=torch.ones_like(output.value),
        returns=torch.zeros_like(output.value),
    )
    assert torch.isfinite(ppo.total)


def test_behavior_cloning_step_updates_model() -> None:
    config = NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8)
    model = P37Neuro(config)
    features, state, mask, *_ = _inputs(config)
    before = model.action_head[-2].weight.detach().clone()
    trainer = BehaviorCloningTrainer(model, learning_rate=1e-3)
    metrics = trainer.step(
        BrainBatch(
            joint_features=features,
            joint_state=state,
            joint_mask=mask,
            time_mask=torch.ones(2, 3, dtype=torch.bool),
            target_actions=torch.zeros(2, 3, 5),
        )
    )
    assert metrics.loss >= 0
    assert not torch.equal(before, model.action_head[-2].weight.detach())


def test_checkpoint_round_trip(tmp_path: Path) -> None:
    config = NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8)
    model = P37Neuro(config)
    digest = save_checkpoint(tmp_path, model, metadata={"stage": "E2"})
    loaded, manifest = load_checkpoint(tmp_path)
    assert len(digest) == 64
    assert manifest["metadata"]["stage"] == "E2"
    assert loaded.config == config
