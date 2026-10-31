"""Completed-week audit totals, failure coverage and safe provider orchestration."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arbit_data.espn.client import EndpointResponse
from arbit_data.espn.endpoints import Endpoint
from arbit_data.espn.scoring_audit import audit_scoring
from arbit_data.espn.transport import SourceReceipt

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"


def inputs():
    fixture = json.loads(FIXTURE.read_bytes())
    cases = {x["case"]: x for x in fixture["cases"]}

    def entry(case, identity, slot):
        c = deepcopy(cases[case])
        c["player"]["id"] = identity
        return {
            "playerId": identity,
            "lineupSlotId": slot,
            "playerPoolEntry": {
                "id": identity,
                "player": c["player"],
                "appliedStatTotal": c["officialPoolTotal"],
            },
        }

    home = [
        entry("quarterback", 1001, 0),
        entry("kicker", 1003, 20),
        entry("quarterback", 1005, 21),
    ]
    home[-1]["playerPoolEntry"]["appliedStatTotal"] = 0
    home[-1]["playerPoolEntry"]["player"]["stats"][0].update(
        stats={}, appliedStats={}, appliedTotal=0
    )
    away = [entry("quarterback", 1002, 0)]
    settings = {
        "id": 1729878439,
        "seasonId": 2026,
        "settings": {
            "size": 2,
            "scoringSettings": fixture["scoringSettings"],
            "rosterSettings": {"lineupSlotCounts": {"0": 1, "20": 7, "21": 1}},
            "scheduleSettings": {"matchupPeriods": {"1": [1]}},
        },
        "status": {"firstScoringPeriod": 1, "latestScoringPeriod": 2, "finalScoringPeriod": 17},
    }
    period = {
        "id": 1729878439,
        "seasonId": 2026,
        "scoringPeriodId": 1,
        "schedule": [
            {
                "id": 1,
                "matchupPeriodId": 1,
                "home": {
                    "teamId": 1,
                    "totalPoints": 35.66,
                    "rosterForCurrentScoringPeriod": {"appliedStatTotal": 35.66, "entries": home},
                },
                "away": {
                    "teamId": 2,
                    "totalPoints": 35.66,
                    "rosterForCurrentScoringPeriod": {"appliedStatTotal": 35.66, "entries": away},
                },
            }
        ],
    }
    return settings, period


class Source:
    def __init__(self, settings=None, period=None, final=None):
        baseline, game = inputs()
        self.settings = settings or baseline
        self.period = period or game
        self.final = final or deepcopy(self.settings)
        self.reads = 0

    def fetch(self, endpoint, options):
        assert endpoint == Endpoint.LEAGUE
        if "mSettings" in options.views:
            payload = self.settings if self.reads == 0 else self.final
            self.reads += 1
        else:
            assert options.scoring_period == 1 and options.matchup_period == 1
            payload = self.period
        return EndpointResponse(
            endpoint,
            deepcopy(payload),
            SourceReceipt(
                "https://lm-api-reads.fantasy.espn.com/synthetic",
                datetime(2026, 10, 31, tzinfo=UTC),
                "a" * 64,
                100,
            ),
            "available",
            (),
        )


def test_actual_math_reconciles_players_and_lineups_with_bench_ir_excluded():
    report = audit_scoring(Source(), 2026)
    assert report["success"] is True and report["recommendationsEnabled"] is False
    assert report["support"]["configuredRules"] == 46 and report["support"]["supportedRules"] == 46
    assert (
        report["totals"]["verifiedPlayerGames"] == 3
        and report["totals"]["providerZeroEntries"] == 1
    )
    assert report["totals"]["lineupsChecked"] == 2 and report["totals"]["lineupsMatched"] == 2
    assert report["totals"]["mismatches"] == 0 and report["totals"]["errors"] == 0
    assert report["periods"][0]["scoringPeriod"] == 1
    assert len(report["sources"]) == 3
    assert "Synthetic" not in json.dumps(report)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["schedule"][0]["home"].update(totalPoints="35.67"),
        lambda d: d["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"][0][
            "playerPoolEntry"
        ].update(appliedStatTotal="35.67"),
        lambda d: d["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"][0].update(
            lineupSlotId=999
        ),
        lambda d: d["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"].append(
            deepcopy(d["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"][0])
        ),
    ],
)
def test_bad_lineup_or_reference_data_fails_instead_of_partial_success(change):
    settings, period = inputs()
    change(period)
    report = audit_scoring(Source(settings, period), 2026)
    assert report["success"] is False
    assert report["issues"]
    assert report["recommendationsEnabled"] is False


def test_settings_changes_during_reconciliation_invalidate_results():
    settings, _ = inputs()
    final = deepcopy(settings)
    final["settings"]["scoringSettings"]["scoringItems"][0]["points"] = 9
    report = audit_scoring(Source(settings=settings, final=final), 2026)
    assert report["success"] is False
    assert any(issue["code"] == "SOURCE_CHANGED" for issue in report["issues"])


def test_current_period_is_never_treated_as_completed():
    report = audit_scoring(Source(), 2026, periods=(2,))
    assert not report["success"]
    assert any(issue["code"] == "INVALID_COMPLETED_PERIOD" for issue in report["issues"])


def test_multiweek_matchups_require_explicit_future_support():
    settings, _ = inputs()
    settings["settings"]["scheduleSettings"]["matchupPeriods"] = {"1": [1, 2]}
    report = audit_scoring(Source(settings=settings), 2026)
    assert not report["success"]
    assert any(issue["code"] == "MULTIWEEK_MATCHUPS_UNSUPPORTED" for issue in report["issues"])


def test_limited_required_source_cannot_pass_even_with_other_fields_present():
    class Limited(Source):
        def fetch(self, endpoint, options):
            result = super().fetch(endpoint, options)
            return EndpointResponse(endpoint, result.payload, result.receipt, "limited", ("teams",))

    report = audit_scoring(Limited(), 2026)
    assert report["success"] is False
    assert any(
        issue["code"] == "REQUIRED_SOURCE_CAPABILITY_UNAVAILABLE" for issue in report["issues"]
    )
