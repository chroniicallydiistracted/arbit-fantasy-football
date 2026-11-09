"""All registered route families execute through the real guarded HTTP stack."""

import json
from decimal import Decimal

import pytest
from arbit_data.espn.client import EspnClient
from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.transport import EspnError
from espn_http import server


@pytest.mark.parametrize(
    "endpoint,options,payload",
    [
        (Endpoint.GAME, {}, {"id": 1, "currentSeasonId": 2026}),
        (Endpoint.SEASON, {"season": 2026}, {"id": 2026, "currentScoringPeriod": {}}),
        (Endpoint.PRO_SCHEDULES, {"season": 2026}, {"settings": {"proTeams": []}}),
        (
            Endpoint.PLAYER_DIRECTORY,
            {"season": 2026},
            [{"id": -16001, "fullName": "Synthetic defense"}],
        ),
        (Endpoint.PLAYER_NEWS, {"player_id": 900001}, {"news": {"feed": []}}),
        (Endpoint.NFL_CORE_LEAGUE, {}, {"id": "28", "athletes": {}, "teams": {}}),
        (
            Endpoint.NFL_CORE_ATHLETES,
            {"limit": 1},
            {
                "count": 1,
                "items": [{"$ref": "https://untrusted.example/must-not-follow"}],
                "pageIndex": 1,
                "pageCount": 1,
            },
        ),
        (
            Endpoint.NFL_CORE_ATHLETE,
            {"season": 2026, "player_id": 900001},
            {"id": "900001", "fullName": "Synthetic athlete"},
        ),
        (
            Endpoint.NFL_CORE_TEAMS,
            {"season": 2026, "limit": 100},
            {"count": 0, "items": [], "pageIndex": 1, "pageCount": 1},
        ),
        (Endpoint.NFL_SCOREBOARD, {}, {"events": [], "leagues": [{"id": "28"}]}),
        (Endpoint.NFL_WEB_SCOREBOARD, {}, {"events": [], "leagues": [{"id": "28"}]}),
        (
            Endpoint.NFL_SUMMARY,
            {"event_id": "401873023"},
            {
                "header": {"id": "401873023"},
                "boxscore": {},
                "drives": {"previous": []},
                "scoringPlays": [],
            },
        ),
        (
            Endpoint.NFL_WEB_SUMMARY,
            {"event_id": "401873023"},
            {
                "header": {"id": "401873023"},
                "boxscore": {},
                "drives": {"previous": []},
                "scoringPlays": [],
            },
        ),
        (Endpoint.NFL_NEWS, {}, {"articles": []}),
        (Endpoint.NFL_STANDINGS, {}, {"children": []}),
        (Endpoint.NOW_NEWS, {"sport": "football"}, {"headlines": []}),
    ],
)
def test_registered_json_family_has_callable_validated_data(
    monkeypatch, endpoint, options, payload
):
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, received, _):
        result = EspnClient(transport).fetch(endpoint, EndpointOptions(**options))
        assert result.capability == "available"
        assert result.payload == payload
        assert result.missing_sections == ()
        assert len(received) == 1
        assert result.receipt.sha256 and result.receipt.byte_count > 0
        assert "Cookie" not in received[0][1] and "Authorization" not in received[0][1]


@pytest.mark.parametrize(
    "endpoint,options",
    [(Endpoint.HEADSHOT, {"player_id": 900001}), (Endpoint.TEAM_LOGO, {"team_abbrev": "lar"})],
)
def test_both_png_routes_are_binary_not_json(monkeypatch, endpoint, options):
    png = b"\x89PNG\r\n\x1a\n" + bytes.fromhex("0000000d49484452000000010000000108060000001f15c489")
    with server(monkeypatch, body=png, headers={"Content-Type": "image/png"}) as (transport, _, _):
        result = EspnClient(transport).fetch(endpoint, EndpointOptions(**options))
        assert result.payload == png and result.capability == "available"
        assert result.receipt.byte_count == 33


@pytest.mark.parametrize(
    "body,content_type", [(b"not a PNG", "image/png"), (b"{}", "application/json")]
)
def test_bad_asset_cannot_be_reported_as_an_image(monkeypatch, body, content_type):
    with server(monkeypatch, body=body, headers={"Content-Type": content_type}) as (
        transport,
        _,
        _,
    ):
        with pytest.raises(EspnError) as error:
            EspnClient(transport).fetch(Endpoint.HEADSHOT, EndpointOptions(player_id=900001))
        assert error.value.code == "INVALID_RESPONSE"


