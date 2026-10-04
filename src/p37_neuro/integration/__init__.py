"""Enterprise-facing robot integration interfaces."""

from p37_neuro.integration.adapter import AdapterHealth, RobotAdapter, validate_adapter
from p37_neuro.integration.kit import (
    IntegrationValidation,
    create_robot_manifest_template,
    validate_robot_integration,
)
from p37_neuro.integration.manifest import (
    AdapterCapabilities,
    EndEffectorMapping,
    JointMapping,
    JointSafetyOverride,
    ObservationMapping,
    RobotIntegrationManifest,
    RobotManifestError,
    SensorMapping,
    SensorRequirement,
    load_robot_manifest,
)
from p37_neuro.integration.simulate import (
    SimulationPreflightError,
    SimulationPreflightResult,
    run_mujoco_preflight,
)

__all__ = [
    "AdapterCapabilities",
    "AdapterHealth",
    "EndEffectorMapping",
    "IntegrationValidation",
    "JointMapping",
    "JointSafetyOverride",
    "ObservationMapping",
    "RobotAdapter",
    "RobotIntegrationManifest",
    "RobotManifestError",
    "SensorMapping",
    "SensorRequirement",
    "SimulationPreflightError",
    "SimulationPreflightResult",
    "create_robot_manifest_template",
    "load_robot_manifest",
    "run_mujoco_preflight",
    "validate_adapter",
    "validate_robot_integration",
]
