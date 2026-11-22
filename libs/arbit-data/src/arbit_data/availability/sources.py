"""NFL's weekly injury report (OWN-063): each player's game status and practice participation.

Read from `api.nfl.com` (`/football/v2/injuries`) through the Live lane's `NflApiClient`, paged
with `pageToken`. Its week and team filters are ignored, so the whole season's report is read.
Only status is read: the response has no projection, ranking or odds field.

Game-day inactives come from ESPN's fantasy injury status instead (OWN-064,
`arbit_data.availability.espn_status`). NFL's API has no inactive designation, and the owner
chose ESPN over NFL Next Gen Stats (Q-015).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from arbit_data.errors import SourceError

INJURY_PAGE = 1000
MAX_INJURY_PAGES = 20


class JsonGetter(Protocol):
    def get(self, path: str, params: Mapping[str, Any] | None = None) -> tuple[Any, bytes]: ...


@dataclass(frozen=True)
class Response:
    source: str
    path: str
    params: dict[str, Any]
    body: bytes


def read_injury_report(
    nfl: JsonGetter, season: int, season_type: str
) -> tuple[list[dict[str, Any]], list[Response]]:
    """Every row of the season's injury report, following `pageToken` to the last page."""
    rows: list[dict[str, Any]] = []
    responses: list[Response] = []
    token: str | None = None
    seen: set[str] = set()
    for _ in range(MAX_INJURY_PAGES):
        params: dict[str, Any] = {"season": season, "seasonType": season_type, "limit": INJURY_PAGE}
        if token:
            params["pageToken"] = token
        body, raw = nfl.get("/football/v2/injuries", params)
        responses.append(Response("nfl.injuries", "/football/v2/injuries", params, raw))
        batch = body.get("injuries") if isinstance(body, dict) else None
        if not isinstance(batch, list):
            raise SourceError("NFL_INJURIES_SHAPE")
        rows.extend(batch)
        token = ((body.get("pagination") or {}).get("token")) or None
        if len(batch) < INJURY_PAGE or token is None:
            return rows, responses
        if token in seen:
            raise SourceError("NFL_INJURIES_PAGING")
        seen.add(token)
    raise SourceError("NFL_INJURIES_TOO_MANY_PAGES")


@dataclass(frozen=True)
class GameStatus:
    """One player's line on a week's injury report."""

    season: int
    season_type: str
    week: int
    team_name: str | None
    nfl_team_id: str | None
    gsis_id: str | None
    nfl_person_id: str | None
    name: str | None
    position: str | None
    game_status: str | None  # OUT, DOUBTFUL, QUESTIONABLE; None when the report gives none
    practice_status: str | None
    practice_days: tuple[tuple[str, str], ...]
    injuries: tuple[str, ...]


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def game_statuses(rows: Sequence[Mapping[str, Any]]) -> list[GameStatus]:
    out = []
    for row in rows:
        team = row.get("team") or {}
        person = row.get("person") or {}
        days = tuple(
            (str(d.get("date")), str(d.get("status")))
            for d in row.get("practiceDays") or []
            if isinstance(d, Mapping) and d.get("date")
        )
        out.append(
            GameStatus(
                season=int(row["season"]),
                season_type=str(row.get("seasonType") or "REG"),
                week=int(row["week"]),
                team_name=_text(team.get("fullName")),
                nfl_team_id=_text(team.get("id")),
                gsis_id=_text(person.get("gsisId")),
                nfl_person_id=_text(person.get("id")),
                name=_text(person.get("displayName")),
                position=_text(row.get("position")),
                game_status=_text(row.get("injuryStatus")),
                practice_status=_text(row.get("practiceStatus")),
                practice_days=days,
                injuries=tuple(str(i) for i in row.get("injuries") or []),
            )
        )
    return out
