"""Static contracts of the cross-body MuJoCo baseline (no MuJoCo dependency required)."""

from __future__ import annotations

from pathlib import Path


def _load_demo() -> object:
    path = Path(__file__).resolve().parents[1] / "scripts" / "mujoco_cross_body_demo.py"
    source = path.read_text(encoding="utf-8")
    compile(source, str(path), "exec")
    return source


def test_script_contains_only_a_baseline_controller() -> None:
    source = str(_load_demo())
    assert "analytic-ik-mujoco-position-servo" in source
    assert "policy_attached=False" in source
    assert 'evidence_level="T2"' in source
    assert "mujoco.mj_step(model, data)" in source


def test_two_morphologies_have_distinct_link_lengths() -> None:
    source = str(_load_demo())
    assert 'RobotConfig("compact-two-link", 0.45, 0.35)' in source
    assert 'RobotConfig("extended-two-link", 0.65, 0.55)' in source
