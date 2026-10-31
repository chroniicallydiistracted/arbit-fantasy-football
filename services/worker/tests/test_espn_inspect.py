"""The actual manual command uses the real reader and prints no source payloads."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_data.espn.transport import EspnError, FetchResult, SourceReceipt
from arbit_worker import main as module

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/espn"


class LocalTransport:
    def __init__(self):
        self.pages = 0

    def get(self, season, *, views, scoring_period=None, fantasy_filter=None):
        if views == ("kona_player_info",):
            filename = "available.synthetic.json"
            self.pages += 1
        else:
            filename = "league.synthetic.json"
        payload = json.loads((FIXTURES / filename).read_bytes(), parse_float=Decimal)
        if self.pages > 1 and views == ("kona_player_info",):
            payload["players"] = []
        return FetchResult(
            payload,
            SourceReceipt(
                "https://lm-api-reads.fantasy.espn.com/synthetic",
                datetime(2026, 10, 30, tzinfo=UTC),
                "a" * 64,
                100,
            ),
        )


def test_inspect_reads_without_database_and_prints_only_safe_summary(monkeypatch, capsys):
    monkeypatch.delenv("ARBIT_DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "EspnTransport", LocalTransport, raising=False)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-inspect"])
    module.main()
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["leagueId"] == "1729878439"
    assert data["season"] == 2026 and data["scoringPeriod"] == 8
    assert data["teams"] == 2 and data["ownedPlayers"] == 2 and data["availablePlayers"] == 1
    assert data["draftPicks"] == 1 and data["scoringItems"] == 47
    assert data["rulesNormalized"] is False and data["published"] is False
    assert len(data["sources"]) == 4
    assert "Synthetic team" not in output and "SYNTHETIC-MANAGER" not in output
    assert "Synthetic available" not in output and "pointsFor" not in output


def test_inspect_failure_returns_safe_code_and_retry_hint(monkeypatch, capsys):
    class Denied:
        def get(self, *args, **kwargs):
            raise EspnError("RATE_LIMITED", status=429, retry_after_seconds=120)

    monkeypatch.setattr(module, "EspnTransport", Denied, raising=False)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-inspect"])
    with pytest.raises(SystemExit) as caught:
        module.main()
    captured = capsys.readouterr()
    assert caught.value.code == 1 and captured.out == ""
    error = json.loads(captured.err)
    assert error == {"error": "RATE_LIMITED", "status": 429, "retryAfterSeconds": 120}


@pytest.mark.parametrize("period", ["0", "-1", "true", "100"])
def test_bad_period_is_rejected_before_transport_creation(monkeypatch, capsys, period):
    def forbidden():
        raise AssertionError("Invalid arguments must not reach the provider")

    monkeypatch.setattr(module, "EspnTransport", forbidden, raising=False)
    monkeypatch.setattr("sys.argv", ["arbit-worker", "espn-inspect", "--scoring-period", period])
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "scoring-period" in capsys.readouterr().err


def test_existing_fixture_command_still_requires_explicit_database(monkeypatch, capsys):
    monkeypatch.delenv("ARBIT_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        "sys.argv", ["arbit-worker", "fixture", "tests/fixtures/league-snapshot.example.json"]
    )
    with pytest.raises(SystemExit) as caught:
        module.main()
    assert caught.value.code == 2
    assert "ARBIT_DATABASE_URL" in capsys.readouterr().err
