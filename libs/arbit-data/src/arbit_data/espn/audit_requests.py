"""Reconstruct audited requests through the allowlisted builder, never replay raw URLs."""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from arbit_data.espn.endpoints import (
    CDN,
    CORE,
    LM,
    SITE,
    WEB,
    Endpoint,
    EndpointOptions,
    EndpointRequest,
    build_request,
)


@dataclass(frozen=True)
class AuditedRequest:
    case: str
    expected: str
    request: EndpointRequest | None
    excluded: str | None = None


def match_request(url: str, fantasy_filter: str | None) -> EndpointRequest:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port is not None
        or parsed.fragment
    ):
        raise ValueError("Unregistered request authority")
    pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
    views = tuple(value for key, value in pairs if key == "view")
    query = {key: value for key, value in pairs if key != "view"}
    if len(query) != sum(key != "view" for key, _ in pairs):
        raise ValueError("Duplicate query parameter")
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    options: dict[str, Any] = {}
    endpoint: Endpoint
    league = re.fullmatch(re.escape(LM) + r"/seasons/(\d+)/segments/0/leagues/1729878439", base)
    season = re.fullmatch(re.escape(LM) + r"/seasons/(\d+)(/players)?", base)
    athlete = re.fullmatch(re.escape(CORE) + r"/seasons/(\d+)/athletes/(\d+)", base)
    teams = re.fullmatch(re.escape(CORE) + r"/seasons/(\d+)/teams", base)
    headshot = re.fullmatch(re.escape(CDN) + r"/i/headshots/nfl/players/full/(\d+)\.png", base)
    if league:
        endpoint = Endpoint.LEAGUE
        options.update(season=int(league[1]), views=views)
        for query_key, option_key in [
            ("scoringPeriodId", "scoring_period"),
            ("matchupPeriodId", "matchup_period"),
        ]:
            if query_key in query:
                options[option_key] = int(query[query_key])
    elif season:
        options["season"] = int(season[1])
        if season[2]:
            if views != ("players_wl",):
                raise ValueError("Unregistered directory view")
            endpoint = Endpoint.PLAYER_DIRECTORY
        elif views == ("proTeamSchedules_wl",):
            endpoint = Endpoint.PRO_SCHEDULES
        elif not views:
            endpoint = Endpoint.SEASON
        else:
            raise ValueError("Unregistered season view")
    elif athlete:
        endpoint = Endpoint.NFL_CORE_ATHLETE
        options.update(season=int(athlete[1]), player_id=int(athlete[2]))
    elif teams:
        endpoint = Endpoint.NFL_CORE_TEAMS
        options["season"] = int(teams[1])
    elif headshot:
        endpoint = Endpoint.HEADSHOT
        options["player_id"] = int(headshot[1])
    else:
        exact = {
            LM: Endpoint.GAME,
            CORE: Endpoint.NFL_CORE_LEAGUE,
            CORE + "/athletes": Endpoint.NFL_CORE_ATHLETES,
            SITE + "/apis/fantasy/v3/games/ffl/news/players": Endpoint.PLAYER_NEWS,
            SITE + "/apis/site/v2/sports/football/nfl/scoreboard": Endpoint.NFL_SCOREBOARD,
            WEB + "/apis/site/v2/sports/football/nfl/scoreboard": Endpoint.NFL_WEB_SCOREBOARD,
            SITE + "/apis/site/v2/sports/football/nfl/summary": Endpoint.NFL_SUMMARY,
            WEB + "/apis/site/v2/sports/football/nfl/summary": Endpoint.NFL_WEB_SUMMARY,
            SITE + "/apis/site/v2/sports/football/nfl/news": Endpoint.NFL_NEWS,
            SITE + "/apis/v2/sports/football/nfl/standings": Endpoint.NFL_STANDINGS,
            "https://now.core.api.espn.com/v1/sports/news": Endpoint.NOW_NEWS,
            CDN + "/combiner/i": Endpoint.TEAM_LOGO,
        }
        if base not in exact:
            raise ValueError("Unregistered endpoint path")
        endpoint = exact[base]
    for query_key, option_key in [
        ("playerId", "player_id"),
        ("seasonId", "season"),
        ("limit", "limit"),
        ("page", "page"),
    ]:
        if query_key in query:
            options[option_key] = int(query[query_key])
    if "event" in query:
        options["event_id"] = query["event"]
    if "sport" in query:
        options["sport"] = query["sport"]
    if endpoint == Endpoint.TEAM_LOGO:
        logo = re.fullmatch(r"/i/teamlogos/nfl/500/([a-z]{2,4})\.png", query.get("img", ""))
        if logo is None:
            raise ValueError("Unregistered image path")
        options["team_abbrev"] = logo[1]
    if fantasy_filter is not None:
        options["fantasy_filter"] = json.loads(fantasy_filter)
    request = build_request(endpoint, EndpointOptions(**options))
    if sorted(parse_qsl(urlsplit(request.url).query, keep_blank_values=True)) != sorted(pairs):
        raise ValueError("Unexpected or unconsumed query parameters")
    if request.url.split("?")[0] != base:
        raise ValueError("Noncanonical endpoint path")
    if request.fantasy_filter is not None and fantasy_filter is None:
        raise ValueError("Missing audited filter")
    return request


def audit_requests(records: list[dict[str, Any]]) -> tuple[AuditedRequest, ...]:
    if not records:
        raise ValueError("Audit must contain request evidence")
    rows = []
    cases: set[str] = set()
    for record in records:
        case = record["case"]
        expected = record["outcome"]
        if expected not in {
            "data_returned",
            "asset_returned",
            "missing_expected_data",
            "json_metadata_only",
            "non_json",
            "http_error",
        }:
            raise ValueError("Unknown audit outcome")
        if type(record["status"]) is not int:
            raise ValueError("Invalid HTTP status evidence")
        if not isinstance(case, str) or not case or case in cases:
            raise ValueError("Invalid/duplicate audit case")
        cases.add(case)
        headers = {key.lower(): value for key, value in record.get("requestHeaders", {}).items()}
        if record["method"] != "GET" or "cookie" in headers or "authorization" in headers:
            raise ValueError("Only public audited GETs allowed")
        excluded = None
        if record["status"] != 200:
            excluded = "http_failure"
        elif (
            case in {"legacy-domain-v1", "legacy-domain-v2", "legacy-domain-v3"}
            and expected == "non_json"
        ):
            excluded = "html_redirect"
        elif case == "unknown-view-control" and expected == "json_metadata_only":
            excluded = "negative_control"
        request = (
            None if excluded else match_request(record["url"], headers.get("x-fantasy-filter"))
        )
        if request is not None:
            compatible = (
                {"asset_returned"}
                if request.response_format == "png"
                else {"data_returned", "missing_expected_data", "json_metadata_only"}
            )
            if expected not in compatible:
                raise ValueError("Audit outcome contradicts registered response format")
        elif excluded == "http_failure" and expected != "http_error":
            raise ValueError("Audit outcome contradicts HTTP status")
        rows.append(AuditedRequest(case, expected, request, excluded))
    return tuple(rows)
