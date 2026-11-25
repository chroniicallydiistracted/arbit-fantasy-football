"""FFA ownership replay and availability (owner audit Phase B, B5) on hand-built histories."""

from datetime import UTC, datetime, timedelta

import pytest
from arbit_model import ffa_history as fh

T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)
HOLD = timedelta(hours=24)


def tx(espn_id, kind, status, period, hours, items, processed=None):
    return {
        "espn_id": espn_id,
        "type": kind,
        "status": status,
        "scoring_period": period,
        "proposed_at": T0 + timedelta(hours=hours),
        "processed_at": None if processed is None else T0 + timedelta(hours=processed),
        "items": items,
    }


def add(player, team):
    return {"type": "ADD", "player_id": player, "from_team_id": None, "to_team_id": team}


def drop(player, team):
    return {"type": "DROP", "player_id": player, "from_team_id": team, "to_team_id": None}


DRAFT = [("dst-a", "t1"), ("dst-b", "t2"), ("rb-1", "t1")]
LOG = [
    # t1 swaps D/ST A for C as a free agent in period 1.
    tx("1", "FREEAGENT", "EXECUTED", 1, 10, [add("dst-c", "t1"), drop("dst-a", "t1")]),
    # A waiver claim proposed at hour 20 takes effect when processed at hour 40.
    tx("2", "WAIVER", "EXECUTED", 2, 20, [add("dst-a", "t2")], processed=40),
    # Failed, canceled and proposed moves change nothing; lineup moves don't change ownership.
    tx("3", "WAIVER", "FAILED_ROSTERLIMIT", 2, 21, [add("dst-d", "t1")], processed=40),
    tx(
        "4",
        "TRADE_PROPOSAL",
        "CANCELED",
        2,
        22,
        [{"type": "TRADE", "player_id": "rb-1", "from_team_id": "t1", "to_team_id": "t2"}],
    ),
    tx(
        "5",
        "ROSTER",
        "EXECUTED",
        2,
        23,
        [{"type": "LINEUP", "player_id": "rb-1", "from_team_id": "t1", "to_team_id": "t1"}],
    ),
    tx("6", "ROSTER", "EXECUTED", 3, 60, [drop("dst-b", "t2")]),
]


def test_moves_keep_only_executed_adds_and_drops_in_effective_time_order():
    moves = fh.moves(LOG)
    assert [(m.transaction, m.kind) for m in moves] == [
        ("1", "DROP"),  # a drop before the add at the same moment
        ("1", "ADD"),
        ("2", "ADD"),  # processed at hour 40, after being proposed at hour 20
        ("6", "DROP"),
    ]
    assert moves[2].when == T0 + timedelta(hours=40)
    with pytest.raises(ValueError, match="has no time"):
        fh.moves([tx("9", "FREEAGENT", "EXECUTED", 1, 0, [add("x", "t1")]) | {"proposed_at": None}])


def test_replay_by_time_and_by_period():
    moves = fh.moves(LOG)
    at = fh.replay(DRAFT, moves, until=T0 + timedelta(hours=30))
    assert at.owners == {
        "dst-b": "t2",
        "rb-1": "t1",
        "dst-c": "t1",
    }  # A dropped, claim not processed
    later = fh.replay(DRAFT, moves, until=T0 + timedelta(hours=41))
    assert later.owners["dst-a"] == "t2"
    period2 = fh.replay(DRAFT, moves, through_period=2)
    assert period2.owners == {"dst-a": "t2", "dst-b": "t2", "rb-1": "t1", "dst-c": "t1"}
    assert at.problems == later.problems == period2.problems == []


def test_an_inconsistent_log_is_reported_not_trusted():
    bad = fh.moves(
        [tx("7", "FREEAGENT", "EXECUTED", 1, 5, [drop("dst-b", "t1"), add("rb-1", "t2")])]
    )
    result = fh.replay(DRAFT, bad)
    assert len(result.problems) == 2


def test_verify_periods_against_captured_rosters():
    moves = fh.moves(LOG)
    captured = {
        1: {("dst-c", "t1"), ("dst-b", "t2"), ("rb-1", "t1")},
        2: {("dst-c", "t1"), ("dst-b", "t2"), ("rb-1", "t1")},  # missing the claimed dst-a
    }
    checks = fh.verify_periods(DRAFT, moves, captured)
    assert checks[1]["verified"] is True
    assert checks[2]["verified"] is False and checks[2]["extraInReplay"] == 1


def test_availability_respects_the_waiver_hold():
    moves = fh.moves(LOG)
    universe = ["dst-a", "dst-b", "dst-c", "dst-d"]

    def states(hours):
        when = T0 + timedelta(hours=hours)
        return fh.availability(
            universe, fh.replay(DRAFT, moves, until=when).owners, moves, when, HOLD
        )

    early = states(20)  # A dropped at hour 10: within one hold
    assert early["dst-a"] == fh.WAIVERS and early["dst-c"] == "OWNED:t1"
    assert early["dst-d"] == fh.FREE_AGENT  # never rostered
    assert states(45)["dst-a"] == "OWNED:t2"
    mid = states(60 + 30)  # B dropped at hour 60: between one and two holds
    assert mid["dst-b"] == fh.UNCERTAIN
    assert states(60 + 49)["dst-b"] == fh.FREE_AGENT


def test_snapshot_agreement_counts_both_directions():
    agreement = fh.snapshot_agreement(
        {"a": "t1", "b": "t2"}, {"a": "t1", "c": "t1"}, ["a", "b", "c"]
    )
    assert agreement == {"agree": 1, "disagree": 2}
