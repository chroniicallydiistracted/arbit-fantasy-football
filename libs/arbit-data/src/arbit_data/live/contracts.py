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
    recommendations_enabled: Literal[False] = False
    fantasy_scoring: Literal["not_calculated; ESPN Fantasy remains authoritative"] = (
        "not_calculated; ESPN Fantasy remains authoritative"
    )
