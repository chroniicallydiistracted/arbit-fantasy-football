"""League facts as members see them: live versus official totals, weekly lineups, transactions.

The ESPN shapes are observed (2026-11-08 audit); the people and numbers are synthetic.
"""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_data import league_history
from arbit_data.archives import CaptureArchive
from arbit_data.espn.client import EndpointResponse
from arbit_data.espn.contracts import League
from arbit_data.espn.endpoints import Endpoint
from arbit_data.espn.transport import SourceReceipt
from arbit_data.league import LeagueDocument, Matchup, MatchupSide
from arbit_data.league_policy import read_policy
from arbit_data.league_store import publish_capture, read_current, read_history

pytestmark = pytest.mark.integration
NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def later(capture, change, seconds=60):
    data = capture.acquisition.league.model_dump(mode="json", by_alias=True)
    change(data)
    old = capture.acquisition
    return capture.model_copy(
        update={
            "acquisition": replace(
                old,
                league=League.model_validate(data),
                receipts=tuple(
                    replace(r, observed_at=r.observed_at + timedelta(seconds=seconds))
                    for r in old.receipts
                ),
                capture_started_at=old.capture_started_at + timedelta(seconds=seconds),
                capture_finished_at=old.capture_finished_at + timedelta(seconds=seconds),
            ),
            "verification": capture.verification,
        }
    )


def publish(uow, tmp_path, capture):
    digest = CaptureArchive(tmp_path).write(capture)
    publish_capture(capture, digest, uow, now=capture.acquisition.capture_finished_at)
    current = read_current(uow, 2026, now=capture.acquisition.capture_finished_at)
    return LeagueDocument.model_validate(current["league"])


def week(data, winner, home_total, away_total, home_live=None, away_live=None):
    game = data["schedule"][0]
    game["winner"] = winner
    game["home"].update(totalPoints=home_total, totalPointsLive=home_live)
    game["away"].update(totalPoints=away_total, totalPointsLive=away_live)


# --- R-054: what a matchup score means -------------------------------------------------------


def test_an_undecided_week_has_a_live_total_and_no_official_one(uow, tmp_path, captured_input):
    # ESPN during a week: totalPoints 0, the running score in totalPointsLive. The away side's
    # only starter has no stat line yet, so ESPN's 0 for it is not a score.
    document = publish(
        uow, tmp_path, later(captured_input, lambda d: week(d, "UNDECIDED", 0, 0, 55.5, 0))
    )
    (game,) = document.matchups
    assert game.winner is None
    assert game.home.official_points is None and game.away.official_points is None
    assert game.home.live_points == Decimal("55.5")
    assert game.away.live_points is None


def test_a_decided_week_keeps_espns_official_total_and_drops_the_live_one(
    uow, tmp_path, captured_input
):
    document = publish(
        uow, tmp_path, later(captured_input, lambda d: week(d, "AWAY", 99.1, 100.2, 99.1, 100.2))
    )
    (game,) = document.matchups
    assert game.winner == "away" and game.playoff_tier == "NONE"
    assert (game.home.official_points, game.away.official_points) == (
        Decimal("99.1"),
        Decimal("100.2"),
    )
    assert game.home.live_points is None and game.away.live_points is None


def test_an_unrecognized_winner_stops_publication_rather_than_guessing(
    uow, tmp_path, captured_input
):
    with pytest.raises(ValueError, match="UNKNOWN_MATCHUP_WINNER"):
        publish(uow, tmp_path, later(captured_input, lambda d: week(d, "FORFEIT", 1, 0)))


def test_espn_deciding_a_week_is_an_update_and_changing_a_final_is_a_correction(
    uow, tmp_path, captured_input
):
    def past(winner, home):
        def change(d):
            d["schedule"][0]["matchupPeriodId"] = 7
            week(d, winner, home, 90)

        return change

    first = later(captured_input, past("UNDECIDED", 0))
    publish(uow, tmp_path, first)
    decided = later(first, past("HOME", 101))
    publish(uow, tmp_path, decided)
    publish(uow, tmp_path, later(decided, past("HOME", 101.5)))
    kinds = [row["kind"] for row in read_history(uow, 2026)]
    assert kinds == ["correction", "update", "initial"]


# --- R-056 to R-058: player and team facts ---------------------------------------------------


