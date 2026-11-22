"""Game-day availability for the Model: NFL's injury report twice a day (OWN-063) and ESPN's
fantasy injury status as of a moment (OWN-064)."""

import json
from datetime import UTC, datetime, timedelta

import pyarrow.parquet as pq
import pytest
from arbit_data.availability import schedule
from arbit_data.availability.capture import INDEX, capture
from arbit_data.availability.espn_status import CURRENT_WITHIN, status_from
from arbit_data.availability.sources import INJURY_PAGE, game_statuses, read_injury_report
from arbit_data.errors import SourceError


def injury(week, gsis, status=None):
    return {
        "season": 2026,
        "seasonType": "REG",
        "week": week,
        "team": {"id": "team-uuid", "fullName": "Atlanta Falcons"},
        "person": {"id": "person-" + gsis, "gsisId": gsis, "displayName": "Player " + gsis},
        "injuries": ["Knee"],
        "injuryStatus": status,
        "practiceDays": [{"date": "2026-11-11", "status": "DIDNOT"}],
        "practiceStatus": "DIDNOT",
        "position": "WR",
    }


class Pages:
    """NFL's API: the week for a date, and the injury report in pages with a token."""

    def __init__(self, pages, week=(2026, "REG", 10)):
        self.pages, self.week, self.calls = pages, week, []
        self.tokens = [f"t{i}" for i in range(len(pages))]

    def get(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        if path.startswith("/football/v2/weeks/date/"):
            season, kind, number = self.week
            return {"season": season, "seasonType": kind, "week": number}, b"{}"
        index = 0 if "pageToken" not in params else self.tokens.index(params["pageToken"]) + 1
        body = {"injuries": self.pages[index], "pagination": {"token": self.tokens[index]}}
        return body, json.dumps(body).encode()


def full_page(week):
    return [injury(week, f"00-{week:02d}{i:05d}") for i in range(INJURY_PAGE)]


def test_injury_report_follows_page_tokens_to_the_short_last_page():
    nfl = Pages([full_page(1), full_page(2), [injury(10, "00-1", "OUT")]])

    rows, responses = read_injury_report(nfl, 2026, "REG")

    assert len(rows) == 2 * INJURY_PAGE + 1
    assert [c[1].get("pageToken") for c in nfl.calls] == [None, "t0", "t1"]
    assert len(responses) == 3 and responses[0].params["limit"] == INJURY_PAGE


def test_injury_report_refuses_a_page_token_that_repeats():
    class Stuck:
        def get(self, path, params=None):
            return {"injuries": full_page(1), "pagination": {"token": "same"}}, b"{}"

    with pytest.raises(SourceError, match="NFL_INJURIES_PAGING"):
        read_injury_report(Stuck(), 2026, "REG")


def test_game_status_keeps_no_status_as_none_and_practice_days():
    rows = game_statuses([injury(10, "00-1", "OUT"), injury(10, "00-2")])

    assert rows[0].game_status == "OUT" and rows[1].game_status is None
    assert rows[0].gsis_id == "00-1" and rows[0].team_name == "Atlanta Falcons"
    assert rows[0].practice_days == (("2026-11-11", "DIDNOT"),)


def clock(*minutes):
    start = datetime(2026, 11, 12, 17, 0, tzinfo=UTC)
    times = iter(start + timedelta(minutes=m) for m in minutes)
    return lambda: next(times)


def test_a_capture_keeps_original_bytes_the_table_and_when_it_finished(tmp_path):
    nfl = Pages([[injury(10, "00-1", "OUT"), injury(10, "00-2")]])

    result = capture(nfl, tmp_path, season=2026, clock=clock(0, 3))

    assert result.errors == {} and result.week == (2026, "REG", 10)
    # Known only once the reads finished, not when they started.
    assert result.observed_at == datetime(2026, 11, 12, 17, 3, tzinfo=UTC)
    manifest = json.loads((tmp_path / "objects" / result.manifest).read_text())
    assert manifest["counts"] == {"gameStatusRows": 2, "gameStatusOut": 1, "responses": 1}
    for source in manifest["sources"]:
        assert (tmp_path / "objects" / source["sha256"]).stat().st_size == source["bytes"]
    table = pq.read_table(tmp_path / "objects" / manifest["tables"]["gameStatus"]["parquet"])
    assert [r["game_status"] for r in table.to_pylist()] == ["OUT", None]
    index = [json.loads(line) for line in (tmp_path / INDEX).read_text().splitlines()]
    assert index == [
        {
            "errors": [],
            "manifest": result.manifest,
            "observedAt": "2026-11-12T17:03:00+00:00",
            "week": [2026, "REG", 10],
        }
    ]


def test_a_failed_read_is_recorded_and_the_capture_still_kept(tmp_path):
    class Down(Pages):
        def get(self, path, params=None):
            if path == "/football/v2/injuries":
                raise SourceError("NFL_API_HTTP_503")
            return super().get(path, params)

    result = capture(Down([[]]), tmp_path, season=2026, clock=clock(0, 1))

    assert result.errors == {"nfl.injuries": "NFL_API_HTTP_503"}
    assert json.loads((tmp_path / INDEX).read_text())["errors"] == ["nfl.injuries"]


def test_the_postseason_report_is_read_in_the_postseason(tmp_path):
    nfl = Pages([[injury(19, "00-1")]], week=(2026, "POST", 19))

    capture(nfl, tmp_path, season=2026, clock=clock(0, 1))

    reads = [params for path, params in nfl.calls if path == "/football/v2/injuries"]
    assert reads and reads[0]["seasonType"] == "POST"


@pytest.mark.parametrize(
    ("now", "latest", "following"),
    [
        # Eastern Standard Time (UTC-5), Thursday 12 November.
        ("2026-11-12T16:59:00+00:00", "2026-11-12T00:15:00+00:00", "2026-11-12T17:00:00+00:00"),
        ("2026-11-12T17:00:00+00:00", "2026-11-12T17:00:00+00:00", "2026-11-13T00:15:00+00:00"),
        ("2026-11-13T00:20:00+00:00", "2026-11-13T00:15:00+00:00", "2026-11-13T17:00:00+00:00"),
        # Eastern Daylight Time (UTC-4) in October.
        ("2026-10-15T16:00:00+00:00", "2026-10-15T16:00:00+00:00", "2026-10-15T23:15:00+00:00"),
    ],
)
def test_reads_fall_at_noon_and_quarter_past_seven_eastern(now, latest, following):
    moment = datetime.fromisoformat(now)
    assert schedule.latest_slot(moment) == datetime.fromisoformat(latest)
    assert schedule.next_slot(moment) == datetime.fromisoformat(following)


# ESPN fantasy status (OWN-064). Kickoff 18:00 UTC; inactives posted about 16:30.
KICKOFF = datetime(2026, 11, 8, 18, 0, tzinfo=UTC)
PLAYERS = [
    {"id": "e-1", "injury_status": "OUT", "injured": True},
    {"id": "e-2", "injury_status": "QUESTIONABLE", "injured": True},
    {"id": "e-3", "injury_status": "ACTIVE", "injured": False},
    {"id": "e-4", "injury_status": None, "injured": False},
]


def test_espn_status_is_current_when_arbit_read_espn_just_before():
    found = status_from(
        KICKOFF, (KICKOFF - timedelta(minutes=40), PLAYERS), KICKOFF - timedelta(minutes=1)
    )

    assert found.current
    assert found.players["e-1"].designation == "out"
    assert found.players["e-2"].designation == "questionable"
    assert found.players["e-3"].designation is None and found.players["e-3"].code == "ACTIVE"
    assert found.players["e-4"].code is None


def test_espn_status_is_stale_when_reads_stopped_before_inactives():
    # The PC slept hours before kickoff: the last read predates the inactive list.
    found = status_from(
        KICKOFF,
        (KICKOFF - timedelta(hours=6), PLAYERS),
        KICKOFF - CURRENT_WITHIN - timedelta(seconds=1),
    )
    assert not found.current
    assert found.players["e-2"].designation == "questionable", "kept, but marked stale"


def test_espn_status_with_no_document_or_no_read_is_not_current():
    assert not status_from(KICKOFF, None, KICKOFF).current
    assert not status_from(KICKOFF, (KICKOFF, PLAYERS), None).current


def test_espn_status_refuses_evidence_from_after_the_moment():
    with pytest.raises(ValueError, match="FUTURE_EVIDENCE"):
        status_from(KICKOFF, (KICKOFF + timedelta(seconds=1), PLAYERS), KICKOFF)
    with pytest.raises(ValueError, match="FUTURE_EVIDENCE"):
        status_from(KICKOFF, (KICKOFF, PLAYERS), KICKOFF + timedelta(seconds=1))


@pytest.mark.parametrize(("minutes", "current"), [(10, True), (20, False), (343, False)])
def test_espn_status_counts_as_current_only_within_minutes_of_a_read(minutes, current):
    # Reads run every 1 to 5 minutes; 343 minutes is 1 November's gap before the 1 PM games.
    read = KICKOFF - timedelta(minutes=minutes)
    assert status_from(KICKOFF, (read, PLAYERS), read).current is current
