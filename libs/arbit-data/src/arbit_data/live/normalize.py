"""Parse explicit source facts; never follow references, name-match, or infer tracking."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from arbit_core.identity import require_aware

from arbit_data.live.contracts import FieldPoint, LiveGame, LivePlay, Participant, PlayKind
from arbit_data.public_sources.repository import json_ready


def _dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("INVALID_OBJECT")
    return value


def _list(value: Any, maximum: int = 6000) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("INVALID_ARRAY")
    return value


def identifier(value: Any) -> str:
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,39}", str(value)):
        raise ValueError("INVALID_SOURCE_ID")
    return str(value)


def _integer(value: Any, maximum: int) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or len(str(value)) > 32:
        raise ValueError("INVALID_INTEGER")
    try:
        number = Decimal(str(value))
        if (
            not number.is_finite()
            or number != number.to_integral_value()
            or not 0 <= number <= maximum
        ):
            raise ValueError("INVALID_INTEGER")
        return int(number)
    except InvalidOperation:
        raise ValueError("INVALID_INTEGER") from None


def _number(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or len(str(value)) > 32:
        raise ValueError("INVALID_NUMBER")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > 1000000:
            raise ValueError("INVALID_NUMBER")
    except InvalidOperation:
        raise ValueError("INVALID_NUMBER") from None
    return str(value)


def _flag(value: Any) -> bool | None:
    if value is not None and type(value) is not bool:
        raise ValueError("INVALID_FLAG")
    return value


def _text(value: Any, limit: int = 8192) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("INVALID_TEXT")
    return value


def reference_id(reference: Any, category: str, season: int, event_id: str) -> str:
    if not isinstance(reference, str):
        raise ValueError("INVALID_REFERENCE")
    u = urlsplit(reference)
    if u.scheme not in ("http", "https") or u.netloc != "sports.core.api.espn.com" or u.fragment:
        raise ValueError("INVALID_REFERENCE")
    base = r"/v2/sports/football/leagues/nfl"
    pattern = base + rf"/seasons/{season}/{category}/([1-9][0-9]{{0,19}})"
    match = re.fullmatch(pattern, u.path)
    if match is None and category == "teams":
        match = re.fullmatch(
            base + rf"/events/{event_id}/competitions/{event_id}/competitors/([1-9][0-9]{{0,19}})",
            u.path,
        )
    if match is None:
        raise ValueError("INVALID_REFERENCE")
    return match.group(1)


def _team(raw: Any, season: int, event_id: str) -> str | None:
    if not isinstance(raw, dict):
        return None
    direct = identifier(raw["id"]) if raw.get("id") is not None else None
    referenced = reference_id(raw["$ref"], "teams", season, event_id) if "$ref" in raw else None
    if direct and referenced and direct != referenced:
        raise ValueError("CONTRADICTORY_TEAM_ID")
    return direct or referenced


def _point(raw: Any, season: int, event_id: str) -> FieldPoint:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("INVALID_FIELD_POINT")
    return FieldPoint(
        yards_to_endzone=_integer(raw.get("yardsToEndzone"), 100),
        team_id=_team(raw.get("team"), season, event_id),
        down=None if raw.get("down") in (-1, "-1") else _integer(raw.get("down"), 4),
        source_down=_number(raw.get("down")),
        distance=_integer(raw.get("distance"), 100),
    )


def _kind(label: str, text: str) -> PlayKind:
    label = label.casefold()
    if label in ("pass reception", "pass incompletion", "passing touchdown", "pass completion"):
        return "pass"
    if label in ("rush", "rushing touchdown"):
        return "sneak" if re.search(r"\bsneak\b", text, re.I) else "rush"
    if label == "sack":
        return "sack"
    if "interception" in label:
        return "interception"
    if "field goal" in label:
        return "field_goal"
    if "extra point" in label or label == "pat":
        return "pat"
    if "two point" in label or "two-point" in label:
        return "two_point"
    if "fumble" in label:
        return "fumble"
    if "punt" in label:
        return "punt"
    if "kickoff" in label or "kick off" in label:
        return "kickoff"
    if label in ("penalty", "no play"):
        return "penalty"
    if label in (
        "end period",
        "end of game",
        "end of half",
        "timeout",
        "official timeout",
        "two-minute warning",
    ):
        return "administrative"
    return "unknown"


def normalize_play(raw: dict[str, Any], event_id: str, season: int) -> LivePlay:
    event_id = identifier(event_id)
    pid = identifier(raw.get("id"))
    sequence = raw.get("sequenceNumber")
    if sequence is not None:
        if len(str(sequence)) > 64:
            raise ValueError("INVALID_SEQUENCE")
        try:
            n = Decimal(str(sequence))
            if not n.is_finite() or not 0 <= n <= Decimal("1e30"):
                raise ValueError("INVALID_SEQUENCE")
        except InvalidOperation:
            raise ValueError("INVALID_SEQUENCE") from None
        sequence = str(sequence)
    kind_data = _dict(raw.get("type"))
    label = _text(kind_data.get("text"), 128) or "Unknown"
    text = _text(raw.get("text")) or ""
    kind = _kind(label, text)
    participants = []
    for value in _list(raw.get("participants"), 100):
        person = _dict(value)
        athlete = _dict(person.get("athlete"))
        direct = identifier(athlete["id"]) if athlete.get("id") is not None else None
        referenced = (
            reference_id(athlete["$ref"], "athletes", season, event_id)
            if "$ref" in athlete
            else None
        )
        if direct and referenced and direct != referenced:
            raise ValueError("CONTRADICTORY_ATHLETE_ID")
        if direct or referenced:
            participants.append(
                Participant(
                    espn_id=direct or referenced or "",
                    role=_text(person.get("type"), 128) or "unknown",
                )
            )
    start = _point(raw.get("start"), season, event_id)
    end = _point(raw.get("end"), season, event_id)
    turnover = _flag(raw.get("isTurnover"))
    penalty = _flag(raw.get("isPenalty"))
    effects: set[str] = {kind}
    if turnover:
        effects.add("turnover")
    if penalty:
        effects.add("penalty")
    point_after = raw.get("pointAfterAttempt")
    if point_after is not None:
        if not isinstance(point_after, dict):
            raise ValueError("INVALID_POINT_AFTER")
        effects.add("two_point" if "two" in str(point_after.get("text", "")).casefold() else "pat")
    modified = _text(raw.get("modified"), 64)
    if modified is not None:
        require_aware(datetime.fromisoformat(modified.replace("Z", "+00:00")))
    return LivePlay(
        event_id=event_id,
        provider_id=pid,
        sequence=sequence,
        provider_type_id=str(kind_data["id"]) if kind_data.get("id") is not None else None,
        provider_type_text=label,
        kind=kind,
        text=text,
        period=_integer(_dict(raw.get("period")).get("number"), 20),
        clock=_text(_dict(raw.get("clock")).get("displayValue"), 32),
        home_score=_number(raw.get("homeScore")),
        away_score=_number(raw.get("awayScore")),
        scoring_play=_flag(raw.get("scoringPlay")),
        score_value=_number(raw.get("scoreValue")),
        cancelled=label.casefold() == "no play" or bool(re.search(r"\bno play\b", text, re.I)),
        modified_at=modified,
        wallclock=_text(raw.get("wallclock"), 64),
        participants=tuple(participants),
        start=start,
        end=end,
        can_connect_endpoints=turnover is False
        and kind in ("pass", "rush", "sneak", "sack")
        and start.team_id is not None
        and start.team_id == end.team_id
        and start.yards_to_endzone is not None
        and end.yards_to_endzone is not None,
        effects=tuple(sorted(effects)),
        point_after=json_ready(point_after),
        stat_yardage=_number(raw.get("statYardage")),
        source_flags={"isTurnover": turnover, "isPenalty": penalty},
    )


def normalize_game(raw: dict[str, Any], season: int) -> LiveGame:
    event_id = identifier(raw.get("id"))
    if _dict(raw.get("season")).get("year") != season:
        raise ValueError("SEASON_MISMATCH")
    competitions = raw.get("competitions")
    if not isinstance(competitions, list) or len(competitions) != 1:
        raise ValueError("INVALID_COMPETITION")
    c = _dict(competitions[0])
    if str(c.get("id")) != event_id:
        raise ValueError("EVENT_SCOPE_MISMATCH")
    competitors = [_dict(x) for x in _list(c.get("competitors"), 2)]
    if len(competitors) != 2 or {x.get("homeAway") for x in competitors} != {"home", "away"}:
        raise ValueError("INVALID_COMPETITORS")
    home = next(x for x in competitors if x["homeAway"] == "home")
    away = next(x for x in competitors if x["homeAway"] == "away")
    status = _dict(c.get("status") or raw.get("status"))
    status_type = _dict(status.get("type"))
    name = _text(status_type.get("name"), 128) or "UNKNOWN"
    period = _integer(status.get("period"), 20)
    completed = _flag(status_type.get("completed"))
    if "POSTPON" in name:
        phase = "postponed"
    elif "CANCEL" in name:
        phase = "cancelled"
    elif "DELAY" in name:
        phase = "delayed"
    elif "HALFTIME" in name:
        phase = "halftime"
    elif completed is True or status_type.get("state") == "post":
        phase = "final"
    elif status_type.get("state") == "in":
        phase = "overtime" if period is not None and period > 4 else "in_progress"
    elif status_type.get("state") == "pre":
        phase = "scheduled"
    else:
        phase = "unknown"
    return LiveGame(
        event_id=event_id,
        season=season,
        date=_text(c.get("date") or raw.get("date"), 64),
        home_team_id=identifier(home.get("id")),
        away_team_id=identifier(away.get("id")),
        home_score=_number(home.get("score")),
        away_score=_number(away.get("score")),
        source_status=name,
        phase=phase,
        completed=completed,
        period=period,
        clock=_text(status.get("displayClock"), 32),
        neutral_site=_flag(c.get("neutralSite")),
    )
