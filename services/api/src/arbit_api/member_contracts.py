"""Executable member wire contract, exported to OpenAPI for the web client."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from arbit_data.league import Matchup, Player, TransactionCounts
from arbit_data.live.board import PlayBoard
from arbit_data.live.choreography import PlayScript
from arbit_data.live.motion import PlayScriptV2
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
    managers: list[str] = Field(description="First names ESPN lists, else display names")
    transactions: TransactionCounts | None


class TeamRef(WireModel):
    id: UUID
    name: str
    abbreviation: str


class Me(WireModel):
    account: Account
    binding_status: Literal["bound", "pending"]
    team_id: UUID | None
    current_team_id: UUID | None
    teams: list[Team]
    season: int
    preferences: Preferences
    fixture: bool
    # The read-only dev account: it sees every team and the administrator pages, and changes nothing.
    observer: bool


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
    confirmed_at: datetime | None = Field(
        default=None,
        description="When this content was last confirmed against ESPN; observed_at is when it first appeared.",
    )
    source_status: Literal["fresh", "stale", "unavailable", "degraded"]
    stale: bool
    season: int
    scoring_period: int
    matchup_period: int


class Analysis(WireModel):
    status: Literal["unavailable"] = "unavailable"
    reason: str = "Model analysis is not available yet."


class SeasonCell(WireModel):
    """One matchup period for the member's team. Points and result only once ESPN decides it."""

    matchup_period: int
    opponent_team_id: UUID | None
    own_points: Decimal | None
    opponent_points: Decimal | None
    result: Literal["win", "loss", "tie"] | None


class PlayerNfl(WireModel):
    """NFL context from ESPN's team directory for the snapshot's scoring period."""

    team_abbreviation: str
    team_name: str
    bye_week: int | None
    on_bye: bool
    opponent_abbreviation: str | None
    home: bool | None
    kickoff: datetime | None


class RosterPlayer(Player):
    nfl: PlayerNfl | None = None


class LineupPlayer(WireModel):
    """One player in a finished week's stored lineup: ESPN's slot and points for that week."""

    player_id: UUID
    display_name: str
    position: str
    slot: str
    official_points: Decimal | None


class LeagueRules(WireModel):
    """Settings from the stored rule version. Unknown stays null; nothing here is a default."""

    lineup_slots: list[str]
    waiver_type: str | None
    waiver_hours: int | None
    waiver_days: list[str]
    uses_bidding: bool | None
    trade_deadline: datetime | None
    trade_veto_votes: int | None
    trade_review_hours: int | None
    regular_season_matchups: int | None
    playoff_team_count: int | None
    playoff_tiebreaker: str | None


class MoveItem(WireModel):
    action: Literal["added", "dropped", "traded"]
    player_id: UUID
    player_name: str | None
    team_name: str | None = Field(description="The team that added, dropped or received him")


class RecentMove(WireModel):
    id: str
    at: datetime | None
    kind: Literal["waiver", "free_agent", "trade", "other"]
    team_name: str | None
    items: list[MoveItem]


class FrontOffice(WireModel):
    snapshot: Snapshot
    team: Team
    matchup: Matchup | None
    roster: list[RosterPlayer]
    roster_state: Literal["current", "lineup", "not_captured", "not_played"] = Field(
        description="current: today's roster; lineup: that week's stored lineup; "
        "not_captured: a finished week with no stored lineup; not_played: a future week"
    )
    lineup: list[LineupPlayer]
    lineup_captured_at: datetime | None
    standings: list[Team]
    analysis: Analysis = Field(default_factory=Analysis)
    matchup_periods: list[int]
    selected_matchup_period: int
    season_strip: list[SeasonCell]
    league: LeagueRules
    recent_moves: list[RecentMove]
    fixture: bool


class Teams(WireModel):
    snapshot: Snapshot
    teams: list[Team]


class PlayerFacts(WireModel):
    snapshot: Snapshot
    player: RosterPlayer
    owner: TeamRef | None = Field(description="The FFA team that rosters him, if any")
    analysis: Analysis = Field(default_factory=Analysis)


class PlayerSearch(WireModel):
    snapshot: Snapshot
    players: list[RosterPlayer]


