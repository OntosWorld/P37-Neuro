import torch
from p37_neuro.core.types import ControlMode, JointType, NumericRange
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.embodiment.schema import EmbodimentSpec, JointSpec

from p37_neuro_ml.dataset import EpisodeExample, collate_episodes, normalize_action
from p37_neuro_ml.model import NeuroConfig, P37Neuro
from p37_neuro_ml.ppo import PPOBatch, PPOTrainer, sample_actions


def _example(identifier: str, joints: int, steps: int) -> EpisodeExample:
    specs = tuple(
        JointSpec(
            name=f"j{index}",
            joint_type=JointType.REVOLUTE,
            control_mode=ControlMode.POSITION,
            position=NumericRange(-2.0, 2.0),
            velocity_limit=3.0,
            effort_limit=20.0,
        )
        for index in range(joints)
    )
    embodiment = EmbodimentSpec(identifier, "arm", specs)
    trajectory = []
    for step in range(steps):
        position = {joint.name: 0.1 * step for joint in specs}
        velocity = {joint.name: 0.1 for joint in specs}
        action = {joint.name: 0.2 for joint in specs}
        trajectory.append(
            EpisodeStep(
                Observation(float(step), position, velocity),
                Action(float(step), action),
                reward=1.0,
                terminal=step == steps - 1,
            )
        )
    episode = Episode(identifier, identifier, "reach", tuple(trajectory), "test")
    return EpisodeExample(episode, embodiment)


def test_collate_episodes_pads_time_and_joints() -> None:
    batch = collate_episodes((_example("a", 2, 2), _example("b", 4, 3)))
    assert batch.joint_features.shape == (2, 4, 10)
    assert batch.joint_state.shape == (2, 3, 4, 2)
    assert batch.joint_mask.tolist() == [[True, True, False, False], [True] * 4]
    assert batch.time_mask.tolist() == [[True, True, False], [True, True, True]]
    assert batch.target_values[0, 0] > batch.target_values[0, 1]


def test_action_normalization() -> None:
    joint = _example("x", 1, 1).embodiment.joints[0]
    assert normalize_action(joint, 2.0) == 1.0
    assert normalize_action(joint, 0.0) == 0.0


def test_ppo_update_runs_on_padded_batch() -> None:
    data = collate_episodes((_example("a", 2, 2), _example("b", 4, 3)))
    config = NeuroConfig(model_dim=32, task_feature_dim=16, high_level_dim=8)
    model = P37Neuro(config)
    with torch.no_grad():
        output = model(
            joint_features=data.joint_features,
            joint_state=data.joint_state,
            joint_mask=data.joint_mask,
            time_mask=data.time_mask,
        )
        actions, log_prob = sample_actions(
            output.action_mean,
            output.action_log_std,
            joint_mask=data.joint_mask,
        )
    trainer = PPOTrainer(model)
    metrics = trainer.step(
        PPOBatch(
            joint_features=data.joint_features,
            joint_state=data.joint_state,
            joint_mask=data.joint_mask,
            time_mask=data.time_mask,
            actions=actions,
            old_log_prob=log_prob,
            advantages=torch.ones_like(log_prob),
            returns=data.target_values,
        )
    )
    assert torch.isfinite(torch.tensor(metrics.loss))
