"""Validate once and preserve supplemental source content and authority labels."""

from typing import Any

from arbit_data.public_sources.repository import json_ready
from arbit_data.sleeper.contracts import Player, State, Trend


def normalize_sleeper(kind: str, payload: Any, *, season: int = 2026) -> dict[str, Any]:
    result = {
        "provider": "sleeper",
        "kind": kind,
        "usage": "supplemental",
        "attribution": "Sleeper",
        "ownership_authority": False,
        "recommendations_enabled": False,
        "data": json_ready(payload),
    }
    if kind == "sleeper.players":
        if not isinstance(payload, dict) or not payload or len(payload) > 100000:
            raise ValueError("INVALID_DIRECTORY")
        kinds = {}
        for key, raw in payload.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 40:
                raise ValueError("INVALID_DIRECTORY_ID")
            player = Player.model_validate(raw)
            if player.player_id != key:
                raise ValueError("MISMATCHED_DIRECTORY_ID")
            positions = set(player.fantasy_positions or []) | {player.position}
            kinds[key] = (
                "defense_unit"
                if "DEF" in positions and key.isalpha()
                else "athlete"
                if key.isascii()
                and key.isdigit()
                and not key.startswith("0")
                and player.sport in (None, "nfl")
                and "DEF" not in positions
                else "unknown"
            )
        result["entity_kinds"] = kinds
        result["count"] = len(payload)
    elif kind == "sleeper.state":
        state = State.model_validate(payload)
        result["season_matches_config"] = state.season == str(season)
        result["configured_season"] = season
    elif kind in ("sleeper.trending.add", "sleeper.trending.drop"):
        if not isinstance(payload, list) or len(payload) > 25:
            raise ValueError("INVALID_TRENDS")
        rows = [Trend.model_validate(row) for row in payload]
        if len({row.player_id for row in rows}) != len(rows):
            raise ValueError("DUPLICATE_TREND_ID")
        result["lookback_hours"] = 24
        result["activity"] = kind.rsplit(".", 1)[1]
        result["count"] = len(rows)
    elif kind in ("sleeper.stats.v1", "sleeper.stats.current"):
        if not isinstance(payload, dict if kind.endswith(".v1") else list) or len(payload) > 100000:
            raise ValueError("INVALID_CANDIDATE_STATS")
        result["usage"] = "candidate"
        result["ffa_scoring_verified"] = False
        result["scope_evidence"] = (
            "request_only" if isinstance(payload, dict) else "source_fields_unverified"
        )
        result["count"] = len(payload)
    else:
        raise ValueError("UNSUPPORTED_SLEEPER_RESOURCE")
    return result
