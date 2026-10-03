from pathlib import Path

import pytest

from p37_neuro.integration import SimulationPreflightError, run_mujoco_preflight


def test_mujoco_preflight_requires_mjcf_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(SimulationPreflightError, match="requires an MJCF"):
        run_mujoco_preflight(root / "examples" / "tabletop_arm" / "robot.yaml")
