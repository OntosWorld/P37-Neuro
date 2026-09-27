"""Model promotion and rollback state machine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReleaseChannel(StrEnum):
    CANDIDATE = "candidate"
    STAGING = "staging"
    PRODUCTION = "production"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class DeploymentRecord:
    artifact_id: str
    channel: ReleaseChannel = ReleaseChannel.CANDIDATE
    previous_artifact_id: str | None = None

    def promote_to_staging(self) -> None:
        if self.channel is not ReleaseChannel.CANDIDATE:
            raise ValueError("only candidate artifacts can enter staging")
        self.channel = ReleaseChannel.STAGING

    def promote_to_production(self, current_production: str | None) -> None:
        if self.channel is not ReleaseChannel.STAGING:
            raise ValueError("only staging artifacts can enter production")
        self.previous_artifact_id = current_production
        self.channel = ReleaseChannel.PRODUCTION

    def rollback(self) -> str:
        if self.channel is not ReleaseChannel.PRODUCTION or self.previous_artifact_id is None:
            raise ValueError("no production rollback target available")
        self.channel = ReleaseChannel.ROLLED_BACK
        return self.previous_artifact_id
