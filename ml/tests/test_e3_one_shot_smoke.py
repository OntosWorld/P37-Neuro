from pathlib import Path

from p37_neuro_ml.e3_one_shot_smoke import run_e3_cpu_smoke


def test_e3_one_shot_smoke_uses_one_demo_without_eval_updates(tmp_path: Path) -> None:
    result = run_e3_cpu_smoke(tmp_path, seed=23, epochs=12)

    assert result.training_tasks == 12
    assert result.heldout_tasks == 6
    assert result.heldout_embodiment_joints == 6
    assert result.qualifying_trials == 6
    assert result.final_train_action_mse < result.initial_train_action_mse
    assert result.final_heldout_action_mse >= 0.0
    assert 0.0 <= result.one_shot_success_rate <= 1.0
