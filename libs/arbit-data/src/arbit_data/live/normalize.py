"""Parse explicit source facts; never follow references, name-match, or infer tracking."""

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from arbit_core.identity import require_aware

from arbit_data.live.contracts import (
    FieldPoint,
    LastPlay,
    Leader,
    LiveGame,
    LivePlay,
    Participant,
    PlayKind,
    PlayPenalty,
    PlayReview,
    Situation,
    TeamLine,
    Venue,
    Weather,
)
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
        yard_line=_bounded(raw.get("yardLine"), 0, 100),
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
    if "$ref" in raw:
        reference = raw["$ref"]
        if not isinstance(reference, str):
            raise ValueError("INVALID_PLAY_REFERENCE")
        parsed = urlsplit(reference)
        expected_path = (
            f"/v2/sports/football/leagues/nfl/events/{event_id}/competitions/{event_id}/plays/{pid}"
        )
        if (
            parsed.scheme not in ("http", "https")
            or parsed.netloc != "sports.core.api.espn.com"
            or parsed.path != expected_path
            or parsed.fragment
        ):
            raise ValueError("PLAY_REFERENCE_SCOPE_MISMATCH")

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
        yards_after_catch=_bounded(raw.get("yardsAfterCatch"), -120, 120),
        penalty=_lenient(_penalty, raw.get("penalty")) if raw.get("penalty") is not None else None,
        review=_lenient(_review, raw.get("review")) if raw.get("review") is not None else None,
    )


def _penalty(value: Any) -> PlayPenalty | None:
    raw = _dict(value)
    if not raw:
        return None
    kind, status = _dict(raw.get("type")), _dict(raw.get("status"))
    return PlayPenalty(
        slug=_text(kind.get("slug"), 64),
        text=_text(kind.get("text"), 128),
        yards=_bounded(raw.get("yards"), -120, 120),
        status=_text(status.get("slug"), 32),
    )


def _review(value: Any) -> PlayReview | None:
    raw = _dict(value)
    if not raw:
        return None
    upheld = raw.get("upheld")
    return PlayReview(
        type=_text(raw.get("type"), 32),
        upheld=upheld if isinstance(upheld, bool) else None,
    )


def _lenient[T](read: Callable[..., T], *args: Any) -> T | None:
    """Scoreboard extras must never cost the score: a shape change here only loses the extra."""
    try:
        return read(*args)
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        return None


def _bounded(value: Any, low: int, high: int) -> int | None:
    """ESPN uses out-of-range values such as a down of -1 for unknown. Unknown is not a number."""
    if value is None or isinstance(value, bool):
        return None
    number = Decimal(str(value))
    if number != number.to_integral_value() or not low <= number <= high:
        return None
    return int(number)


def _hex_color(value: Any) -> str | None:
    return (
        value.lower() if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{6}", value) else None
    )


def _team_line(competitor: dict[str, Any]) -> TeamLine:
    team = _dict(competitor.get("team"))
    overall = next(
        (
            _dict(r).get("summary")
            for r in _list(competitor.get("records"), 8)
            if _dict(r).get("type") == "total"
        ),
        None,
    )
    scores = (
        _bounded(_dict(p).get("value"), 0, 200) for p in _list(competitor.get("linescores"), 12)
    )
    periods = tuple(None if score is None else str(score) for score in scores)
    return TeamLine(
        color=_hex_color(team.get("color")),
        alternate_color=_hex_color(team.get("alternateColor")),
        record=_text(overall, 16),
        periods=periods,
    )


def _last_play(raw: dict[str, Any]) -> LastPlay:
    probability = _dict(raw.get("probability")).get("homeWinPercentage")
    return LastPlay(
        provider_id=_text(raw.get("id"), 40) if isinstance(raw.get("id"), str) else None,
        kind_text=_text(_dict(raw.get("type")).get("text"), 64),
        text=_text(raw.get("text"), 500),
        yards=_bounded(raw.get("statYardage"), -120, 120),
        team_id=_lenient(identifier, _dict(raw.get("team")).get("id")),
        home_win=round(float(probability), 4) if probability is not None else None,
    )


def _situation(value: Any) -> Situation | None:
    raw = _dict(value)
    if not raw:
        return None
    last_play = _dict(raw.get("lastPlay"))
    return Situation(
        down=_bounded(raw.get("down"), 1, 4),
        distance=_bounded(raw.get("distance"), 0, 120),
        yard_line=_bounded(raw.get("yardLine"), 0, 100),
        possession_team_id=_lenient(identifier, raw.get("possession")),
        field_text=_text(raw.get("possessionText"), 32),
        short_text=_text(raw.get("shortDownDistanceText"), 32),
        red_zone=_flag(raw.get("isRedZone")),
        home_timeouts=_bounded(raw.get("homeTimeouts"), 0, 3),
        away_timeouts=_bounded(raw.get("awayTimeouts"), 0, 3),
        last_play=_lenient(_last_play, last_play) if last_play else None,
    )


def _venue(value: Any) -> Venue | None:
    raw = _dict(value)
    if not raw:
        return None
    address = _dict(raw.get("address"))
    return Venue(
        name=_text(raw.get("fullName"), 128),
        city=_text(address.get("city"), 64),
        state=_text(address.get("state"), 32),
        indoor=_flag(raw.get("indoor")),
    )


