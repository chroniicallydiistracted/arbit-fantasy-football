"""Observed/documented Sleeper fields; upstream extensions remain intact."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Player(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
    player_id: str
    position: str | None = None
    sport: str | None = None
    fantasy_positions: list[str] | None = None
    espn_id: Any = None
    gsis_id: Any = None


class State(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
    season: str = Field(pattern=r"^20[0-9]{2}$")
    week: int | None = Field(default=None, strict=True, ge=0, le=25)
    season_type: str


class Trend(BaseModel):
    model_config = ConfigDict(extra="allow", hide_input_in_errors=True)
    player_id: str = Field(min_length=1, max_length=40)
    count: int = Field(strict=True, ge=0)
