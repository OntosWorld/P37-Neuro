from pathlib import Path

import torch
from p37_neuro.data.schema import Action, Episode, EpisodeStep, Observation
from p37_neuro.data.storage import write_episode

from p37_neuro_ml.checkpoint import load_checkpoint
from p37_neuro_ml.experiment import evaluate_checkpoint, train_behavior_cloning
from p37_neuro_ml.export import RuntimeExportWrapper


def _write_fixture(root: Path) -> Path:
    robot = root / "arm.urdf"
    robot.write_text(
        '<robot name="arm"><joint name="j1" type="revolute">'
        '<limit lower="-1" upper="1" velocity="2" effort="3"/>'
        "</joint></robot>",
        encoding="utf-8",
    )

    observation = Observation(0.0, {"j1": 0.0}, {"j1": 0.0})
    episode = Episode(
        "episode-1",
        "arm",
        "reach",
        (
            EpisodeStep(
                observation,
                Action(0.0, {"j1": 0.25}),
                reward=1.0,
                terminal=True,
            ),
        ),
        "test",
    )
    episode_path = root / "episode.jsonl"
    write_episode(episode_path, episode)

    manifest = root / "experiment.yaml"
    manifest.write_text(
        "\n".join(
            (
                "schema_version: 1",
                "seed: 3",
                "epochs: 1",
                "batch_size: 1",
                "learning_rate: 0.001",
                "weight_decay: 0.0",
                "device: cpu",
                "output_dir: run",
                "model:",
                "  model_dim: 16",
                "  task_feature_dim: 8",
                "  high_level_dim: 4",
                "  transformer_heads: 4",
                "  transformer_layers: 1",
                "  temporal_layers: 1",
                "  context_length: 8",
                "  dropout: 0.0",
                "sources:",
                "  - robot: arm.urdf",
                "    episodes:",
                "      - episode.jsonl",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def test_behavior_cloning_manifest_runs_end_to_end(tmp_path: Path) -> None:
    manifest = _write_fixture(tmp_path)
    result = train_behavior_cloning(manifest)
    assert result.examples == 1
    assert result.checkpoint_dir.joinpath("manifest.json").is_file()

    metrics = evaluate_checkpoint(manifest, result.checkpoint_dir)
    assert metrics["examples"] == 1.0
    assert metrics["action_mse"] >= 0.0


def test_runtime_export_wrapper_has_stable_tensor_surface(tmp_path: Path) -> None:
    manifest = _write_fixture(tmp_path)
    result = train_behavior_cloning(manifest)
    model, _ = load_checkpoint(result.checkpoint_dir)
    wrapper = RuntimeExportWrapper(model)
    config = model.config

    action, high_level, value, memory = wrapper(
        torch.zeros(1, 1, config.joint_feature_dim),
        torch.zeros(1, 1, 1, config.joint_state_dim),
        torch.ones(1, 1, dtype=torch.bool),
        torch.zeros(1, 1, config.task_feature_dim),
        torch.zeros(1, 1, config.image_channels, 32, 32),
        torch.zeros(config.temporal_layers, 1, config.model_dim),
    )
    assert action.shape == (1, 1)
    assert high_level.shape == (1, config.high_level_dim)
    assert value.shape == (1,)
    assert memory.shape == (config.temporal_layers, 1, config.model_dim)
