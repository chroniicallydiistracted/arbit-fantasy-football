from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LiveModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


class Participant(LiveModel):
    espn_id: str
    role: str


class MotionPerson(LiveModel):
    source_id: str
    espn_id: str | None = None
    team_id: str | None = None
    name: str | None = None
    jersey: str | None = None
    roles: tuple[str, ...]
    stat_types: tuple[int, ...]


class MotionEvidence(LiveModel):
    people: tuple[MotionPerson, ...] = ()
    numbered_text: str | None = None
    air_yards: int | None = None
    air_stat_type: Literal[111, 112] | None = None


def _absent(value: Any) -> bool:
    return value is None


class FieldPoint(LiveModel):
    yards_to_endzone: int | None = None
    team_id: str | None = None
    down: int | None = None
    source_down: str | None = None
    distance: int | None = None
    # ESPN's `yardLine`, counted from the home team's goal line. `yards_to_endzone` sometimes
    # repeats it instead of flipping it while the home team has the ball (ENG-033).
    yard_line: int | None = Field(default=None, exclude_if=_absent)


class PlayPenalty(LiveModel):
    slug: str | None = None
    text: str | None = None
    yards: int | None = None
    status: str | None = None


class PlayReview(LiveModel):
    type: str | None = None
    upheld: bool | None = None


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
    # Left out of the stored payload when ESPN doesn't send them, so such plays keep their hash.
    yards_after_catch: int | None = Field(default=None, exclude_if=_absent)
    penalty: PlayPenalty | None = Field(default=None, exclude_if=_absent)
    review: PlayReview | None = Field(default=None, exclude_if=_absent)
    # The NFL API's play record (OWN-041), when the play came from it rather than ESPN. Absent on
    # ESPN plays, so their stored hashes are unchanged.
    source: Literal["nfl"] | None = Field(default=None, exclude_if=_absent)
    snap_at: str | None = Field(default=None, exclude_if=_absent)  # UTC, the snap
    whistle_at: str | None = Field(default=None, exclude_if=_absent)  # UTC, the whistle
    clock_end: str | None = Field(default=None, exclude_if=_absent)  # the game clock at the whistle
    jerseys: dict[str, str] | None = Field(default=None, exclude_if=_absent)  # ESPN ID → number
    nfl: dict[str, Any] | None = Field(default=None, exclude_if=_absent)  # every field, as sent
    motion_evidence: MotionEvidence | None = Field(default=None, exclude_if=_absent)
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