def test_season_points_plain_injury_and_team_move_counts(uow, tmp_path, captured_input):
    def change(d):
        team = d["teams"][0]
        team["transactionCounter"] = {
            "acquisitions": 12,
            "drops": 11,
            "trades": 0,
            "moveToActive": 18,
            "moveToIR": 1,
            "paid": 0.0,
        }
        player = team["roster"]["entries"][0]["playerPoolEntry"]["player"]
        player["injuryStatus"] = "INJURY_RESERVE"
        player["stats"].append(
            {
                "seasonId": 2026,
                "scoringPeriodId": 0,
                "statSourceId": 0,
                "statSplitTypeId": 0,
                "appliedTotal": 77.7,
            }
        )
        other = d["teams"][1]["roster"]["entries"][0]["playerPoolEntry"]["player"]
        other["injuryStatus"] = "NOT_YET_SEEN_CODE"

    document = publish(uow, tmp_path, later(captured_input, change))
    team = next(t for t in document.teams if t.abbreviation == document.teams[0].abbreviation)
    assert team.transactions is not None and team.transactions.acquisitions == 12
    assert team.transactions.move_to_ir == 1
    owned = sorted((p for p in document.players if p.team_id), key=lambda p: p.display_name)
    injured = next(p for p in owned if p.injury_status == "INJURY_RESERVE")
    assert injured.injury == "injured_reserve"
    assert injured.official_season_points == Decimal("77.7")
    unknown = next(p for p in owned if p.injury_status == "NOT_YET_SEEN_CODE")
    assert unknown.injury == "other", "an unlisted code is still an injury listing"
    assert unknown.official_season_points is None, "no season line is unknown, not zero"


def test_stored_documents_from_before_these_fields_still_load():
    old = {
        "season": 2026,
        "scoring_period": 9,
        "matchup_period": 9,
        "rules_hash": "a" * 64,
        "managers": [],
        "teams": [],
        "nfl_teams": [],
        "players": [],
        "matchups": [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "matchup_period": 8,
                "scoring_periods": [8],
                "home": {
                    "team_id": "00000000-0000-0000-0000-000000000002",
                    "official_points": "1.5",
                },
                "away": None,
            }
        ],
        "draft_completed": True,
        "draft_in_progress": False,
        "draft_picks": [],
    }
    (game,) = LeagueDocument.model_validate(old).matchups
    assert game.winner is None and game.home.live_points is None


def test_league_policy_reads_stored_settings_and_leaves_absent_ones_unknown():
    rules = {
        "lineup_slots": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1},
        "provider_policy": {
            "acquisitionSettings": {
                "acquisitionType": "WAIVERS_TRADITIONAL",
                "waiverHours": 24,
                "waiverProcessDays": ["SUNDAY", "MONDAY"],
                "isUsingAcquisitionBudget": False,
                "acquisitionBudget": 100,
            },
            "tradeSettings": {"deadlineDate": 1796230800000, "vetoVotesRequired": 3},
            "scheduleSettings": {
                "playoffTeamCount": 6,
                "playoffSeedingRule": "TOTAL_POINTS_SCORED",
            },
        },
    }
    policy = read_policy(rules)
    assert policy.lineup_slots == ("QB", "RB", "WR", "TE", "FLEX", "DST", "K")
    assert policy.waiver_days == ("MONDAY", "SUNDAY")
    assert policy.uses_bidding is False, "a budget that isn't in use is not bidding"
    assert policy.trade_deadline == datetime(2026, 12, 2, 17, tzinfo=UTC)
    assert policy.trade_review_hours is None and policy.regular_season_matchups is None
    assert read_policy(None).playoff_team_count is None


# --- R-055: weekly lineups -------------------------------------------------------------------

SCORING = Path("tests/fixtures/espn/ffa-scoring.observed.json")


