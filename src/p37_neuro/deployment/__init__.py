"""Deployment lifecycle management."""

from p37_neuro.deployment.fleet import (
    DeploymentTarget,
    RolloutHealth,
    RolloutPlan,
    build_rollback_plan,
    load_rollout_plan,
    rollout_ready,
    rollout_requires_rollback,
    write_rollout_plan,
)
from p37_neuro.deployment.qualification import (
    DeploymentQualificationError,
    VerifiedQualification,
    sha256_file,
    verify_qualification_for_deployment,
)

__all__ = [
    "DeploymentQualificationError",
    "DeploymentTarget",
    "RolloutHealth",
    "RolloutPlan",
    "VerifiedQualification",
    "build_rollback_plan",
    "load_rollout_plan",
    "rollout_ready",
    "rollout_requires_rollback",
    "sha256_file",
    "verify_qualification_for_deployment",
    "write_rollout_plan",
]
