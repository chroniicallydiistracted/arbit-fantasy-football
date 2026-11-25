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


# Final directive PB-AUD-02 (fail closed) and the v2 availability rule.


def test_an_executed_trade_or_unknown_ownership_change_stops_the_replay():
    trade = tx(
        "8",
        "TRADE_ACCEPT",
        "EXECUTED",
        3,
        30,
        [{"type": "TRADE", "player_id": "rb-1", "from_team_id": "t1", "to_team_id": "t2"}],
    )
    with pytest.raises(fh.UnsupportedHistory, match="does not support"):
        fh.moves([*LOG, trade])
    # An add recorded on a type the replay doesn't know.
    odd = tx("9", "KEEPER", "EXECUTED", 3, 30, [add("dst-d", "t1")])
    with pytest.raises(fh.UnsupportedHistory):
        fh.moves([odd])
    unknown = tx("10", "ROSTER", "EXECUTED", 3, 30, [{"type": "SWAP", "player_id": "x"}])
    with pytest.raises(fh.UnsupportedHistory, match="unknown item types"):
        fh.moves([unknown])
    # A canceled trade proposal changes nothing and is fine (as in LOG).
    assert fh.moves(LOG)


def test_an_executed_waiver_without_its_processing_time_stops_the_replay():
    claim = tx("11", "WAIVER", "EXECUTED", 2, 20, [add("dst-d", "t1")])  # processed=None
    with pytest.raises(fh.UnsupportedHistory, match="no processing time"):
        fh.moves([claim])
    # A free-agent add takes effect when made: its proposal time is its effective time.
    assert fh.moves([tx("12", "FREEAGENT", "EXECUTED", 2, 20, [add("dst-d", "t1")])])[0].when


def test_conflicting_transitions_are_reported_not_corrected():
    twice = fh.moves(
        [
            tx("13", "FREEAGENT", "EXECUTED", 1, 5, [add("dst-d", "t1")]),
            tx("14", "FREEAGENT", "EXECUTED", 1, 6, [add("dst-d", "t2")]),  # still held by t1
        ]
    )
    result = fh.replay(DRAFT, twice)
    assert result.problems == ["14: add of a held player"]


def test_simultaneous_moves_apply_drops_first_and_later_moves_wait():
    same = fh.moves(
        [
            tx("15", "FREEAGENT", "EXECUTED", 1, 5, [add("dst-a", "t2")]),
            tx("16", "ROSTER", "EXECUTED", 1, 5, [drop("dst-a", "t1")]),
        ]
    )
    assert [m.kind for m in same] == ["DROP", "ADD"]
    assert fh.replay(DRAFT, same).problems == []
    # A move effective after the moment asked about is not applied.
    later = fh.replay(DRAFT, same, until=T0 + timedelta(hours=4))
    assert later.owners["dst-a"] == "t1" and later.applied == 0


def test_the_draft_is_validated_before_replay():
    assert fh.validate_draft(DRAFT, ["t1", "t2"]) == []
    problems = fh.validate_draft([*DRAFT, ("dst-a", "t2"), ("k-1", "t9")], ["t1", "t2"])
    assert problems == ["dst-a drafted twice", "k-1 drafted by a team outside the league"]


def test_rule_v2_holds_drops_until_processing_and_locks_started_games_until_wednesday():
    from datetime import UTC, date, datetime

    moments = fh.processing_moments(
        date(2026, 11, 1),
        date(2026, 11, 20),
        ["MONDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"],
    )
    assert all(m.astimezone(fh.PACIFIC).weekday() != 1 for m in moments)  # never Tuesday
    # Midnight Pacific: 07:00 UTC on 2026-11-01 (before that night's 02:00 clock change), then 08:00.
    assert [m.astimezone(UTC).hour for m in moments[:2]] == [7, 8]
    dropped = datetime(2026, 11, 3, 18, tzinfo=UTC)  # Tuesday 10:00 Pacific
    log = fh.moves(
        [tx("17", "ROSTER", "EXECUTED", 9, 0, [drop("dst-x", "t1")]) | {"proposed_at": dropped}]
    )
    kickoff = datetime(2026, 11, 8, 18, tzinfo=UTC)  # Sunday game
    states = lambda at: fh.availability_v2(  # noqa: E731
        ["dst-x", "dst-y"],
        {},
        log,
        at,
        timedelta(hours=24),
        moments,
        {"dst-x": [kickoff], "dst-y": [kickoff]},
    )
    # Hold ends Wednesday 10:00 Pacific; the first processing after that is Thursday 00:00.
    assert states(datetime(2026, 11, 5, 7, tzinfo=UTC))["dst-x"][0] == fh.WAIVERS
    assert states(datetime(2026, 11, 5, 9, tzinfo=UTC))["dst-x"][0] == fh.FREE_AGENT
    # After its Sunday kickoff an unowned unit is on waivers until Wednesday's processing.
    assert states(datetime(2026, 11, 9, 12, tzinfo=UTC))["dst-y"][0] == fh.WAIVERS
    assert states(datetime(2026, 11, 10, 12, tzinfo=UTC))["dst-y"][0] == fh.WAIVERS  # Tuesday
    assert states(datetime(2026, 11, 11, 9, tzinfo=UTC))["dst-y"][0] == fh.FREE_AGENT
    # At the exact kickoff (a preweek cutoff is the first kickoff) the game has not started.
    assert states(kickoff)["dst-y"][0] == fh.FREE_AGENT
    owned = fh.availability_v2(
        ["dst-y"], {"dst-y": "t2"}, log, kickoff, timedelta(hours=24), moments, {}
    )
    assert owned["dst-y"][0] == "OWNED:t2"
