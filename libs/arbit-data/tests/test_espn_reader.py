"""Provider acquisition correctness using observed-shape, synthetic-identity data."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_data.espn import reader as module
from arbit_data.espn.reader import EspnReader
from arbit_data.espn.transport import EspnError, FetchResult, SourceReceipt

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/espn"


def fixture(name):
    return json.loads((FIXTURES / name).read_bytes(), parse_float=Decimal)


def available(pid, status="FREEAGENT"):
    entry = fixture("available.synthetic.json")["players"][0]
    entry["id"] = entry["player"]["id"] = pid
    entry["status"] = status
    return entry


class ScriptedEspn:
    def __init__(self, *, initial=None, final=None, pages=None, cap=300):
        self.initial = initial if initial is not None else fixture("league.synthetic.json")
        self.final = final if final is not None else deepcopy(self.initial)
        self.pages = pages if pages is not None else [[available(910001)]]
        self.cap = cap
        self.calls = []
        self.context_reads = 0

    def get(self, season, *, views, scoring_period=None, fantasy_filter=None):
        self.calls.append((views, scoring_period, fantasy_filter))
        if views == ("kona_player_info",):
            assert fantasy_filter["players"]["filterStatus"] == {"value": ["FREEAGENT", "WAIVERS"]}
            assert fantasy_filter["players"]["limit"] == 300
            offset = fantasy_filter["players"]["offset"]
            payload = {
                "players": [entry for page in self.pages for entry in page][
                    offset : offset + self.cap
                ]
            }
        else:
            assert set(views) == {
                "mSettings",
                "mTeam",
                "mRoster",
                "mMatchupScore",
                "mDraftDetail",
                "mStatus",
            }
            payload = self.initial if self.context_reads == 0 else self.final
            self.context_reads += 1
        data = deepcopy(payload)
        receipt = SourceReceipt(
            "https://lm-api-reads.fantasy.espn.com/synthetic",
            datetime(2026, 10, 30, 12, tzinfo=UTC),
            hashlib.sha256(json.dumps(data, default=str).encode()).hexdigest(),
            100,
        )
        return FetchResult(data, receipt)


def test_reads_all_available_pages_and_preserves_exact_observed_facts():
    transport = ScriptedEspn(
        pages=[[available(910000 + i) for i in range(300)], [available(920001, "WAIVERS")]]
    )
    result = EspnReader(transport).fetch_league_snapshot(2026)
    assert len(result.available) == 301
    assert result.available[-1].status == "WAIVERS"
    assert result.league.teams[1].roster.entries[0].player_id == -16001
    assert result.league.settings.is_public is True
    assert result.league.settings.draft_settings["type"] == "OFFLINE"
    assert result.league.settings.scoring_settings.scoring_items[-1].stat_id == 9999
    assert result.league.settings.scoring_settings.scoring_items[-1].points == Decimal("0.1")
    assert result.league.settings.scoring_settings.scoring_items[-1].points_overrides == {
        "16": Decimal("0.25")
    }
    assert result.league.teams[0].record.overall.points_for == Decimal("939.04")
    assert result.league.schedule[0].matchup_period_id == 8
    assert len(result.receipts) == 5
    assert [call[1] for call in transport.calls] == [None, 8, 8, 8, 8]
    assert transport.calls[2][2]["players"]["offset"] == 300
    assert result.capture_started_at <= result.capture_finished_at
    assert result.league.teams[0].owners == ("SYNTHETIC-MANAGER",)
    assert "notificationSettings" not in result.league.model_dump_json()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.pop("teams"),
        lambda d: d["settings"]["scoringSettings"].pop("scoringItems"),
        lambda d: d["teams"][0]["record"].pop("overall"),
        lambda d: d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"].pop(
            "eligibleSlots"
        ),
        lambda d: d.update(id=42),
        lambda d: d.update(segmentId=1),
        lambda d: d["teams"][0].update(id=True),
    ],
)
def test_missing_or_invalid_required_data_is_not_defaulted(change):
    league = fixture("league.synthetic.json")
    change(league)
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(initial=league)).fetch_league_snapshot(2026)
    assert caught.value.code == "SCHEMA_DRIFT"
    assert "Synthetic team" not in str(caught.value)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["teams"].append(deepcopy(d["teams"][0])),
        lambda d: d["teams"][0]["roster"]["entries"].append(
            deepcopy(d["teams"][0]["roster"]["entries"][0])
        ),
        lambda d: d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"].update(onTeamId=2),
        lambda d: d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"]["player"].update(id=42),
        lambda d: d["schedule"][0]["home"].update(teamId=42),
        lambda d: d["draftDetail"]["picks"][0].update(teamId=42),
    ],
)
def test_ownership_and_referential_invariants_are_enforced(change):
    league = fixture("league.synthetic.json")
    change(league)
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(initial=league)).fetch_league_snapshot(2026)
    assert caught.value.code == "INCONSISTENT_DATA"


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["teams"][0]["roster"]["entries"][0].update(lineupSlotId=20),
        lambda d: d["teams"][0]["roster"]["entries"][0]["playerPoolEntry"].update(
            lineupLocked=True
        ),
        lambda d: d["settings"]["scoringSettings"]["scoringItems"][0].update(points=Decimal("9")),
        lambda d: d["status"].update(latestScoringPeriod=9),
        lambda d: d["draftDetail"]["picks"][0].update(playerId=900003),
    ],
)
def test_changed_context_is_rejected(change):
    final = fixture("league.synthetic.json")
    change(final)
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(final=final)).fetch_league_snapshot(2026)
    assert caught.value.code == "SOURCE_CHANGED"


@pytest.mark.parametrize(
    "pages",
    [
        [[available(900001)]],
        [[available(910001, "ONTEAM")]],
        [[available(910001, "INJURED_RESERVE")]],
        [[available(910001), available(910001)]],
        [[available(910000 + i) for i in range(300)], [available(910001)]],
    ],
)
def test_partial_or_wrong_availability_is_rejected(pages):
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(pages=pages)).fetch_league_snapshot(2026)
    assert caught.value.code == "INCONSISTENT_DATA"


def test_page_limit_never_marks_unterminated_inventory_complete(monkeypatch):
    monkeypatch.setattr(module, "MAX_PAGES", 2)
    pages = [
        [available(910000 + i) for i in range(300)],
        [available(920000 + i) for i in range(300)],
    ]
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(pages=pages)).fetch_league_snapshot(2026)
    assert caught.value.code == "PAGE_LIMIT"


def test_historical_rosters_cannot_be_combined_with_current_availability():
    initial = fixture("league.synthetic.json")
    initial["scoringPeriodId"] = 1
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn(initial=initial)).fetch_league_snapshot(2026, scoring_period=1)
    assert caught.value.code == "HISTORICAL_AVAILABILITY_UNSUPPORTED"


def test_requested_season_must_match_response():
    with pytest.raises(EspnError) as caught:
        EspnReader(ScriptedEspn()).fetch_league_snapshot(2027)
    assert caught.value.code == "SCOPE_MISMATCH"


def test_empty_preseason_rosters_and_draft_are_valid_without_invented_players():
    initial = fixture("league.synthetic.json")
    for team in initial["teams"]:
        team["roster"]["entries"] = []
    initial["draftDetail"].update(drafted=False, picks=[])
    initial["schedule"] = []
    result = EspnReader(ScriptedEspn(initial=initial, pages=[[]])).fetch_league_snapshot(
        2026, scoring_period=8
    )
    assert result.available == ()
    assert result.league.draft_detail.picks == ()
    assert all(not team.roster.entries for team in result.league.teams)


def test_provider_page_cap_cannot_silently_truncate_availability():
    transport = ScriptedEspn(pages=[[available(930000 + i) for i in range(101)]], cap=50)
    result = EspnReader(transport).fetch_league_snapshot(2026)
    assert len(result.available) == 101
    assert result.available[-1].id == 930100
    assert transport.calls[-2][2]["players"]["offset"] == 101


def test_observed_null_ownership_and_absent_stat_values_remain_unknown():
    result = EspnReader(ScriptedEspn()).fetch_league_snapshot(2026)
    assert result.available[0].player.ownership["activityLevel"] is None
    assert result.available[0].player.stats[1].stats is None
    assert result.available[0].player.stats[1].applied_total is None


def test_manager_changes_during_capture_are_rejected():
    first = fixture("league.synthetic.json")
    first["members"] = [{"id": "owner-1", "displayName": "Owner"}]
    last = deepcopy(first)
    last["teams"][0]["owners"] = ["other-owner"]
    with pytest.raises(EspnError, match="SOURCE_CHANGED"):
        EspnReader(ScriptedEspn(initial=first, final=last)).fetch_league_snapshot(2026)
