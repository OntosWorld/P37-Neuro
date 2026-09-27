from pathlib import Path

from p37_neuro_ml.e4_recovery_smoke import run_e4_recovery_smoke


def test_e4_recovery_smoke_exercises_chunked_recurrent_memory(tmp_path: Path) -> None:
    result = run_e4_recovery_smoke(tmp_path, seed=41, epochs=20)

    assert result.train_joint_counts == (3, 4)
    assert result.heldout_joint_count == 5
    assert result.recovery_mse_with_memory >= 0.0
    assert result.recovery_mse_after_memory_reset >= 0.0
    assert tmp_path.joinpath("checkpoint", "manifest.json").is_file()
