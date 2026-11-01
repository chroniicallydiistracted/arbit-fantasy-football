"""Observed ESPN boundary contracts. These IDs and scoring items remain provider facts."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from pydantic.alias_generators import to_camel

from arbit_data.espn.transport import SourceReceipt

PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class ProviderModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )


class SourceSettings(ProviderModel):
    # Preserve unknown settings/rule options for the later support report.
    model_config = ConfigDict(extra="allow")


class ScoringItem(SourceSettings):
    stat_id: StrictInt
    points: Decimal
    points_overrides: dict[str, Decimal]
    is_reverse_item: StrictBool


class ScoringSettings(SourceSettings):
    scoring_type: StrictStr
    scoring_items: Annotated[tuple[ScoringItem, ...], Field(min_length=1)]


class RosterSettings(SourceSettings):
    lineup_slot_counts: dict[str, NonNegativeInt]
    lineup_locktime_type: StrictStr


class LeagueSettings(SourceSettings):
    size: PositiveInt
    is_public: StrictBool
    scoring_settings: ScoringSettings
    roster_settings: RosterSettings
    draft_settings: dict[str, Any]
    acquisition_settings: dict[str, Any]
    schedule_settings: dict[str, Any]
    trade_settings: dict[str, Any]


class LeagueStatus(ProviderModel):
    first_scoring_period: PositiveInt
    final_scoring_period: PositiveInt
    latest_scoring_period: PositiveInt
    current_matchup_period: PositiveInt


class StatBlock(ProviderModel):
    season_id: StrictInt
    scoring_period_id: StrictInt
    stat_source_id: StrictInt
    stat_split_type_id: StrictInt
    stats: dict[str, Decimal] | None = None
    applied_total: Decimal | None = None
    applied_stats: dict[str, Decimal] | None = None


class Player(ProviderModel):
    id: StrictInt  # D/ST IDs are negative; never treat them as missing.
    full_name: StrictStr
    pro_team_id: StrictInt
    default_position_id: StrictInt
    eligible_slots: tuple[StrictInt, ...]
    active: StrictBool
    injured: StrictBool
    injury_status: StrictStr | None = None
    ownership: dict[str, Decimal | None] | None = None
    stats: tuple[StatBlock, ...]


class PoolEntry(ProviderModel):
    id: StrictInt
    on_team_id: NonNegativeInt
    status: StrictStr
    player: Player
    lineup_locked: StrictBool
    roster_locked: StrictBool
    trade_locked: StrictBool
    applied_stat_total: Decimal | None = None


class RosterEntry(ProviderModel):
    player_id: StrictInt
    lineup_slot_id: StrictInt
    player_pool_entry: PoolEntry


class Roster(ProviderModel):
    entries: tuple[RosterEntry, ...]


class OverallRecord(ProviderModel):
    wins: NonNegativeInt
    losses: NonNegativeInt
    ties: NonNegativeInt
    points_for: Decimal
    points_against: Decimal


class TeamRecord(ProviderModel):
    overall: OverallRecord


class Team(ProviderModel):
    id: PositiveInt
    name: StrictStr
    abbrev: StrictStr
    record: TeamRecord
    roster: Roster
    owners: tuple[StrictStr, ...] = ()
    primary_owner: StrictStr | None = None
    waiver_rank: PositiveInt | None = None
    playoff_seed: NonNegativeInt | None = None


class Member(ProviderModel):
    id: StrictStr
    display_name: StrictStr
    first_name: StrictStr | None = Field(default=None, exclude_if=lambda value: value is None)


class MatchupSide(ProviderModel):
    team_id: PositiveInt
    total_points: Decimal | None = None


class Matchup(ProviderModel):
    id: StrictInt
    matchup_period_id: PositiveInt
    home: MatchupSide | None = None
    away: MatchupSide | None = None  # Byes may have only one side.


class DraftPick(ProviderModel):
    id: StrictInt
    overall_pick_number: PositiveInt
    round_id: PositiveInt
    round_pick_number: PositiveInt
    team_id: PositiveInt
    player_id: StrictInt | None = None
    keeper: StrictBool


class DraftDetail(ProviderModel):
    drafted: StrictBool
    in_progress: StrictBool
    picks: tuple[DraftPick, ...]


class League(ProviderModel):
    id: StrictInt
    game_id: StrictInt
    season_id: StrictInt
    segment_id: StrictInt
    scoring_period_id: PositiveInt
    settings: LeagueSettings
    status: LeagueStatus
    teams: Annotated[tuple[Team, ...], Field(min_length=1)]
    schedule: tuple[Matchup, ...]
    draft_detail: DraftDetail
    members: tuple[Member, ...] = ()


class AvailablePage(ProviderModel):
    # kona_player_info intentionally has no league/season metadata envelope.
    players: tuple[PoolEntry, ...]


@dataclass(frozen=True)
class EspnAcquisition:
    league: League = field(repr=False)
    available: tuple[PoolEntry, ...] = field(repr=False)
    receipts: tuple[SourceReceipt, ...]
    capture_started_at: datetime
    capture_finished_at: datetime
