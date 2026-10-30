"""Validated owner-confirmed context, without inferred league rules."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LeagueConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)

    league_id: Literal["1729878439"] = Field(alias="leagueId")
    season: int = Field(ge=2026, le=2100)
    provider: Literal["espn"]
    league_name: str = Field(alias="leagueName", min_length=1)
    abbreviation: Literal["FFA"]
    deployment_preference: Literal["portable-local-first"] = Field(alias="deploymentPreference")


def load_league_config(path: Path) -> LeagueConfig:
    return LeagueConfig.model_validate_json(path.read_bytes())
