"""Availability in the owner's order (OWN-073): ESPN's status is final on game day; before that,
the freshest copy of NFL's injury report; otherwise unknown, never assumed active.

Week 9 of 2026, SEA at LA on Sunday 2026-11-08 (kickoff 21:25 UTC). Players:
- 00-Q: questionable all week; ESPN marks him OUT on game day (an inactive).
- 00-L: limited in practice; listed by nflverse only, from a version Arbit held.
- 00-F: full practice; in NFL's capture only.
"""

from datetime import UTC, datetime

import polars as pl
import pytest
from arbit_data.availability.espn_status import PlayerStatus, StatusAsOf
from arbit_model.availability import CaptureRef, availability, is_game_day
from arbit_model.point_in_time import BASIS, KNOWN_FROM, PointInTime
from test_point_in_time import CALENDAR, MemorySource

INJURIES = "injuries/injuries_2026"
SEASON, WEEK = 2026, 9
KICKOFF = datetime(2026, 11, 8, 21, 25, tzinfo=UTC)


def utc(*parts):
    return datetime(*parts, tzinfo=UTC)


def nflverse_row(gsis, status, practice, week=WEEK):
    return {
        "season": SEASON,
        "week": week,
        "team": "SEA",
        "gsis_id": gsis,
        "report_status": status,
        "practice_status": practice,
    }


# nflverse republished Friday's report in the 7 November import (Arbit read daily).
NFLVERSE = {
    INJURIES: (
        [
            (
                utc(2026, 11, 6, 3),
                [nflverse_row("00-Q", None, "Limited Participation in Practice")],
            ),
            (
                utc(2026, 11, 7, 3),
                [
                    nflverse_row("00-Q", "Questionable", "Limited Participation in Practice"),
                    nflverse_row("00-L", "Questionable", "Limited Participation in Practice"),
                    nflverse_row("00-OLD", "Out", "Did Not Participate In Practice", week=8),
                ],
            ),
        ],
        [utc(2026, 11, 5, 3), utc(2026, 11, 8, 3)],
    )
}


def capture_rows(*rows):
    return pl.DataFrame(
        [
            {
                "season": SEASON,
                "week": WEEK,
                "gsis_id": g,
                "game_status": s,
                "practice_status": p,
            }
            for g, s, p in rows
        ]
    )


class FakeSource:
    def __init__(self, captures, espn_status=None, gsis=None):
        self._captures = captures  # [(CaptureRef, frame)]
        self._espn = espn_status
        self._gsis = gsis or {}

    def captures(self):
        return [ref for ref, _ in self._captures]

    def report(self, capture):
        return next(frame for ref, frame in self._captures if ref == capture)

    def espn(self, season, at):
        assert self._espn is not None
        return self._espn

    def gsis_by_entity(self):
        return self._gsis


def ref(at, errors=()):
    return CaptureRef(at, f"m-{at.isoformat()}", (SEASON, "REG", WEEK), tuple(errors))


CAPTURES = [
    # Friday 19:15 Eastern: Q questionable, F full.
    (
        ref(utc(2026, 11, 8, 0, 15)),
        capture_rows(("00-Q", "QUESTIONABLE", "LIMITED"), ("00-F", None, "FULL")),
    ),
    # A capture whose injury read failed carries no report.
    (ref(utc(2026, 11, 8, 17, 0), errors=["nfl.injuries"]), capture_rows()),
    # After kickoff: never used for this decision.
    (ref(utc(2026, 11, 9, 0, 15)), capture_rows(("00-Q", "OUT", "DIDNOT"))),
]


def pit():
    return PointInTime(MemorySource(NFLVERSE), CALENDAR)


PUBLISHED = utc(2026, 11, 8, 19, 50)
LAST_READ = utc(2026, 11, 8, 21, 20)


def espn(current, players, published=PUBLISHED, read=LAST_READ):
    return StatusAsOf(
        at=KICKOFF,
        document_published_at=published,
        last_read_at=read,
        current=current,
        players={e: PlayerStatus(e, code, None) for e, code in players.items()},
    )


def by_player(reading):
    return {row["gsis_id"]: row for row in reading.rows}


