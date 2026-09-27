from pathlib import Path

from p37_neuro_ml.e5_ppo_smoke import run_e5_ppo_smoke


def test_e5_ppo_smoke_executes_real_policy_updates(tmp_path: Path) -> None:
    result = run_e5_ppo_smoke(tmp_path, seed=31, updates=8)

    assert result.environments == 32
    assert result.joints == 3
    assert -10.0 < result.initial_mean_reward < 2.0
    assert -10.0 < result.final_mean_reward < 2.0
    assert tmp_path.joinpath("checkpoint", "manifest.json").is_file()
