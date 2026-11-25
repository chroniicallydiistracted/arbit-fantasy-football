"""The prospective completion gate (owner directive AUD-01c), tested on the gate itself.

Each case the directive lists: only the first game final; several games unfinished; every game
final but labels missing; a missed week; a retrospective forecast for a missed week; the full
valid window; a subset; an archive failing timing or integrity checks; duplicate archives.
"""

from datetime import UTC, datetime, timedelta

import polars as pl
from arbit_model.dvp import window as w

WEEKS = [12, 13, 14]
GRACE = timedelta(days=4)
CUT = {wk: datetime(2026, 11, 26, 1, tzinfo=UTC) + timedelta(weeks=wk - 12) for wk in WEEKS}
LATE = datetime(2027, 1, 20, tzinfo=UTC)  # after every game


def entry(week, **overrides):
    base = {
        "week": week,
        "classification": "PROSPECTIVE",
        "folder": f"week-{week}",
        "generatedAt": (CUT[week] - timedelta(days=1)).isoformat(),
        "archivedAt": (CUT[week] - timedelta(days=1) + timedelta(seconds=5)).isoformat(),
        "entrySha256": f"e{week}",
    }
    return base | overrides


def published(week, hours_before=24, verified=True):
    return {
        "ledgerEntrySha256": f"e{week}",
        "verified": verified,
        "kind": "github-branch",
        "externalTimestamp": (CUT[week] - timedelta(hours=hours_before)).isoformat(),
    }


def archived(week, *, entries=None, files_match=True, publications=None):
    found = entries if entries is not None else [entry(week)]
    return w.WeekArchive(
        week=week,
        cutoff=CUT[week],
        entries=found,
        files_match={e["folder"]: files_match for e in found if "folder" in e},
        publications=publications if publications is not None else [published(week)],
    )


def schedule(week, final=2, games=2):
    kickoff = CUT[week]
    rows = [
        {
            "week": week,
            "game_id": f"g{week}-{i}",
            "kickoff": kickoff + timedelta(hours=3 * i),
            "available_at": kickoff + timedelta(days=1),
            "status": "completed" if i < final else "not_completed",
        }
        for i in range(games)
    ]
    return pl.DataFrame(rows)


def labelled(week, games=2, missing=0, invalid=0):
    rows = []
    for g in range(games):
        for t in range(w.PER_GAME_TARGETS):
            rows.append({"week": week, "game_id": f"g{week}-{g}", "label_status": "valid", "t": t})
    frame = pl.DataFrame(rows)
    statuses = ["missing"] * missing + ["invalid_refused_line"] * invalid
    if statuses:
        frame = frame.with_columns(
            pl.Series(
                "label_status",
                statuses + frame.get_column("label_status").to_list()[len(statuses) :],
            )
        )
    return frame


def gate(archives, labels, weeks=WEEKS, now=LATE):
    a = {wk: w.archive_state(archives[wk], now) for wk in weeks}
    lab = {wk: labels[wk] for wk in weeks}
    return w.window_state(weeks, WEEKS, a, lab), a


def full_labels(now=LATE):
    return {wk: w.label_state(wk, schedule(wk), labelled(wk), now, GRACE) for wk in WEEKS}


def test_only_the_first_game_final_keeps_the_week_open():
    now = CUT[12] + timedelta(days=1, hours=1)
    state = w.label_state(12, schedule(12, final=1, games=3), labelled(12, games=3), now, GRACE)
    assert state["status"] == w.AWAITING_GAMES and len(state["awaitingResult"]) == 2
    labels = full_labels() | {12: state}
    result, _ = gate({wk: archived(wk) for wk in WEEKS}, labels, now=now)
    assert result["status"] == w.INTERIM and not result["confirmationAllowed"]


def test_several_unfinished_games_and_results_not_yet_available():
    early = CUT[12] + timedelta(hours=2)
    state = w.label_state(12, schedule(12, final=0, games=4), labelled(12, games=4), early, GRACE)
    assert state["status"] == w.AWAITING_GAMES and len(state["awaitingResult"]) == 4
    # Final, but the results aren't available under the timing rule yet.
    state = w.label_state(12, schedule(12), labelled(12), CUT[12] + timedelta(hours=8), GRACE)
    assert state["status"] == w.AWAITING_GAMES and state["resultsNotYetAvailable"]


