"""The NFL API live log (OWN-041): every request the NFL lanes make, for confirming the fastest
consistent route to each play.

One JSON line per request, appended to `ARBIT_NFL_API_LOG_PATH` (default `data/nfl-api/live-log`,
ignored by Git), one file per UTC day. Each line records the lane and route, the request's timing,
status and size, the response's cache headers (Varnish's Age, Cache-Control and hits), and what
the response says:
- **A week's summaries:** each game's offset, phase, quarter, clock, down, distance, possession and
  score.
- **A game record:** its play count, the newest play and its whistle time, and a short fingerprint
  of every play, so a correction to an earlier play shows.

Never a token or a request header: only the response's own headers listed in `KEPT_HEADERS`.
"""

import hashlib
import json
import os
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:12]


def summaries(payload: Any) -> dict[str, Any]:
    games = {}
    data = _mapping(payload).get("data")
    for game in _records(data):
        home, away = _mapping(game.get("homeTeam")), _mapping(game.get("awayTeam"))
        games[str(game.get("gameId"))] = {
            "offset": game.get("offset"),
            "phase": game.get("phase"),
            "quarter": game.get("quarter"),
            "clock": game.get("clock"),
            "down": game.get("down"),
            "distance": game.get("distance"),
            "yard_line": game.get("yardLine"),
            "possession": "home"
            if home.get("hasPossession")
            else "away"
            if away.get("hasPossession")
            else None,
            "score": [
                _mapping(away.get("score")).get("total"),
                _mapping(home.get("score")).get("total"),
            ],
            "fingerprint": fingerprint(game),
        }
    return {"games": games}


def plays(payload: Any) -> dict[str, Any]:
    """A game record's plays: from v2 (`driveChart.plays`) or v1 (`data.viewer.gameDetail.plays`)."""
    if isinstance(payload, list):  # the week's game records
        return {"games": {str(g["id"]): plays(g) for g in _records(payload) if g.get("id")}}
    game = _mapping(payload)
    chart = _mapping(game.get("driveChart"))
    detail = _mapping(_mapping(_mapping(game.get("data")).get("viewer")).get("gameDetail"))
    collection = chart.get("plays", detail.get("plays"))
    state = _mapping(game.get("summary")) or detail
    if not isinstance(collection, list):
        return {"phase": state.get("phase"), "offset": state.get("offset")}
    records = _records(collection)
    newest = max(
        records,
        key=lambda r: (
            _number(r.get("playSequenceNumber") or r.get("orderSequence")),
            _number(r.get("playId")),
        ),
        default=None,
    )
    return {
        "count": len(records),
        "newest": None
        if newest is None
        else {
            "play_id": newest.get("playId"),
            "type": newest.get("playType"),
            "snap_at": newest.get("playStartTime") or newest.get("timeOfDay"),
            "whistle_at": newest.get("playEndTime") or newest.get("endClockTime"),
            "clock": newest.get("clockTime"),
            "quarter": newest.get("quarter"),
            "latest_play": newest.get("latestPlay"),
            "play_clock": newest.get("playClock"),
            "review_status": newest.get("playReviewStatus"),
        },
        "newest_timed": _timed(records),
        "offset": state.get("offset"),
        "drive_offset": chart.get("offset"),
        "phase": state.get("phase"),
        "fingerprints": {
            str(r["playId"]): fingerprint(r) for r in records if r.get("playId") is not None
        },
        "whistles": {
            str(r["playId"]): whistle
            for r in records
            if r.get("playId") is not None and (whistle := _whistle(r))
        },
        "deleted": [str(r["playId"]) for r in records if r.get("playId") and r.get("playDeleted")],
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _records(value: Any) -> list[Mapping[str, Any]]:
    return (
        [record for record in value if isinstance(record, Mapping)]
        if isinstance(value, list)
        else []
    )


def _number(value: Any) -> int:
    return int(value) if str(value).isascii() and str(value).isdigit() else 0


def _whistle(record: Mapping[str, Any]) -> str | None:
    value = record.get("playEndTime") or record.get("endClockTime")
    return value if isinstance(value, str) and "T" in value else None


def _timed(records: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    """The newest play with a whistle time: the one whose delay to us can be measured."""
    timed = [(whistle, r) for r in records if (whistle := _whistle(r))]
    if not timed:
        return None
    whistle, newest = max(timed, key=lambda pair: pair[0])
    return {
        "play_id": newest.get("playId"),
        "whistle_at": whistle,
    }


class LiveLog:
    def __init__(
        self,
        root: Path | None = None,
        *,
        enabled: bool | None = None,
        on_problem: Callable[[str], None] = lambda _code: None,
    ):
        self.root = root or Path(os.environ.get("ARBIT_NFL_API_LOG_PATH", "data/nfl-api/live-log"))
        self.enabled = (
            enabled if enabled is not None else os.environ.get("ARBIT_NFL_API_LOG", "1") != "0"
        )
        self.on_problem = on_problem
        self.problem = False

    def request(self, lane: str, route: str, client: Any, **facts: Any) -> None:
        """Keep token renewals and rejected attempts as separate, metadata-only rows."""
        attempts = getattr(client, "attempts", ())
        for meta in attempts:
            if meta.get("path") == "/identity/v3/token" or meta is not client.last:
                self.write(
                    lane, "sign-in" if meta.get("path") == "/identity/v3/token" else route, meta
                )
        last = getattr(client, "last", {})
        if last.get("path") != "/identity/v3/token" or "error" in facts:
            self.write(
                lane, route, last if last.get("path") != "/identity/v3/token" else {}, **facts
            )

    def write(self, lane: str, route: str, meta: Mapping[str, Any], **facts: Any) -> None:
        if not self.enabled:
            return
        at = datetime.now(UTC)
        line = {"at": at.isoformat(), "lane": lane, "route": route, **dict(meta), **facts}
        path = self.root / f"{at.date().isoformat()}.jsonl"
        try:
            with _LOCK:
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(descriptor, "a", encoding="utf-8") as out:
                    if os.fstat(out.fileno()).st_mode & 0o077:
                        os.fchmod(out.fileno(), 0o600)
                    out.write(json.dumps(line, separators=(",", ":"), default=str) + "\n")
        except OSError:
            if not self.problem:
                self.on_problem("NFL_API_LOG_WRITE_FAILED")
            self.problem = True
        else:
            self.problem = False
