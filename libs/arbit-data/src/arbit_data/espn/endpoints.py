"""Explicit, read-only ESPN routes observed by the public endpoint audit."""

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

LM = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
SITE = "https://site.api.espn.com"
WEB = "https://site.web.api.espn.com"
CDN = "https://a.espncdn.com"
VIEWS = frozenset(
    {
        "mSettings",
        "mTeam",
        "mRoster",
        "mMatchupScore",
        "mMatchup",
        "mScoreboard",
        "mStandings",
        "mSchedule",
        "mBoxscore",
        "mLiveScoring",
        "mDraftDetail",
        "mTransactions2",
        "mStatus",
        "mPositionalRatings",
        "kona_player_info",
        "kona_playercard",
        "modular",
        "mNav",
        "proTeamSchedules_wl",
    }
)


class Endpoint(StrEnum):
    LEAGUE = "league"
    GAME = "game"
    SEASON = "season"
    PRO_SCHEDULES = "pro_schedules"
    PLAYER_DIRECTORY = "player_directory"
    PLAYER_NEWS = "player_news"
    NFL_CORE_LEAGUE = "nfl_core_league"
    NFL_CORE_ATHLETES = "nfl_core_athletes"
    NFL_CORE_ATHLETE = "nfl_core_athlete"
    NFL_CORE_TEAMS = "nfl_core_teams"
    NFL_SCOREBOARD = "nfl_scoreboard"
    NFL_WEB_SCOREBOARD = "nfl_web_scoreboard"
    NFL_SUMMARY = "nfl_summary"
    NFL_WEB_SUMMARY = "nfl_web_summary"
    NFL_NEWS = "nfl_news"
    NFL_STANDINGS = "nfl_standings"
    NOW_NEWS = "now_news"
    HEADSHOT = "headshot"
    TEAM_LOGO = "team_logo"


class EndpointOptions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)
    season: Annotated[int, Field(ge=2026, le=2100)] | None = None
    views: tuple[str, ...] = ()
    scoring_period: Annotated[int, Field(ge=1, le=99)] | None = None
    matchup_period: Annotated[int, Field(ge=1, le=99)] | None = None
    player_id: Annotated[int, Field(gt=0)] | None = None
    event_id: Annotated[str, Field(pattern=r"^[1-9][0-9]{0,19}$")] | None = None
    team_abbrev: Annotated[str, Field(pattern=r"^[a-z]{2,4}$")] | None = None
    limit: Annotated[int, Field(ge=1, le=300)] | None = None
    page: Annotated[int, Field(ge=1, le=100000)] | None = None
    sport: Literal["football"] | None = None
    fantasy_filter: dict[str, Any] | None = None


@dataclass(frozen=True)
class Route:
    path: str
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()
    response_format: Literal["object", "array", "png"] = "object"


ROUTES = {
    Endpoint.LEAGUE: Route(
        LM + "/seasons/{season}/segments/0/leagues/1729878439",
        frozenset({"season"}),
        frozenset({"views", "scoring_period", "matchup_period", "fantasy_filter"}),
    ),
    Endpoint.GAME: Route(LM),
    Endpoint.SEASON: Route(LM + "/seasons/{season}", frozenset({"season"})),
    Endpoint.PRO_SCHEDULES: Route(LM + "/seasons/{season}", frozenset({"season"})),
    Endpoint.PLAYER_DIRECTORY: Route(
        LM + "/seasons/{season}/players",
        frozenset({"season"}),
        frozenset({"fantasy_filter"}),
        "array",
    ),
    Endpoint.PLAYER_NEWS: Route(
        SITE + "/apis/fantasy/v3/games/ffl/news/players",
        frozenset({"player_id"}),
        frozenset({"season"}),
    ),
    Endpoint.NFL_CORE_LEAGUE: Route(CORE),
    Endpoint.NFL_CORE_ATHLETES: Route(
        CORE + "/athletes", frozenset(), frozenset({"limit", "page"})
    ),
    Endpoint.NFL_CORE_ATHLETE: Route(
        CORE + "/seasons/{season}/athletes/{player_id}", frozenset({"season", "player_id"})
    ),
    Endpoint.NFL_CORE_TEAMS: Route(
        CORE + "/seasons/{season}/teams", frozenset({"season"}), frozenset({"limit", "page"})
    ),
    Endpoint.NFL_SCOREBOARD: Route(SITE + "/apis/site/v2/sports/football/nfl/scoreboard"),
    Endpoint.NFL_WEB_SCOREBOARD: Route(WEB + "/apis/site/v2/sports/football/nfl/scoreboard"),
    Endpoint.NFL_SUMMARY: Route(
        SITE + "/apis/site/v2/sports/football/nfl/summary", frozenset({"event_id"})
    ),
    Endpoint.NFL_WEB_SUMMARY: Route(
        WEB + "/apis/site/v2/sports/football/nfl/summary", frozenset({"event_id"})
    ),
    Endpoint.NFL_NEWS: Route(SITE + "/apis/site/v2/sports/football/nfl/news"),
    Endpoint.NFL_STANDINGS: Route(SITE + "/apis/v2/sports/football/nfl/standings"),
    Endpoint.NOW_NEWS: Route(
        "https://now.core.api.espn.com/v1/sports/news", frozenset(), frozenset({"sport"})
    ),
    Endpoint.HEADSHOT: Route(
        CDN + "/i/headshots/nfl/players/full/{player_id}.png",
        frozenset({"player_id"}),
        response_format="png",
    ),
    Endpoint.TEAM_LOGO: Route(
        CDN + "/combiner/i", frozenset({"team_abbrev"}), response_format="png"
    ),
}


