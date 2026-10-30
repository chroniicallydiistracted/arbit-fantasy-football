"""Normalized snapshot boundary; completeness is established by the provider adapter."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, Self
from uuid import UUID

from arbit_core.identity import require_aware
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RosterEntry(DataModel):
    entity_id: UUID
    team_id: UUID
    slot: str = Field(min_length=1)


class LeagueSnapshotCandidate(DataModel):
    league_id: Literal["1729878439"]
    season: int = Field(strict=True, ge=2026, le=2100)
    observed_at: datetime
    complete: bool = Field(strict=True)
    rules_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    teams: tuple[UUID, ...] = Field(min_length=1)
    roster: tuple[RosterEntry, ...]
    available: tuple[UUID, ...]

    @model_validator(mode="after")
    def valid_snapshot(self) -> Self:
        require_aware(self.observed_at)
        if len(set(self.teams)) != len(self.teams):
            raise ValueError("duplicate fantasy teams")
        owned = [entry.entity_id for entry in self.roster]
        if len(set(owned)) != len(owned):
            raise ValueError("duplicate player ownership")
        if any(entry.team_id not in self.teams for entry in self.roster):
            raise ValueError("roster references unknown fantasy team")
        if set(owned) & set(self.available):
            raise ValueError("owned player cannot be available")
        if len(set(self.available)) != len(self.available):
            raise ValueError("duplicate available player")
        return self

    @property
    def content_hash(self) -> str:
        payload = self.model_dump(mode="json")
        payload["observed_at"] = self.observed_at.astimezone(UTC).isoformat()
        # Provider ordering is not a league change. Normalize unordered collections.
        payload["teams"] = sorted(payload["teams"])
        payload["available"] = sorted(payload["available"])
        payload["roster"] = sorted(payload["roster"], key=lambda row: row["entity_id"])
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