class SourceRow(WireModel):
    source: str
    label: str
    state: Literal["current", "behind", "down", "idle", "never"]
    last_success_at: datetime | None
    error_code: str | None = Field(default=None, description="Administrators only")


class Sources(WireModel):
    sources: list[SourceRow]


class LiveTeam(WireModel):
    abbreviation: str | None
    name: str | None
    score: str | None
    color: str | None
    record: str | None
    periods: list[str | None]
    timeouts: int | None
    has_ball: bool


class LiveLastPlay(WireModel):
    kind: str | None
    text: str | None
    yards: int | None


class LiveSituation(WireModel):
    """`yard_line` and `first_down_line` run from the home goal line (0) to the away goal line (100)."""

    down: int | None
    distance: int | None
    short_text: str | None
    field_text: str | None
    yard_line: int | None
    first_down_line: int | None
    possession: Literal["home", "away"] | None
    red_zone: bool | None
    last_play: LiveLastPlay | None


class LiveVenue(WireModel):
    name: str | None
    city: str | None
    state: str | None
    indoor: bool | None


class LiveWeather(WireModel):
    temperature: int | None
    condition: str | None


class LiveGameRow(WireModel):
    event_id: str
    phase: str
    kickoff: datetime | None
    period: int | None
    clock: str | None
    home: LiveTeam
    away: LiveTeam
    situation: LiveSituation | None
    venue: LiveVenue | None
    weather: LiveWeather | None
    broadcast: list[str]
    own_players: list[str]
    observed_at: datetime
    changed_at: datetime


class LiveLeader(WireModel):
    category: str
    name: str | None
    team: str | None
    line: str | None


class LiveDrive(WireModel):
    team: str | None
    result: str | None
    plays: int | None
    yards: int | None
    elapsed: str | None
    start: str | None
    end: str | None
    scored: bool | None
    current: bool


class LiveWinPoint(WireModel):
    home: float


class LiveTeamStat(WireModel):
    key: str
    label: str | None
    home: str | None
    away: str | None


class LiveGameDetail(WireModel):
    game: LiveGameRow
    leaders: list[LiveLeader]
    drives: list[LiveDrive]
    win_probability: list[LiveWinPoint]
    team_stats: list[LiveTeamStat]
    summary_observed_at: datetime | None


class LiveGames(WireModel):
    week: int | None
    season_type: int | None
    games: list[LiveGameRow]
    source_state: Literal["current", "behind", "down", "idle", "never"]
    last_success_at: datetime | None


class LivePlayRow(WireModel):
    id: str
    period: int | None
    clock: str | None
    kind: str
    text: str
    home_score: str | None
    away_score: str | None
    scoring: bool
    cancelled: bool
    corrected: bool
    own: bool


class LivePlays(WireModel):
    game: LiveGameRow
    plays: list[LivePlayRow]
    plays_observed_at: datetime | None
    has_participants: bool


class LiveAnimationEntry(WireModel):
    """One play or try, drawn by the browser's live field (OWN-042)."""

    play_id: str
    part: Literal["play", "try"]
    period: int | None
    clock: str | None
    kind: str
    text: str
    cancelled: bool
    source: Literal["nfl", "espn"]  # the NFL API, or ESPN as the emergency fallback (OWN-041)
    snap_at: str | None
    whistle_at: str | None
    script: PlayScript | PlayScriptV2 | None
    board: PlayBoard | None


class LiveArt(WireModel):
    available: bool
    labels: dict[str, str | None]
    revision: str | None = None


class LiveAnimation(WireModel):
    event_id: str
    home: str
    away: str
    home_code: str
    away_code: str
    art: LiveArt
    entries: list[LiveAnimationEntry]


class DeviceSession(WireModel):
    id: UUID
    device: str | None
    created_at: datetime
    last_seen_at: datetime
    current: bool


class DeviceSessions(WireModel):
    sessions: list[DeviceSession]


class RevokeDevice(WireModel):
    session_id: UUID


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
    first_name: str | None = None
    team_ids: list[UUID]
    team_names: list[str] = Field(default_factory=list)


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