@dataclass(frozen=True)
class EndpointRequest:
    endpoint: Endpoint
    options: EndpointOptions
    url: str
    response_format: Literal["object", "array", "png"]
    fantasy_filter: str | None


def build_request(endpoint: Endpoint, options: EndpointOptions) -> EndpointRequest:
    endpoint = Endpoint(endpoint)
    # Revalidate model_copy/construct inputs too; a frozen wrapper is not a trust boundary.
    options = EndpointOptions.model_validate(options.model_dump())
    route = ROUTES[endpoint]
    supplied = {
        name for name, value in options.model_dump().items() if value is not None and value != ()
    }
    if not route.required <= supplied or supplied - route.required - route.optional:
        raise ValueError("Missing or unsupported options for endpoint")
    if len(set(options.views)) != len(options.views) or any(
        view not in VIEWS for view in options.views
    ):
        raise ValueError("Unsupported or duplicate league view")
    params: list[tuple[str, str]] = []
    if endpoint == Endpoint.LEAGUE:
        params.extend(("view", view) for view in options.views)
        for key, value in [
            ("scoringPeriodId", options.scoring_period),
            ("matchupPeriodId", options.matchup_period),
        ]:
            if value is not None:
                params.append((key, str(value)))
    elif endpoint == Endpoint.PRO_SCHEDULES:
        params.append(("view", "proTeamSchedules_wl"))
    elif endpoint == Endpoint.PLAYER_DIRECTORY:
        params.append(("view", "players_wl"))
    elif endpoint == Endpoint.PLAYER_NEWS:
        params.append(("playerId", str(options.player_id)))
        if options.season is not None:
            params.append(("seasonId", str(options.season)))
    elif endpoint in (Endpoint.NFL_CORE_ATHLETES, Endpoint.NFL_CORE_TEAMS):
        for key, value in [("limit", options.limit), ("page", options.page)]:
            if value is not None:
                params.append((key, str(value)))
    elif endpoint in (Endpoint.NFL_SUMMARY, Endpoint.NFL_WEB_SUMMARY):
        params.append(("event", str(options.event_id)))
        if endpoint == Endpoint.NFL_WEB_SUMMARY:
            params.extend([("region", "us"), ("lang", "en")])
    elif endpoint == Endpoint.NOW_NEWS and options.sport:
        params.append(("sport", options.sport))
    elif endpoint == Endpoint.TEAM_LOGO:
        params.append(("img", f"/i/teamlogos/nfl/500/{options.team_abbrev}.png"))
    fantasy_filter = options.fantasy_filter
    if endpoint == Endpoint.PLAYER_DIRECTORY and fantasy_filter is None:
        fantasy_filter = {"filterActive": {"value": True}}
    filter_json = None
    if fantasy_filter is not None:
        filter_json = json.dumps(
            fantasy_filter, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        if len(filter_json) > 8192:
            raise ValueError("Fantasy filter exceeds size limit")
        players = fantasy_filter.get("players")
        if isinstance(players, dict) and "filterStatus" in players:
            statuses = players["filterStatus"]
            if (
                not isinstance(statuses, dict)
                or not isinstance(statuses.get("value"), list)
                or any(s not in ("FREEAGENT", "WAIVERS", "ONTEAM") for s in statuses["value"])
            ):
                raise ValueError("Unsupported availability status")
    url = route.path.format(**options.model_dump())
    if params:
        url += "?" + urlencode(params)
    return EndpointRequest(endpoint, options, url, route.response_format, filter_json)
