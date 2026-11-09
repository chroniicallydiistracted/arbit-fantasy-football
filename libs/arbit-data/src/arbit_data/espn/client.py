"""Observed source capability checks for every registered read endpoint.

Source payloads remain inside the data layer. This is retrieval, not canonical
identity/rule normalization or proof of complete historical/live coverage.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.transport import EspnError, EspnTransport, SourceReceipt

Section = tuple[str, type]
VIEW_SECTIONS: dict[str, tuple[Section, ...]] = {
    "mSettings": (("settings.scoringSettings.scoringItems", list),),
    "mTeam": (("teams", list), ("members", list), ("teams.*.record", dict)),
    "mRoster": (("teams.*.roster.entries", list),),
    "mMatchupScore": (("schedule", list),),
    "mMatchup": (("schedule", list),),
    "mBoxscore": (("schedule", list),),
    "mLiveScoring": (("schedule", list),),
    "mScoreboard": (("schedule", list),),
    "mSchedule": (("schedule", list),),
    "mStandings": (("teams.*.record", dict),),
    "mDraftDetail": (("draftDetail.picks", list),),
    "mStatus": (("status", dict),),
    "mTransactions2": (("transactions", list),),
    "mPositionalRatings": (("positionAgainstOpponent.positionalRatings", dict),),
    "kona_player_info": (("players", list),),
    "kona_playercard": (("players", list), ("players.*.player.stats", list)),
    "proTeamSchedules_wl": (("proTeamSchedules", list),),
    "modular": (),
    "mNav": (),
}
SECTIONS: dict[Endpoint, tuple[Section, ...]] = {
    Endpoint.GAME: (("currentSeasonId", int),),
    Endpoint.SEASON: (("currentScoringPeriod", dict),),
    Endpoint.PRO_SCHEDULES: (("settings.proTeams", list),),
    Endpoint.PLAYER_NEWS: (("news.feed", list),),
    Endpoint.NFL_CORE_LEAGUE: (("id", str), ("athletes", dict), ("teams", dict)),
    Endpoint.NFL_CORE_ATHLETES: (
        ("count", int),
        ("items", list),
        ("pageIndex", int),
        ("pageCount", int),
    ),
    Endpoint.NFL_CORE_ATHLETE: (("id", str),),
    Endpoint.NFL_CORE_TEAMS: (
        ("count", int),
        ("items", list),
        ("pageIndex", int),
        ("pageCount", int),
    ),
    Endpoint.NFL_SCOREBOARD: (("events", list), ("leagues", list)),
    Endpoint.NFL_WEB_SCOREBOARD: (("events", list), ("leagues", list)),
    Endpoint.NFL_SUMMARY: (
        ("header", dict),
        ("boxscore", dict),
        ("drives.previous", list),
        ("scoringPlays", list),
    ),
    Endpoint.NFL_WEB_SUMMARY: (
        ("header", dict),
        ("boxscore", dict),
        ("drives.previous", list),
        ("scoringPlays", list),
    ),
    Endpoint.NFL_NEWS: (("articles", list),),
    Endpoint.NFL_STANDINGS: (("children", list),),
    Endpoint.NOW_NEWS: (("headlines", list),),
}


@dataclass(frozen=True)
class EndpointResponse:
    endpoint: Endpoint
    payload: dict[str, Any] | list[Any] | bytes = field(repr=False)
    receipt: SourceReceipt
    capability: Literal["available", "limited", "metadata_only"]
    missing_sections: tuple[str, ...]


def _section(payload: dict[str, Any], path: str, expected: type) -> bool:
    values: list[Any] = [payload]
    for part in path.split("."):
        next_values = []
        for value in values:
            if part == "*":
                if not isinstance(value, list):
                    raise EspnError("SCHEMA_DRIFT")
                next_values.extend(value)
            else:
                if not isinstance(value, dict):
                    raise EspnError("SCHEMA_DRIFT")
                if part not in value:
                    return False
                next_values.append(value[part])
        values = next_values
    if any(type(value) is not expected for value in values):
        raise EspnError("SCHEMA_DRIFT")
    return True


def _transaction_in_scope(transaction: dict[str, Any], period: int) -> bool:
    """A period's transactions, plus what ESPN was observed to list with them (2026-11-08):
    lineups already set for a later week (FUTURE_ROSTER) and a lineup move stamped period 0."""
    stamped, kind = transaction["scoringPeriodId"], transaction.get("type")
    return (
        stamped == period
        or (kind == "FUTURE_ROSTER" and stamped > period)
        or (kind == "ROSTER" and stamped == 0)
    )


def _scope(endpoint: Endpoint, options: EndpointOptions, payload: dict[str, Any]) -> None:
    if endpoint == Endpoint.LEAGUE:
        pool_only = bool(options.views) and set(options.views) <= {
            "kona_player_info",
            "kona_playercard",
        }
        if (not pool_only or "id" in payload) and (
            type(payload.get("id")) is not int or payload["id"] != 1729878439
        ):
            raise EspnError("SCOPE_MISMATCH")
        for key, expected in [
            ("seasonId", options.season),
            ("scoringPeriodId", options.scoring_period),
            ("segmentId", 0),
            ("gameId", 1),
        ]:
            if key in payload and (
                type(payload[key]) is not int or (expected is not None and payload[key] != expected)
            ):
                raise EspnError("SCOPE_MISMATCH")
        if "mTransactions2" in options.views and isinstance(payload.get("transactions"), list):
            for transaction in payload["transactions"]:
                if (
                    not isinstance(transaction, dict)
                    or type(transaction.get("scoringPeriodId")) is not int
                ):
                    raise EspnError("SCHEMA_DRIFT")
                if options.scoring_period is not None and not _transaction_in_scope(
                    transaction, options.scoring_period
                ):
                    raise EspnError("SCOPE_MISMATCH")
        if "kona_playercard" in options.views and options.fantasy_filter is not None:
            players_filter = options.fantasy_filter.get("players", {})
            ids = (
                players_filter.get("filterIds", {}).get("value")
                if isinstance(players_filter, dict)
                else None
            )
            if ids is not None and isinstance(payload.get("players"), list):
                actual = []
                for player in payload["players"]:
                    if not isinstance(player, dict) or type(player.get("id")) is not int:
                        raise EspnError("SCHEMA_DRIFT")
                    actual.append(player["id"])
                if set(actual) - set(ids):
                    raise EspnError("SCOPE_MISMATCH")
                if len(set(actual)) != len(actual) or set(actual) != set(ids):
                    raise EspnError("INCOMPLETE_RESPONSE")
    elif endpoint in (Endpoint.GAME, Endpoint.SEASON):
        expected = 1 if endpoint == Endpoint.GAME else options.season
        if type(payload.get("id")) is not int or payload["id"] != expected:
            raise EspnError("SCOPE_MISMATCH")
    elif endpoint == Endpoint.NFL_CORE_LEAGUE:
        if payload.get("id") != "28":
            raise EspnError("SCOPE_MISMATCH")
    elif endpoint in (Endpoint.NFL_CORE_ATHLETES, Endpoint.NFL_CORE_TEAMS):
        if (
            options.page is not None
            and "pageIndex" in payload
            and payload["pageIndex"] != options.page
        ):
            raise EspnError("SCOPE_MISMATCH")
    elif endpoint == Endpoint.NFL_CORE_ATHLETE:
        if payload.get("id") != str(options.player_id):
            raise EspnError("SCOPE_MISMATCH")
    elif endpoint in (Endpoint.NFL_SUMMARY, Endpoint.NFL_WEB_SUMMARY):
        header = payload.get("header")
        if isinstance(header, dict) and header.get("id") != options.event_id:
            raise EspnError("SCOPE_MISMATCH")


def _matchup_rosters(payload: dict[str, Any], options: EndpointOptions) -> bool:
    status = payload.get("status", {})
    period = options.matchup_period
    if period is None and isinstance(status, dict):
        period = status.get("requestedMatchupPeriodId", status.get("currentMatchupPeriod"))
    if type(period) is not int:
        return False
    schedule = payload.get("schedule")
    if not isinstance(schedule, list):
        return False
    selected = [
        matchup
        for matchup in schedule
        if isinstance(matchup, dict) and matchup.get("matchupPeriodId") == period
    ]
    if not selected:
        return False
    for matchup in selected:
        sides = [side for side in (matchup.get("home"), matchup.get("away")) if side is not None]
        if not sides:
            return False
        for side in sides:
            if not isinstance(side, dict):
                raise EspnError("SCHEMA_DRIFT")
            if not _section(side, "rosterForCurrentScoringPeriod.entries", list):
                return False
    return True


class EspnClient:
    def __init__(self, transport: EspnTransport):
        self._transport = transport

    def fetch(self, endpoint: Endpoint, options: EndpointOptions) -> EndpointResponse:
        fetched = self._transport.fetch(endpoint, options)
        payload = fetched.payload
        missing: tuple[str, ...] = ()
        capability: Literal["available", "limited", "metadata_only"] = "available"
        if isinstance(payload, dict):
            _scope(endpoint, options, payload)
            if endpoint == Endpoint.LEAGUE:
                sections = (
                    tuple(section for view in options.views for section in VIEW_SECTIONS[view])
                    if options.views
                    else (("teams", list), ("status", dict))
                )
                if options.views and set(options.views) <= {"modular", "mNav"}:
                    capability = "metadata_only"
            else:
                sections = SECTIONS.get(endpoint, ())
            if endpoint == Endpoint.LEAGUE and options.fantasy_filter is not None:
                player_filter = options.fantasy_filter.get("players", {})
                if (
                    isinstance(player_filter, dict)
                    and "filterRanksForScoringPeriodIds" in player_filter
                ):
                    sections += (("players.*.ratings", dict),)
            missing = tuple(
                dict.fromkeys(path for path, kind in sections if not _section(payload, path, kind))
            )
            if (
                endpoint == Endpoint.LEAGUE
                and "mBoxscore" in options.views
                and not _matchup_rosters(payload, options)
            ):
                missing += ("matchup_rosters",)
            if missing:
                capability = "limited"
        elif isinstance(payload, list):
            if any(
                not isinstance(player, dict) or type(player.get("id")) is not int
                for player in payload
            ):
                raise EspnError("SCHEMA_DRIFT")
        return EndpointResponse(endpoint, payload, fetched.receipt, capability, missing)