def test_before_game_day_the_freshest_copy_of_nfls_report_counts():
    saturday = utc(2026, 11, 8, 2)  # Friday night Eastern, before nflverse's next import
    reading = availability(
        FakeSource(CAPTURES), pit(), season=SEASON, week=WEEK, at=saturday, game_day=False
    )
    rows = by_player(reading)
    # Arbit's own capture (00:15 UTC) is fresher than nflverse's import (03:00 UTC on the 7th).
    assert rows["00-Q"]["source"] == "nfl-report"
    assert (rows["00-Q"]["status"], rows["00-Q"]["practice"]) == ("QUESTIONABLE", "LIMITED")
    assert rows["00-Q"][KNOWN_FROM] == utc(2026, 11, 8, 0, 15)
    assert rows["00-F"]["status"] is None and rows["00-F"]["practice"] == "FULL"
    # nflverse lists L; the capture doesn't. Week 8's row stays out.
    assert rows["00-L"]["source"] == "nflverse-report"
    assert rows["00-L"]["practice"] == "LIMITED"
    assert "00-OLD" not in rows
    assert not any(row["final"] for row in reading.rows)
    assert reading.lineage["gameDayUnknown"] is False


def test_when_captures_stop_the_newer_nflverse_copy_wins():
    # Only the failed and post-kickoff captures exist; nflverse is the freshest copy.
    later = [c for c in CAPTURES if c[0].observed_at.hour != 0 or c[0].observed_at.day == 9]
    reading = availability(
        FakeSource(later),
        pit(),
        season=SEASON,
        week=WEEK,
        at=utc(2026, 11, 8, 12),
        game_day=False,
    )
    rows = by_player(reading)
    assert rows["00-Q"]["source"] == "nflverse-report"
    assert rows["00-Q"][BASIS] == "observed"
    assert reading.lineage["nflCapture"] is None


def test_on_game_day_a_current_espn_status_is_final():
    status = espn(True, {"e-Q": "OUT", "e-F": "ACTIVE", "e-unmapped": "OUT"})
    source = FakeSource(CAPTURES, status, gsis={"e-Q": "00-Q", "e-F": "00-F"})
    reading = availability(source, pit(), season=SEASON, week=WEEK, at=KICKOFF, game_day=True)
    rows = by_player(reading)
    assert (rows["00-Q"]["status"], rows["00-Q"]["source"], rows["00-Q"]["final"]) == (
        "OUT",
        "espn-game-day",
        True,
    )
    assert rows["00-Q"][KNOWN_FROM] == utc(2026, 11, 8, 19, 50)
    assert rows["00-F"]["status"] == "ACTIVE" and rows["00-F"]["final"] is True
    # ESPN doesn't list L: the report stands, not final.
    assert rows["00-L"]["source"] == "nflverse-report" and rows["00-L"]["final"] is False
    assert reading.lineage["espn"]["unmapped"] == 1
    assert reading.lineage["gameDayUnknown"] is False


def test_on_game_day_without_a_current_espn_read_game_day_status_is_unknown():
    stale = espn(False, {"e-Q": "OUT"}, read=utc(2026, 11, 8, 20, 0))
    source = FakeSource(CAPTURES, stale, gsis={"e-Q": "00-Q"})
    reading = availability(source, pit(), season=SEASON, week=WEEK, at=KICKOFF, game_day=True)
    rows = by_player(reading)
    assert rows["00-Q"]["source"] == "nfl-report"  # last known report, not ESPN's stale OUT
    assert not any(row["final"] for row in reading.rows)
    assert reading.lineage["gameDayUnknown"] is True


def test_game_day_is_the_eastern_date_up_to_kickoff():
    game = CALENDAR.game("2026_09_SEA_LA")
    assert is_game_day(game, utc(2026, 11, 8, 5, 30))  # 00:30 Eastern, Sunday
    assert is_game_day(game, KICKOFF)
    assert not is_game_day(game, utc(2026, 11, 8, 4, 30))  # 23:30 Eastern, Saturday
    assert not is_game_day(game, utc(2026, 11, 8, 21, 26))  # after kickoff
    with pytest.raises(ValueError, match="DECISION_TIME_NEEDS_TIMEZONE"):
        is_game_day(game, datetime(2026, 11, 8, 12))
