from pathlib import Path

from p37_neuro.integration import validate_robot_integration


def test_reference_robot_integrations_validate() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("tabletop_arm", "mobile_manipulator", "quadruped"):
        result = validate_robot_integration(root / "examples" / name / "robot.yaml")
        assert result.action_dimension > 0
        assert result.control_frequency_hz > 0
        assert "safety_profile" in result.checks