def period_payload():
    """A finished week in ESPN's shape, reconciling exactly with the FFA scoring proof."""
    fixture = json.loads(SCORING.read_bytes())
    cases = {x["case"]: x for x in fixture["cases"]}

    def entry(case, identity, slot, name):
        c = deepcopy(cases[case])
        c["player"].update(id=identity, fullName=name, proTeamId=33)
        return {
            "playerId": identity,
            "lineupSlotId": slot,
            "playerPoolEntry": {
                "id": identity,
                "player": c["player"],
                "appliedStatTotal": c["officialPoolTotal"],
            },
        }

    home = [entry("quarterback", 1001, 0, "Synthetic passer"), entry("kicker", 1003, 20, "Kick")]
    away = [entry("quarterback", 1002, 0, "Synthetic rival")]
    return {
        "id": 1729878439,
        "seasonId": 2026,
        "scoringPeriodId": 1,
        "settings": {
            "size": 2,
            "scoringSettings": fixture["scoringSettings"],
            "rosterSettings": {"lineupSlotCounts": {"0": 1, "20": 7, "21": 1}},
            "scheduleSettings": {"matchupPeriods": {"1": [1], "2": [2]}},
        },
        "status": {"firstScoringPeriod": 1, "latestScoringPeriod": 2, "finalScoringPeriod": 17},
        "schedule": [
            {
                "id": 1,
                "matchupPeriodId": 1,
                "winner": "TIE",
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


class Client:
    def __init__(self, payload):
        self.payload, self.reads = payload, 0

    def fetch(self, endpoint, options):
        assert endpoint == Endpoint.LEAGUE and options.scoring_period == 1
        self.reads += 1
        return EndpointResponse(
            endpoint,
            deepcopy(self.payload),
            SourceReceipt("https://lm-api-reads.fantasy.espn.com/synthetic", NOW, "c" * 64, 1),
            "available",
            (),
        )


def document_for(lineup_team_ids, totals, winner="tie"):
    home, away = lineup_team_ids
    return LeagueDocument(
        season=2026,
        scoring_period=2,
        matchup_period=2,
        rules_hash="a" * 64,
        managers=(),
        teams=(),
        nfl_teams=(),
        players=(),
        matchups=(
            Matchup(
                id=home,
                matchup_period=1,
                scoring_periods=(1,),
                home=MatchupSide(team_id=home, official_points=totals[0]),
                away=MatchupSide(team_id=away, official_points=totals[1]),
                winner=winner,
            ),
        ),
        draft_completed=True,
        draft_in_progress=False,
        draft_picks=(),
    )


def test_a_reconciled_week_is_stored_once_with_bench_points_kept_apart(uow):
    client = Client(period_payload())
    assert league_history.capture_lineups(uow, client, 2026, 1, 1, now=NOW) == "stored"
    assert league_history.capture_lineups(uow, client, 2026, 1, 1, now=NOW) == "unchanged"
    lineup = league_history.read_lineup(uow, 2026, 1)
    assert lineup is not None and len(lineup.entries) == 3
    by_name = {e.display_name: e for e in lineup.entries}
    assert by_name["Synthetic passer"].slot == "QB"
    assert by_name["Kick"].slot == "BENCH" and by_name["Kick"].position == "K"
    assert set(league_history.starter_totals(lineup).values()) == {Decimal("35.66")}
    assert league_history.read_lineup(uow, 2026, 2) is None


def test_a_week_that_does_not_reconcile_is_not_stored(uow):
    payload = period_payload()
    payload["schedule"][0]["home"]["totalPoints"] = 35.67
    with pytest.raises(league_history.HistoryError) as failure:
        league_history.capture_lineups(uow, Client(payload), 2026, 1, 1, now=NOW)
    assert failure.value.code == "LINEUP_SCORE_MISMATCH"
    assert league_history.read_lineup(uow, 2026, 1) is None


def test_a_moved_official_total_makes_a_week_due_again_and_keeps_the_old_capture(uow):
    league_history.capture_lineups(uow, Client(period_payload()), 2026, 1, 1, now=NOW)
    teams = sorted({e.team_id for e in league_history.read_lineup(uow, 2026, 1).entries})
    same = document_for(teams, (Decimal("35.66"), Decimal("35.66")))
    assert league_history.due_lineup_periods(uow, same) == []
    corrected = document_for(teams, (Decimal("37.66"), Decimal("35.66")))
    assert league_history.due_lineup_periods(uow, corrected) == [(1, 1)]
    undecided = document_for(teams, (None, None), winner=None)
    assert league_history.due_lineup_periods(uow, undecided) == []

    payload = period_payload()
    kicker = payload["schedule"][0]["home"]["rosterForCurrentScoringPeriod"]["entries"][1]
    kicker["lineupSlotId"] = 21  # moved to IR: a different capture, the first one kept
    later_read = NOW + timedelta(hours=1)
    league_history.capture_lineups(uow, Client(payload), 2026, 1, 1, now=later_read)
    assert league_history.read_lineup(uow, 2026, 1).captured_at == later_read
    with uow.engine.connect() as c:
        from sqlalchemy import text

        assert c.scalar(text("SELECT count(*) FROM fantasy_lineup_capture")) == 2


# --- R-058 / R-027: transactions ------------------------------------------------------------


def transaction(identity, kind, status, items, processed=None):
    return {
        "id": identity,
        "type": kind,
        "status": status,
        "scoringPeriodId": 9,
        "teamId": 2,
        "memberId": "{NOT-READ}",
        "proposedDate": 1793897778542,
        "processDate": processed,
        "items": items,
    }


def item(kind, player, from_team, to_team, from_slot=-1, to_slot=-1):
    return {
        "type": kind,
        "playerId": player,
        "fromTeamId": from_team,
        "toTeamId": to_team,
        "fromLineupSlotId": from_slot,
        "toLineupSlotId": to_slot,
    }


class TransactionClient:
    def __init__(self, transactions):
        self.transactions = transactions

    def fetch(self, endpoint, options):
        assert options.views == ("mTransactions2",)
        return EndpointResponse(
            endpoint,
            {"seasonId": 2026, "scoringPeriodId": 9, "transactions": self.transactions},
            SourceReceipt("https://lm-api-reads.fantasy.espn.com/synthetic", NOW, "d" * 64, 1),
            "available",
            (),
        )


def test_transactions_are_kept_by_espn_id_and_only_executed_moves_are_listed(uow):
    rows = [
        transaction(
            "w1",
            "WAIVER",
            "EXECUTED",
            [item("ADD", 401, 0, 2), item("DROP", 402, 2, 0, from_slot=20)],
        ),
        transaction("f1", "FREEAGENT", "EXECUTED", [item("ADD", -16004, 0, 2, to_slot=20)]),
        transaction("r1", "ROSTER", "EXECUTED", [item("LINEUP", 401, 0, 0, 20, 0)]),
        transaction("t1", "TRADE_DECLINE", "EXECUTED", []),
        transaction("w2", "WAIVER", "CANCELED", [item("ADD", 403, 0, 2)]),
    ]
    page, receipt = league_history.fetch_transactions(TransactionClient(rows), 2026, 9)
    assert league_history.store_transactions(uow, 2026, page, receipt_sha256=receipt, now=NOW) == 5
    assert league_history.store_transactions(uow, 2026, page, receipt_sha256=receipt, now=NOW) == 0
    moves = league_history.recent_moves(uow, 2026)
    assert {m.espn_id for m in moves} == {"w1", "f1"}
    waiver = next(m for m in moves if m.espn_id == "w1")
    assert [i["type"] for i in waiver.items] == ["ADD", "DROP"]
    assert waiver.items[0]["to_team_id"] == str(waiver.team_id)
    assert waiver.items[1]["from_slot"] == "BENCH" and waiver.items[1]["to_slot"] is None

    rows[4]["status"] = "EXECUTED"  # ESPN processes the claim later
    page, receipt = league_history.fetch_transactions(TransactionClient(rows), 2026, 9)
    assert league_history.store_transactions(uow, 2026, page, receipt_sha256=receipt, now=NOW) == 1
    assert "w2" in {m.espn_id for m in league_history.recent_moves(uow, 2026)}


def test_each_period_is_read_once_then_only_the_latest_two_stay_fresh(uow):
    assert league_history.due_transaction_periods(uow, 2026, 3, NOW, 60) == [1]
    for period in (1, 2, 3):
        rows = {"seasonId": 2026, "scoringPeriodId": period, "transactions": []}
        page = league_history.TransactionPage.model_validate(rows)
        league_history.store_transactions(uow, 2026, page, receipt_sha256="e" * 64, now=NOW)
    assert league_history.due_transaction_periods(uow, 2026, 3, NOW, 60) == []
    assert league_history.due_transaction_periods(
        uow, 2026, 3, NOW + timedelta(seconds=61), 60
    ) == [3, 2]


def test_a_periods_page_keeps_next_weeks_lineup_moves_under_their_own_period(uow):
    """Observed in period 8's page: FUTURE_ROSTER entries for period 9 and one entry for 0."""
    ahead = dict(transaction("n1", "FUTURE_ROSTER", "EXECUTED", []), scoringPeriodId=10)
    zero = dict(transaction("z1", "ROSTER", "EXECUTED", []), scoringPeriodId=0)
    page, receipt = league_history.fetch_transactions(TransactionClient([ahead, zero]), 2026, 9)
    league_history.store_transactions(uow, 2026, page, receipt_sha256=receipt, now=NOW)
    with uow.engine.connect() as c:
        from sqlalchemy import text

        stored = dict(
            c.execute(text("SELECT espn_id, scoring_period FROM fantasy_transaction")).all()
        )
    assert stored == {"n1": 10, "z1": 0}
    assert league_history.recent_moves(uow, 2026) == []


def test_a_transaction_page_from_another_period_is_refused():
    client = TransactionClient([transaction("x", "WAIVER", "EXECUTED", [])])
    with pytest.raises(league_history.HistoryError) as failure:
        league_history.fetch_transactions(client, 2026, 8)
    assert failure.value.code == "SCOPE_MISMATCH"


class LaneClient:
    """ESPN as the league lane sees it: finished-week lineups and per-period transactions."""

    def __init__(self, payload):
        self.payload, self.lineup_reads, self.transaction_reads = payload, 0, []

    def fetch(self, endpoint, options):
        receipt = SourceReceipt("https://lm-api-reads.fantasy.espn.com/synthetic", NOW, "c" * 64, 1)
        if options.views == ("mTransactions2",):
            self.transaction_reads.append(options.scoring_period)
            page = {"seasonId": 2026, "scoringPeriodId": options.scoring_period, "transactions": []}
            return EndpointResponse(endpoint, page, receipt, "available", ())
        self.lineup_reads += 1
        return EndpointResponse(endpoint, deepcopy(self.payload), receipt, "available", ())


def test_league_lane_stores_finished_weeks_and_reads_each_periods_moves(
    uow, tmp_path, captured_input
):
    from arbit_data import freshness
    from arbit_worker.daemon import LINEUP_RETRY_SECONDS, LeagueLane

    def finished_first_week(d):
        d["settings"]["scheduleSettings"]["matchupPeriods"]["1"] = [1]
        d["schedule"][0]["matchupPeriodId"] = 1
        week(d, "TIE", 35.66, 35.66)

    publish(uow, tmp_path, later(captured_input, finished_first_week))
    client = LaneClient(period_payload())
    lane = LeagueLane(uow, 2026, service=object(), history_client=client, clock=lambda: NOW)
    lane._sync_history(NOW)
    assert league_history.read_lineup(uow, 2026, 1) is not None
    assert client.transaction_reads == [1], "the oldest unread period first"
    lane._sync_history(NOW + timedelta(minutes=1))
    assert client.lineup_reads == 1, "a stored week that still matches is not read again"
    assert client.transaction_reads == [1, 2]
    states = {s.source: s.state for s in freshness.read_sources(uow, 2026, NOW)}
    assert states[freshness.LINEUPS] == "current" and states[freshness.TRANSACTIONS] == "current"

    # ESPN later corrects the week, but its lineups no longer reconcile: recorded, then it waits.
    def corrected(d):
        finished_first_week(d)
        week(d, "TIE", 36.66, 35.66)

    current = read_current(uow, 2026, now=NOW)["snapshot_id"]
    publish(uow, tmp_path, later(later(captured_input, finished_first_week, 120), corrected, 60))
    assert read_current(uow, 2026, now=NOW)["snapshot_id"] != current
    broken = period_payload()
    broken["schedule"][0]["home"]["totalPoints"] = 36.66
    lane.history_client = client = LaneClient(broken)
    lane.history_next = None
    lane._sync_history(NOW + timedelta(minutes=2))
    assert client.lineup_reads == 1
    assert freshness.failures_of(uow, freshness.LINEUPS) == 1
    lane.history_next = None
    lane._sync_history(NOW + timedelta(minutes=3))
    assert client.lineup_reads == 1, "a week that didn't reconcile waits before another read"
    lane.history_next = None
    lane._sync_history(NOW + timedelta(seconds=LINEUP_RETRY_SECONDS + 180))
    assert client.lineup_reads == 2
