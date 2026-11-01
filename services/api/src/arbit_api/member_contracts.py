"""Executable member wire contract, exported to OpenAPI for the web client."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from arbit_data.league import Matchup, Player
from pydantic import BaseModel, ConfigDict, Field


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Problem(WireModel):
    type: str
    title: str
    status: int = Field(ge=400, le=599)
    detail: str
    instance: str
    code: str = Field(pattern=r"^[A-Z0-9_]{1,64}$")
    requestId: str = Field(pattern=r"^[a-f0-9]{32}$")
    error: str = Field(description="Compatibility alias of code")


class Preferences(WireModel):
    version: int = Field(ge=0)
    theme: Literal["system", "light", "dark"]
    watchlist: list[UUID] = Field(max_length=100)


class Account(WireModel):
    id: UUID
    role: Literal["member", "admin"]
    display_name: str


class Team(WireModel):
    id: UUID
    name: str
    abbreviation: str
    wins: int
    losses: int
    ties: int
    points_for: Decimal
    points_against: Decimal
    waiver_rank: int | None
    playoff_seed: int | None


class Me(WireModel):
    account: Account
    binding_status: Literal["bound", "pending"]
    team_id: UUID | None
    current_team_id: UUID | None
    teams: list[Team]
    season: int
    preferences: Preferences
    fixture: bool


class AuthStatus(WireModel):
    enabled: bool
    authenticated: bool
    csrf_token: str | None
    fixture: bool


class StartRequest(WireModel):
    invitation: str | None = Field(default=None, min_length=32, max_length=128)


class StartResponse(WireModel):
    authorization_url: str


class FixtureRequest(WireModel):
    member: Literal["one", "two"]


class Snapshot(WireModel):
    id: UUID
    observed_at: datetime
    source_status: Literal["fresh", "stale", "unavailable", "degraded"]
    stale: bool
    season: int
    scoring_period: int
    matchup_period: int


class Analysis(WireModel):
    status: Literal["unavailable"] = "unavailable"
    reason: str = "Model analysis is not available yet."


class FrontOffice(WireModel):
    snapshot: Snapshot
    team: Team
    matchup: Matchup | None
    roster: list[Player]
    standings: list[Team]
    analysis: Analysis = Field(default_factory=Analysis)
    matchup_periods: list[int]
    selected_matchup_period: int
    historical_roster_unavailable: bool
    fixture: bool


class Teams(WireModel):
    snapshot: Snapshot
    teams: list[Team]


class PlayerFacts(WireModel):
    snapshot: Snapshot
    player: Player
    analysis: Analysis = Field(default_factory=Analysis)


class PlayerSearch(WireModel):
    snapshot: Snapshot
    players: list[Player]


class InviteRequest(WireModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["member", "admin"] = "member"


class InviteResponse(WireModel):
    invitation_url: str


class BindingRequest(WireModel):
    account_id: UUID
    manager_id: UUID


class AdminAccount(Account):
    suspended: bool
    manager_ids: list[UUID]


class AdminManager(WireModel):
    id: UUID
    display_name: str
    team_ids: list[UUID]


class AdminDirectory(WireModel):
    accounts: list[AdminAccount]
    managers: list[AdminManager]


class ReactivateRequest(WireModel):
    account_id: UUID


class RevokeRequest(WireModel):
    account_id: UUID
    suspend: bool = False


class Success(WireModel):
    success: bool = True