@pytest.mark.parametrize(
    "view,payload,capability,missing",
    [
        ("mSchedule", {"id": 1729878439}, "limited", ("schedule",)),
        ("mStandings", {"id": 1729878439, "teams": [{"id": 1}]}, "limited", ("teams.*.record",)),
        ("modular", {"id": 1729878439}, "metadata_only", ()),
        ("mNav", {"id": 1729878439}, "metadata_only", ()),
        ("proTeamSchedules_wl", {"id": 1729878439}, "limited", ("proTeamSchedules",)),
        ("mScoreboard", {"id": 1729878439, "schedule": []}, "available", ()),
        (
            "mRoster",
            {"id": 1729878439, "seasonId": 2026, "scoringPeriodId": 1, "teams": []},
            "available",
            (),
        ),
    ],
)
def test_http_success_is_not_silently_treated_as_complete_data(
    monkeypatch, view, payload, capability, missing
):
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, _, _):
        result = EspnClient(transport).fetch(
            Endpoint.LEAGUE, EndpointOptions(season=2026, views=(view,), scoring_period=1)
        )
        assert result.capability == capability
        assert result.missing_sections == missing


@pytest.mark.parametrize(
    "endpoint,options,payload,code",
    [
        (Endpoint.LEAGUE, dict(season=2026, views=("mSettings",)), {"id": 42}, "SCOPE_MISMATCH"),
        (
            Endpoint.LEAGUE,
            dict(season=2026, views=("mStatus",), scoring_period=8),
            {"id": 1729878439, "seasonId": 2026, "scoringPeriodId": 1, "status": {}},
            "SCOPE_MISMATCH",
        ),
        (
            Endpoint.NFL_CORE_ATHLETE,
            dict(season=2026, player_id=900001),
            {"id": "42"},
            "SCOPE_MISMATCH",
        ),
        (
            Endpoint.NFL_SUMMARY,
            dict(event_id="401873023"),
            {"header": {"id": "42"}, "boxscore": {}, "drives": {}, "scoringPlays": []},
            "SCOPE_MISMATCH",
        ),
        (Endpoint.NFL_NEWS, {}, {"articles": {}}, "SCHEMA_DRIFT"),
        (Endpoint.PLAYER_DIRECTORY, dict(season=2026), {}, "INVALID_RESPONSE"),
        (Endpoint.LEAGUE, dict(season=2026, views=("mRoster",)), [], "INVALID_RESPONSE"),
        (
            Endpoint.LEAGUE,
            dict(season=2026, views=("mTransactions2",), scoring_period=8),
            {"id": 1729878439, "transactions": [{"id": "synthetic", "scoringPeriodId": 1}]},
            "SCOPE_MISMATCH",
        ),
    ],
)
def test_wrong_scope_or_shape_is_a_typed_failure(monkeypatch, endpoint, options, payload, code):
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, _, _):
        with pytest.raises(EspnError) as error:
            EspnClient(transport).fetch(endpoint, EndpointOptions(**options))
        assert error.value.code == code


def test_a_periods_transactions_may_include_lineups_set_ahead_as_espn_lists_them(monkeypatch):
    """Observed in FFA period 8 (2026-11-08): FUTURE_ROSTER for period 9 and a ROSTER at 0."""
    body = {
        "id": 1729878439,
        "scoringPeriodId": 8,
        "transactions": [
            {"id": "a", "type": "WAIVER", "scoringPeriodId": 8},
            {"id": "b", "type": "FUTURE_ROSTER", "scoringPeriodId": 9},
            {"id": "c", "type": "ROSTER", "scoringPeriodId": 0},
        ],
    }
    options = EndpointOptions(season=2026, views=("mTransactions2",), scoring_period=8)
    with server(monkeypatch, body=json.dumps(body).encode()) as (transport, _, _):
        assert (
            len(EspnClient(transport).fetch(Endpoint.LEAGUE, options).payload["transactions"]) == 3
        )
    body["transactions"].append({"id": "d", "type": "WAIVER", "scoringPeriodId": 9})
    with server(monkeypatch, body=json.dumps(body).encode()) as (transport, _, _):
        with pytest.raises(EspnError) as error:
            EspnClient(transport).fetch(Endpoint.LEAGUE, options)
        assert error.value.code == "SCOPE_MISMATCH", "any other period is still drift"