def _weather(value: Any) -> Weather | None:
    raw = _dict(value)
    if not raw:
        return None
    # ESPN's condition text has been seen in either field, with a bare code in the other.
    words = [
        v
        for v in (raw.get("displayValue"), raw.get("conditionId"))
        if isinstance(v, str) and v and not v.isdigit()
    ]
    return Weather(
        temperature=_bounded(raw.get("temperature"), -60, 140),
        condition=_text(words[0], 64) if words else None,
    )


def _broadcast(value: Any) -> tuple[str, ...]:
    names = [
        n for b in _list(value, 8) for n in _list(_dict(b).get("names"), 8) if isinstance(n, str)
    ]
    return tuple(dict.fromkeys(names))[:4]


def _leaders(value: Any) -> tuple[Leader, ...]:
    found = []
    for category in _list(value, 12)[:6]:
        top = _list(_dict(category).get("leaders"), 12)
        short = _text(_dict(category).get("shortDisplayName"), 16)
        if not top or short not in ("PASS", "RUSH", "REC"):
            continue
        athlete = _dict(_dict(top[0]).get("athlete"))
        found.append(
            Leader(
                category=short,
                athlete_id=_lenient(identifier, athlete.get("id")),
                name=_text(athlete.get("shortName"), 64),
                team_id=_lenient(identifier, _dict(_dict(top[0]).get("team")).get("id")),
                line=_text(_dict(top[0]).get("displayValue"), 64),
            )
        )
    return tuple(found)


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
        status_detail=_lenient(_text, status_type.get("shortDetail"), 64),
        home_line=_lenient(_team_line, home),
        away_line=_lenient(_team_line, away),
        situation=_lenient(_situation, c.get("situation")),
        venue=_lenient(_venue, c.get("venue")),
        weather=_lenient(_weather, raw.get("weather") or c.get("weather")),
        broadcast=_lenient(_broadcast, c.get("broadcasts")) or (),
        leaders=_lenient(_leaders, c.get("leaders")) or (),
    )


def _drive(raw: dict[str, Any], current: bool) -> dict[str, Any]:
    return {
        "team_id": _lenient(identifier, _dict(raw.get("team")).get("id")),
        "result": _text(raw.get("displayResult"), 48),
        "plays": _bounded(raw.get("offensivePlays"), 0, 60),
        "yards": _bounded(raw.get("yards"), -120, 200),
        "elapsed": _text(_dict(raw.get("timeElapsed")).get("displayValue"), 16),
        "start": _text(_dict(raw.get("start")).get("text"), 32),
        "end": _text(_dict(raw.get("end")).get("text"), 32),
        "scored": _flag(raw.get("isScore")),
        "current": current,
    }


def _drives(value: Any) -> list[dict[str, Any]]:
    raw = _dict(value)
    finished = [_dict(d) for d in _list(raw.get("previous"), 100)]
    current = _dict(raw.get("current"))
    # ESPN lists the latest drive in both places. It is still running only if it has no result.
    running = bool(current) and not current.get("displayResult")
    drive_id = current.get("id")
    if running and drive_id is not None:
        finished = [d for d in finished if d.get("id") != drive_id]
    # ESPN also lists empty placeholders with no plays and no result, which are not drives.
    drives = [
        drive for drive in (_drive(d, False) for d in finished) if drive["plays"] or drive["result"]
    ]
    if (
        current
        and not running
        and (drive_id is None or all(d.get("id") != drive_id for d in finished))
    ):
        drives.append(_drive(current, False))
    return drives + ([_drive(current, True)] if running else [])


def _win_points(value: Any) -> list[dict[str, Any]]:
    points = []
    for item in _list(value, 600):
        value = _dict(item).get("homeWinPercentage")
        if value is not None:
            points.append(
                {"play_id": str(_dict(item).get("playId")), "home": round(float(value), 4)}
            )
    return points


def _team_stats(value: Any) -> list[dict[str, Any]]:
    raw = _dict(value)
    sides = {_dict(t).get("homeAway"): _dict(t) for t in _list(raw.get("teams"), 2)}
    home, away = (
        _list(sides["home"].get("statistics"), 60),
        _list(sides["away"].get("statistics"), 60),
    )
    other = {_dict(s).get("name"): _dict(s).get("displayValue") for s in away}
    rows: dict[str, dict[str, Any]] = {}
    for stat in home:
        name = _text(_dict(stat).get("name"), 48)
        if name and name not in rows:
            rows[name] = {
                "key": name,
                "label": _text(_dict(stat).get("label"), 64),
                "home": _text(_dict(stat).get("displayValue"), 16),
                "away": _text(other.get(name), 16),
            }
    return list(rows.values())


def normalize_summary_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """What a game page shows beyond the scoreboard. Each part can fail alone without the others."""
    return {
        "drives": _lenient(_drives, raw.get("drives")) or [],
        "win_probability": _lenient(_win_points, raw.get("winprobability")) or [],
        "team_stats": _lenient(_team_stats, raw.get("boxscore")) or [],
    }