def test_every_game_final_but_labels_missing_is_not_complete():
    state = w.label_state(13, schedule(13), labelled(13, missing=3), LATE, GRACE)
    assert state["status"] == w.LABELS_INCOMPLETE and state["labels"]["missing"] == 3
    result, _ = gate({wk: archived(wk) for wk in WEEKS}, full_labels() | {13: state})
    assert result["status"] == w.INTERIM and not result["confirmationAllowed"]
    # A final game with no archived forecasts at all is also incomplete.
    state = w.label_state(13, schedule(13, games=3, final=3), labelled(13, games=2), LATE, GRACE)
    assert state["status"] == w.LABELS_INCOMPLETE and state["finalGamesWithoutForecasts"]


def test_invalid_labels_with_a_recorded_reason_do_not_hold_the_week_open():
    state = w.label_state(13, schedule(13), labelled(13, invalid=2), LATE, GRACE)
    assert state["status"] == w.LABELLED and state["invalidLabels"] == {"invalid_refused_line": 2}


def test_a_postponed_game_is_recorded_and_does_not_hold_the_week_open():
    games = schedule(14, final=1, games=2)
    state = w.label_state(14, games, labelled(14, games=1), LATE, GRACE)
    assert state["status"] == w.LABELLED and state["postponedOrCanceled"] == ["g14-1"]


def test_a_missed_week_makes_the_window_incomplete_never_confirmed():
    archives = {wk: archived(wk) for wk in WEEKS}
    archives[13] = archived(13, entries=[], publications=[])
    result, states = gate(archives, full_labels())
    assert states[13]["status"] == w.MISSED
    assert result["status"] == w.INCOMPLETE_WINDOW and not result["confirmationAllowed"]


def test_a_retrospective_forecast_never_fills_a_missed_week():
    retro = {
        "week": 13,
        "classification": "RETROSPECTIVE",
        "folder": "week-13-retrospective",
        "generatedAt": (CUT[13] + timedelta(days=2)).isoformat(),
        "entrySha256": "r13",
    }
    missed = {"week": 13, "classification": "MISSED", "reason": "no forecast before the cutoff"}
    archives = {wk: archived(wk) for wk in WEEKS}
    archives[13] = archived(13, entries=[missed, retro], publications=[])
    result, states = gate(archives, full_labels())
    assert states[13]["status"] == w.MISSED and states[13]["evidence"]["retrospectiveArchives"] == 1
    assert result["status"] == w.INCOMPLETE_WINDOW


def test_the_full_valid_window_is_complete():
    result, states = gate({wk: archived(wk) for wk in WEEKS}, full_labels())
    assert all(s["status"] == w.PROSPECTIVE for s in states.values())
    assert result == {"status": w.COMPLETE, "confirmationAllowed": True, "reasons": []}


def test_a_subset_of_the_window_is_interim():
    archives = {wk: archived(wk) for wk in WEEKS}
    result, _ = gate(archives, full_labels(), weeks=[12, 13])
    assert result["status"] == w.INTERIM and not result["confirmationAllowed"]


def test_an_archive_failing_timing_checks_is_not_prospective():
    archives = {wk: archived(wk) for wk in WEEKS}
    # Generated before the cutoff, but its commitment reached GitHub only afterward.
    archives[12] = archived(12, publications=[published(12, hours_before=-1)])
    _, states = gate(archives, full_labels())
    assert states[12]["status"] == w.MISSED
    assert "no verified external commitment before the cutoff" in states[12]["reasons"]
    # Durable archival finished after the cutoff.
    late = entry(12, archivedAt=(CUT[12] + timedelta(minutes=1)).isoformat())
    archives[12] = archived(12, entries=[late])
    _, states = gate(archives, full_labels())
    assert states[12]["status"] == w.MISSED
    # An unverified publication record doesn't count.
    archives[12] = archived(12, publications=[published(12, verified=False)])
    result, states = gate(archives, full_labels())
    assert states[12]["status"] == w.MISSED and result["status"] == w.INCOMPLETE_WINDOW
    # Before the cutoff, a week waiting for its commitment is still pending, not missed.
    pending = w.archive_state(archived(12, publications=[]), CUT[12] - timedelta(hours=1))
    assert pending["status"] == w.PENDING


