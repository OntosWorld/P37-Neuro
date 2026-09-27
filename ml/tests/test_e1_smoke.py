from pathlib import Path

from p37_neuro_ml.e1_smoke import run_e1_cpu_smoke


def test_e1_cpu_smoke_trains_one_checkpoint_across_morphologies(tmp_path: Path) -> None:
    result = run_e1_cpu_smoke(tmp_path, seed=11, epochs=8)

    assert result.train_joint_counts == (2, 3, 4, 5)
    assert result.heldout_joint_counts == (6, 7)
    assert result.final_train_action_mse < result.initial_train_action_mse
    assert result.final_heldout_action_mse >= 0.0
    assert tmp_path.joinpath("checkpoint", "manifest.json").is_file()
    assert tmp_path.joinpath("metrics.json").is_file()
