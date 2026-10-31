"""Operator scoring verification keeps actual computation and output privacy real."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arbit_data.espn.client import EndpointResponse
from arbit_data.espn.transport import EspnError, SourceReceipt
from arbit_worker import main as module

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"


class Source:
    def __init__(self, *args):
        pass

    def fetch(self, endpoint, options):
        fixture = json.loads(FIXTURE.read_bytes())
        case = deepcopy(fixture["cases"][0])
        case["player"]["id"] = 900001
        case["player"]["fullName"] = "PRIVATE PLAYER"
        if "mSettings" in options.views:
            payload = {
                "settings": {
                    "size": 1,
                    "scoringSettings": fixture["scoringSettings"],
                    "rosterSettings": {"lineupSlotCounts": {"0": 1}},
                    "scheduleSettings": {"matchupPeriods": {"1": [1]}},
                },
                "status": {
                    "firstScoringPeriod": 1,
                    "latestScoringPeriod": 2,
                    "finalScoringPeriod": 17,
                },
            }
        else:
            payload = {
                "schedule": [
                    {
                        "matchupPeriodId": 1,
                        "home": {
                            "teamId": 1,
                            "totalPoints": 35.66,
                            "rosterForCurrentScoringPeriod": {
                                "appliedStatTotal": 35.66,
                                "entries": [
                                    {
                                        "playerId": 900001,
                                        "lineupSlotId": 0,
                                        "playerPoolEntry": {
                                            "id": 900001,
                                            "player": case["player"],
                                            "appliedStatTotal": 35.66,
                                        },
                                    }
                                ],
                            },
                        },
                    }
                ]
            }
        return EndpointResponse(
            endpoint,
            payload,
            SourceReceipt(
                "https://lm-api-reads.fantasy.espn.com/synthetic",
                datetime(2026, 10, 31, tzinfo=UTC),
                "a" * 64,
                100,
            ),
            "available",
            (),
        )


def test_command_runs_real_math_and_prints_no_player_payload(monkeypatch, capsys):
    monkeypatch.setattr(module, "EspnClient", Source)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-score-audit", "--periods", "1"])
    module.main()
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["success"] is True and report["recommendationsEnabled"] is False
    assert report["totals"]["verifiedPlayerGames"] == 1 and report["totals"]["lineupsMatched"] == 1
    assert "PRIVATE PLAYER" not in output and "900001" not in output


def test_provider_error_is_a_safe_report_and_nonzero_exit(monkeypatch, capsys):
    class Denied(Source):
        def fetch(self, *args):
            raise EspnError("RATE_LIMITED", status=429, retry_after_seconds=120)

    monkeypatch.setattr(module, "EspnClient", Denied)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-score-audit"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert caught.value.code == 1 and report["success"] is False
    assert report["issues"] == [{"code": "RATE_LIMITED", "status": 429, "retryAfterSeconds": 120}]


def test_bad_period_never_opens_transport(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("Bad arguments reached transport")

    monkeypatch.setattr(module, "EspnTransport", forbidden)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-score-audit", "--periods", "0"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "period" in capsys.readouterr().err
