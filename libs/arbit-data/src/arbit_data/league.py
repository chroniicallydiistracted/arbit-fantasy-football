"""Canonical, provider-independent FFA serving facts. Points are exact Decimal strings."""

import hashlib
import json
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from arbit_data.contracts import DataModel


def content_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class Manager(DataModel):
    id: UUID
    display_name: str
    first_name: str | None = Field(default=None, exclude_if=lambda value: value is None)


class FantasyTeam(DataModel):
    id: UUID
    name: str
    abbreviation: str
    managers: tuple[UUID, ...]
    primary_manager: UUID | None
    wins: int
    losses: int
    ties: int
    points_for: Decimal
    points_against: Decimal
    waiver_rank: int | None
    playoff_seed: int | None


class Player(DataModel):
    id: UUID
    kind: Literal["athlete", "defense_unit"]
    display_name: str
    position: Literal["QB", "RB", "WR", "TE", "K", "DST"]
    nfl_team_id: UUID | None
    eligible_slots: tuple[str, ...]
    active: bool
    injured: bool
    injury_status: str | None
    availability: Literal["owned", "free_agent", "waivers"]
    team_id: UUID | None
    lineup_slot: str | None
    lineup_locked: bool
    roster_locked: bool
    trade_locked: bool
    official_current_points: Decimal | None


class NflTeam(DataModel):
    id: UUID
    # Display metadata needs a separately verified NFL-team directory; never guess from a player name.


class MatchupSide(DataModel):
    team_id: UUID
    official_points: Decimal | None


class Matchup(DataModel):
    id: UUID
    matchup_period: int
    scoring_periods: tuple[int, ...]
    home: MatchupSide | None
    away: MatchupSide | None


class DraftPick(DataModel):
    overall: int
    round: int
    pick_in_round: int
    team_id: UUID
    player_id: UUID | None
    keeper: bool


class LeagueDocument(DataModel):
    format: Literal["ffa-league-v1"] = "ffa-league-v1"
    league_id: Literal["1729878439"] = "1729878439"
    season: int
    scoring_period: int
    matchup_period: int
    rules_hash: str
    managers: tuple[Manager, ...]
    teams: tuple[FantasyTeam, ...]
    nfl_teams: tuple[NflTeam, ...]
    players: tuple[Player, ...]
    matchups: tuple[Matchup, ...]
    draft_completed: bool
    draft_in_progress: bool
    draft_picks: tuple[DraftPick, ...]
    recommendations_enabled: Literal[False] = False

    @property
    def state_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))