def test_player_cards_do_not_claim_missing_or_wrong_requested_ids(monkeypatch):
    with server(monkeypatch, body=b'{"players":[{"id":42}]}') as (transport, _, _):
        with pytest.raises(EspnError) as error:
            EspnClient(transport).fetch(
                Endpoint.LEAGUE,
                EndpointOptions(
                    season=2026,
                    views=("kona_playercard",),
                    fantasy_filter={"players": {"filterIds": {"value": [900001]}}},
                ),
            )
        assert error.value.code == "SCOPE_MISMATCH"


def test_exact_decimals_survive_array_transport(monkeypatch):
    with server(monkeypatch, body=b'[{"id":900001,"ownership":0.1}]') as (transport, _, _):
        result = EspnClient(transport).fetch(
            Endpoint.PLAYER_DIRECTORY, EndpointOptions(season=2026)
        )
        assert result.payload[0]["ownership"] == Decimal("0.1")


@pytest.mark.parametrize(
    "endpoint,options,payload,missing",
    [
        (
            Endpoint.LEAGUE,
            dict(season=2026, views=("mBoxscore",), scoring_period=1, matchup_period=1),
            {
                "id": 1729878439,
                "schedule": [{"matchupPeriodId": 1, "home": {"teamId": 1}, "away": {"teamId": 2}}],
            },
            "matchup_rosters",
        ),
        (
            Endpoint.LEAGUE,
            dict(
                season=2026,
                views=("kona_playercard",),
                fantasy_filter={"players": {"filterIds": {"value": [900001]}}},
            ),
            {"players": [{"id": 900001}]},
            "players.*.player.stats",
        ),
        (
            Endpoint.LEAGUE,
            dict(
                season=2026,
                views=("kona_player_info",),
                fantasy_filter={"players": {"filterRanksForScoringPeriodIds": {"value": [8]}}},
            ),
            {"players": [{"id": 900001}]},
            "players.*.ratings",
        ),
        (
            Endpoint.NFL_SUMMARY,
            dict(event_id="401873023"),
            {"header": {"id": "401873023"}, "boxscore": {}, "drives": {}, "scoringPlays": []},
            "drives.previous",
        ),
    ],
)
def test_nested_audited_capabilities_cannot_disappear_silently(
    monkeypatch, endpoint, options, payload, missing
):
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, _, _):
        result = EspnClient(transport).fetch(endpoint, EndpointOptions(**options))
        assert result.capability == "limited" and missing in result.missing_sections


@pytest.mark.parametrize(
    "endpoint,options,payload",
    [
        (
            Endpoint.LEAGUE,
            dict(season=2026, views=("kona_player_info",)),
            {"id": 42, "players": []},
        ),
        (Endpoint.NFL_CORE_LEAGUE, {}, {"id": "46", "athletes": {}, "teams": {}}),
        (
            Endpoint.NFL_CORE_ATHLETES,
            {"page": 2},
            {"count": 1, "items": [], "pageIndex": 1, "pageCount": 2},
        ),
    ],
)
def test_optional_metadata_still_rejects_contradictory_scope(
    monkeypatch, endpoint, options, payload
):
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, _, _):
        with pytest.raises(EspnError) as caught:
            EspnClient(transport).fetch(endpoint, EndpointOptions(**options))
        assert caught.value.code == "SCOPE_MISMATCH"


def test_boxscore_validates_only_requested_matchup_rosters(monkeypatch):
    payload = {
        "id": 1729878439,
        "schedule": [
            {
                "matchupPeriodId": 1,
                "home": {"teamId": 1, "rosterForCurrentScoringPeriod": {"entries": []}},
            },
            {"matchupPeriodId": 8, "home": {"teamId": 2}},
        ],
    }
    with server(monkeypatch, body=json.dumps(payload).encode()) as (transport, _, _):
        result = EspnClient(transport).fetch(
            Endpoint.LEAGUE,
            EndpointOptions(season=2026, views=("mBoxscore",), scoring_period=1, matchup_period=1),
        )
        assert result.capability == "available"