def test_an_archive_failing_integrity_checks_blocks_the_window():
    archives = {wk: archived(wk) for wk in WEEKS}
    archives[14] = archived(14, files_match=False)
    result, states = gate(archives, full_labels())
    assert states[14]["status"] == w.BLOCKED and result["status"] == w.BLOCKED


def test_duplicate_or_conflicting_archives_block_the_window():
    archives = {wk: archived(wk) for wk in WEEKS}
    archives[12] = archived(12, entries=[entry(12), entry(12, folder="week-12-b")])
    result, _ = gate(archives, full_labels())
    assert result["status"] == w.BLOCKED
    missed = {"week": 12, "classification": "MISSED", "reason": "x"}
    archives[12] = archived(12, entries=[entry(12), missed])
    result, _ = gate(archives, full_labels())
    assert result["status"] == w.BLOCKED


def test_the_amendment_leaves_the_original_declaration_and_frozen_rules_unchanged():
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    amendment = json.loads((root / "config/dvp/prospective-amendment-1.json").read_text())
    original = root / amendment["amends"]["path"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == amendment["amends"]["sha256"]
    gate_states = amendment["completionGate"]["window"]
    assert set(gate_states) == {w.BLOCKED, w.INTERIM, w.INCOMPLETE_WINDOW, w.COMPLETE}
    assert amendment["write_to_production"] is False


def readiness_case():
    kickoff = datetime(2026, 11, 22, 18, tzinfo=UTC)
    games = pl.DataFrame(
        {
            "season": [2026] * 4,
            "week": [11] * 4,
            "game_id": ["a", "b", "c", "d"],
            "kickoff": [kickoff] * 4,
            "available_at": [kickoff + timedelta(hours=18)] * 4,
            "status": ["completed", "completed", "completed", "not_completed"],
        }
    )
    cells = []
    for gid, n, invalid in (("a", 12, 0), ("b", 12, 1), ("c", 5, 0)):
        for i in range(n):
            cells.append(
                {
                    "season": 2026,
                    "game_id": gid,
                    "offense": f"T{i % 2}",
                    "position": f"P{i // 2}",
                    "status": "invalid_refused_line" if i < invalid else "valid",
                }
            )
    return kickoff, games, pl.DataFrame(cells)


def test_readiness_names_the_state_of_every_earlier_game():
    kickoff, games, cells = readiness_case()
    now = kickoff + timedelta(days=2)
    # The held statistics file predates game c's results; the catalog knows nothing newer.
    held = kickoff - timedelta(hours=1)
    ready, detail = w.game_readiness(games, cells, 2026, 12, now, GRACE, held, held)
    assert not ready
    assert detail["states"] == {
        w.AWAITING_RESULT: 1,
        w.ELIGIBLE_VERIFIED: 1,
        w.RETRIEVED_INVALID: 1,
        w.SOURCE_NOT_YET_PUBLISHED: 1,
    }
    # A newer revision is in the catalog but wasn't imported.
    _, detail = w.game_readiness(
        games, cells, 2026, 12, now, GRACE, held, kickoff + timedelta(hours=10)
    )
    assert detail["blocking"][w.PUBLISHED_NOT_RETRIEVED] == ["c"]
    # The held file postdates the game, yet cells are missing: an integrity failure.
    late = kickoff + timedelta(hours=9)
    _, detail = w.game_readiness(games, cells, 2026, 12, now, GRACE, late, late)
    assert detail["blocking"][w.DATA_INTEGRITY_FAILURE] == ["c"]
    # Long after kickoff, the unfinished game is recorded and stops blocking.
    full = cells.filter(pl.col("game_id") != "c")
    ready, detail = w.game_readiness(
        games.filter(pl.col("game_id") != "c"),
        full,
        2026,
        12,
        kickoff + timedelta(days=5),
        GRACE,
        late,
        late,
    )
    assert ready and detail["postponedOrCanceled"] == ["d"] and detail["retrievedInvalid"] == ["b"]
    # A final game is not usable before its results are available under the rule.
    ready, detail = w.game_readiness(
        games.filter(pl.col("game_id") == "a"),
        full,
        2026,
        12,
        kickoff + timedelta(hours=6),
        GRACE,
        late,
        late,
    )
    assert not ready and detail["blocking"] == {w.NOT_YET_AVAILABLE: ["a"]}
