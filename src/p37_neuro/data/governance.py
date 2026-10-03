"""Enterprise data-governance policy for robot episodes and sensor data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from p37_neuro.data.schema import Episode


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class DataGovernancePolicy:
    customer_id: str
    site_id: str
    region: str
    classification: DataClassification = DataClassification.CONFIDENTIAL
    training_allowed: bool = False
    raw_sensor_retention_hours: int = 24
    contains_personal_data: bool = False
    allowed_purposes: tuple[str, ...] = ("evaluation",)

    def __post_init__(self) -> None:
        if not self.customer_id.strip() or not self.site_id.strip() or not self.region.strip():
            raise ValueError("customer_id, site_id and region are required")
        if self.raw_sensor_retention_hours < 0:
            raise ValueError("raw_sensor_retention_hours cannot be negative")
        if not self.allowed_purposes:
            raise ValueError("allowed_purposes cannot be empty")


@dataclass(frozen=True, slots=True)
class DataUseDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_data_use(
    policy: DataGovernancePolicy,
    *,
    purpose: str,
    destination_region: str | None = None,
) -> DataUseDecision:
    reasons: list[str] = []
    if purpose not in policy.allowed_purposes:
        reasons.append("purpose_not_allowed")
    if purpose == "training" and not policy.training_allowed:
        reasons.append("training_not_allowed")
    if destination_region is not None and destination_region != policy.region:
        reasons.append("cross_region_transfer_not_allowed")
    return DataUseDecision(allowed=not reasons, reasons=tuple(reasons))


def governance_metadata(policy: DataGovernancePolicy) -> dict[str, str]:
    return {
        "governance.customer_id": policy.customer_id,
        "governance.site_id": policy.site_id,
        "governance.region": policy.region,
        "governance.classification": policy.classification.value,
        "governance.training_allowed": str(policy.training_allowed).lower(),
        "governance.raw_sensor_retention_hours": str(policy.raw_sensor_retention_hours),
        "governance.contains_personal_data": str(policy.contains_personal_data).lower(),
        "governance.allowed_purposes": ",".join(policy.allowed_purposes),
    }


def policy_from_episode(episode: Episode) -> DataGovernancePolicy:
    metadata = episode.metadata
    prefix = "governance."
    required = ("customer_id", "site_id", "region")
    missing = [key for key in required if prefix + key not in metadata]
    if missing:
        raise ValueError(f"episode is missing governance metadata: {missing}")
    purposes = tuple(
        item.strip()
        for item in metadata.get(prefix + "allowed_purposes", "evaluation").split(",")
        if item.strip()
    )
    return DataGovernancePolicy(
        customer_id=metadata[prefix + "customer_id"],
        site_id=metadata[prefix + "site_id"],
        region=metadata[prefix + "region"],
        classification=DataClassification(
            metadata.get(prefix + "classification", DataClassification.CONFIDENTIAL.value)
        ),
        training_allowed=metadata.get(prefix + "training_allowed", "false").lower() == "true",
        raw_sensor_retention_hours=int(metadata.get(prefix + "raw_sensor_retention_hours", "24")),
        contains_personal_data=(
            metadata.get(prefix + "contains_personal_data", "false").lower() == "true"
        ),
        allowed_purposes=purposes,
    )


def require_episode_use(
    episode: Episode,
    *,
    purpose: str,
    destination_region: str | None = None,
) -> None:
    decision = evaluate_data_use(
        policy_from_episode(episode),
        purpose=purpose,
        destination_region=destination_region,
    )
    if not decision.allowed:
        raise PermissionError("episode use denied: " + ", ".join(decision.reasons))
