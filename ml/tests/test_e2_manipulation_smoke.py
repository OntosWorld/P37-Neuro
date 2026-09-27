from pathlib import Path

from p37_neuro_ml.e2_manipulation_smoke import run_e2_cpu_smoke


def test_e2_manipulation_smoke_trains_across_arm_dofs(tmp_path: Path) -> None:
    result = run_e2_cpu_smoke(tmp_path, seed=19, epochs=10)

    assert result.train_joint_counts == (3, 4, 5)
    assert result.heldout_joint_counts == (6, 7)
    assert result.final_train_action_mse < result.initial_train_action_mse
    assert result.final_heldout_action_mse >= 0.0
    assert 0.0 <= result.heldout_success_rate <= 1.0
    assert tmp_path.joinpath("checkpoint", "manifest.json").is_file()
