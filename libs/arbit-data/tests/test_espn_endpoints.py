"""Exact route/filter reconstruction and fail-closed endpoint scope."""

import json
from pathlib import Path

import pytest
from arbit_data.espn.audit_requests import audit_requests, match_request
from arbit_data.espn.endpoints import Endpoint, EndpointOptions, build_request

AUDIT = Path(__file__).resolve().parents[3] / "docs/research/espn-public-2026-10-30.json"


@pytest.mark.parametrize(
    "endpoint,options,url",
    [
        (
            Endpoint.LEAGUE,
            dict(season=2026, views=("mBoxscore",), scoring_period=1, matchup_period=1),
            "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/1729878439?view=mBoxscore&scoringPeriodId=1&matchupPeriodId=1",
        ),
        (
            Endpoint.PLAYER_NEWS,
            dict(player_id=4426515, season=2026),
            "https://site.api.espn.com/apis/fantasy/v3/games/ffl/news/players?playerId=4426515&seasonId=2026",
        ),
        (
            Endpoint.PRO_SCHEDULES,
            dict(season=2026),
            "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026?view=proTeamSchedules_wl",
        ),
        (
            Endpoint.NFL_STANDINGS,
            {},
            "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        ),
        (
            Endpoint.NFL_WEB_SUMMARY,
            dict(event_id="401873023"),
            "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401873023&region=us&lang=en",
        ),
        (
            Endpoint.TEAM_LOGO,
            dict(team_abbrev="lar"),
            "https://a.espncdn.com/combiner/i?img=%2Fi%2Fteamlogos%2Fnfl%2F500%2Flar.png",
        ),
    ],
)
def test_routes_use_verified_origins_paths_and_periods(endpoint, options, url):
    request = build_request(endpoint, EndpointOptions(**options))
    assert request.url == url


def test_every_audited_request_is_accounted_for_through_builder():
    records = json.loads(AUDIT.read_bytes())["requests"]
    classified = audit_requests(records)
    assert len(classified) == 81
    assert sum(row.request is not None for row in classified) == 68
    assert (
        sum(row.expected == "data_returned" for row in classified if row.request is not None) == 61
    )
    assert (
        sum(row.expected == "asset_returned" for row in classified if row.request is not None) == 2
    )
    assert sum(row.request is None for row in classified) == 13
    assert {row.case for row in classified if row.excluded == "html_redirect"} == {
        "legacy-domain-v1",
        "legacy-domain-v2",
        "legacy-domain-v3",
    }
    card = next(row.request for row in classified if row.case == "player-card")
    assert json.loads(card.fantasy_filter)["players"]["filterIds"]["value"] == [
        4426515,
        4379399,
        4685382,
    ]
    assert (
        next(
            row.request for row in classified if row.case == "pro-player-directory"
        ).response_format
        == "array"
    )


@pytest.mark.parametrize(
    "endpoint,options",
    [
        (Endpoint.LEAGUE, dict(season=2026, views=("kona_league_messageboard",))),
        (Endpoint.LEAGUE, dict(season=2026, views=("unknown",))),
        (Endpoint.LEAGUE, dict(season=2026, views=("mSettings", "mSettings"))),
        (Endpoint.LEAGUE, dict(season=True)),
        (Endpoint.LEAGUE, dict(season=2025)),
        (Endpoint.LEAGUE, dict(season=2026, scoring_period=0)),
        (Endpoint.LEAGUE, dict(season=2026, matchup_period=True)),
        (Endpoint.LEAGUE, dict(season=2026, player_id=4426515)),
        (
            Endpoint.LEAGUE,
            dict(
                season=2026,
                fantasy_filter={"players": {"filterStatus": {"value": ["INJURED_RESERVE"]}}},
            ),
        ),
        (Endpoint.NFL_SUMMARY, dict(event_id="../secrets")),
        (Endpoint.HEADSHOT, dict(player_id=-16001)),
        (Endpoint.TEAM_LOGO, dict(team_abbrev="../../foo")),
        (Endpoint.GAME, dict(season=2026)),
        (Endpoint.NOW_NEWS, dict(sport="basketball")),
    ],
)
def test_invalid_or_ignored_options_are_rejected(endpoint, options):
    with pytest.raises(ValueError):
        build_request(endpoint, EndpointOptions(**options))


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/apis/v3/games/ffl",
        "http://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl",
        "https://user:password@lm-api-reads.fantasy.espn.com/apis/v3/games/ffl",
        "https://lm-api-reads.fantasy.espn.com:444/apis/v3/games/ffl",
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl#secret",
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/42?view=mSettings",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=1&event=2",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=1&unexpected=true",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=1&",
        "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/%2e%2e/secret",
    ],
)
def test_audit_matcher_cannot_become_arbitrary_url_fetcher(url):
    with pytest.raises(ValueError):
        match_request(url, None)


def test_new_unknown_success_fails_coverage_instead_of_being_silently_skipped():
    records = [
        {
            "case": "unexpected",
            "status": 200,
            "outcome": "data_returned",
            "url": "https://site.api.espn.com/new-route",
            "method": "GET",
            "requestHeaders": {},
        }
    ]
    with pytest.raises(ValueError):
        audit_requests(records)


@pytest.mark.parametrize(
    "fantasy_filter",
    [
        {"unknown": {}},
        {"players": {"unknown": {"value": 1}}},
        {"players": {"filterIds": "invalid"}},
        {"players": {"filterIds": {"value": [True]}}},
        {"players": {"filterIds": {"value": [1, 1]}}},
        {"players": {"limit": True}},
        {"players": {"offset": -1}},
        {"players": {"sortPercOwned": {"sortPriority": 1, "sortAsc": "false"}}},
    ],
)
def test_unobserved_or_malformed_filter_options_are_rejected(fantasy_filter):
    with pytest.raises(ValueError):
        build_request(
            Endpoint.LEAGUE,
            EndpointOptions(
                season=2026, views=("kona_player_info",), fantasy_filter=fantasy_filter
            ),
        )
