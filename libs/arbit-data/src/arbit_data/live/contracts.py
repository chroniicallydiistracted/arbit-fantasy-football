from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class LiveModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


class Participant(LiveModel):
    espn_id: str
    role: str


class FieldPoint(LiveModel):
    yards_to_endzone: int | None = None
    team_id: str | None = None
    down: int | None = None
    source_down: str | None = None
    distance: int | None = None


PlayKind = Literal[
    "pass",
    "rush",
    "sneak",
    "sack",
    "interception",
    "field_goal",
    "pat",
    "two_point",
    "punt",
    "kickoff",
    "fumble",
    "penalty",
    "administrative",
    "unknown",
]


class LivePlay(LiveModel):
    event_id: str
    provider_id: str
    sequence: str | None
    provider_type_id: str | None
    provider_type_text: str
    kind: PlayKind
    text: str
    period: int | None
    clock: str | None
    home_score: str | None
    away_score: str | None
    scoring_play: bool | None
    score_value: str | None
    cancelled: bool
    modified_at: str | None
    wallclock: str | None
    participants: tuple[Participant, ...]
    start: FieldPoint
    end: FieldPoint
    can_connect_endpoints: bool
    effects: tuple[str, ...]
    point_after: dict[str, Any] | None
    stat_yardage: str | None
    source_flags: dict[str, bool | None]
    coordinate_basis: Literal["source_yards_to_endzone_separate_team_frames"] = (
        "source_yards_to_endzone_separate_team_frames"
    )


class TeamLine(LiveModel):
    color: str | None = None
    alternate_color: str | None = None
    record: str | None = None
    periods: tuple[str | None, ...] = ()


class LastPlay(LiveModel):
    provider_id: str | None = None
    kind_text: str | None = None
    text: str | None = None
    yards: int | None = None
    team_id: str | None = None
    home_win: float | None = None


class Situation(LiveModel):
    """ESPN's live game state. `yard_line` is measured from the home team's goal line."""

    down: int | None = None
    distance: int | None = None
    yard_line: int | None = None
    possession_team_id: str | None = None
    field_text: str | None = None
    short_text: str | None = None
    red_zone: bool | None = None
    home_timeouts: int | None = None
    away_timeouts: int | None = None
    last_play: LastPlay | None = None


class Venue(LiveModel):
    name: str | None = None
    city: str | None = None
    state: str | None = None
    indoor: bool | None = None


class Weather(LiveModel):
    temperature: int | None = None
    condition: str | None = None


class Leader(LiveModel):
    category: str
    athlete_id: str | None = None
    name: str | None = None
    team_id: str | None = None
    line: str | None = None


class LiveGame(LiveModel):
    event_id: str
    season: int
    date: str | None
    home_team_id: str
    away_team_id: str
    home_score: str | None
    away_score: str | None
    source_status: str
    phase: str
    completed: bool | None
    period: int | None
    clock: str | None
    neutral_site: bool | None
    status_detail: str | None = None
    home_line: TeamLine | None = None
    away_line: TeamLine | None = None
    situation: Situation | None = None
    venue: Venue | None = None
    weather: Weather | None = None
    broadcast: tuple[str, ...] = ()
    leaders: tuple[Leader, ...] = ()
    recommendations_enabled: Literal[False] = False
    fantasy_scoring: Literal["not_calculated; ESPN Fantasy remains authoritative"] = (
        "not_calculated; ESPN Fantasy remains authoritative"
    )
