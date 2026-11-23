"""Point-in-time reads (ADR-007 as amended by OWN-066, M3 slice 3).

One synthetic 2026 statistics file carries every case. Arbit first read it on 6 November (so
earlier weeks are retrospective), read it daily through 10 November, and then not again until
22 November (the R-068 outage):

- week 8, game A: in the first version; timed by the family rule.
- week 9, game B: first held by the 9 November read, a day after the previous read: observed.
  The 22 November version revises it (a stat correction published after the gap).
- week 8, game L: nflverse published it late; it is first held after the gap. Its rule time is
  before the gap started, so the gap start bounds it.
- week 10, Thursday game C and Sunday game D: published during the gap, first held on
  22 November.
"""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta

import pytest
from arbit_model.point_in_time import BASIS, KNOWN_FROM, PointInTime, PolicyRefused
from arbit_model.timing import (
    BASES,
    Calendar,
    depth_rows,
    injury_rows,
    next_publication,
    spec_for,
)
from arbit_model.vintages import KeyHistory, Version


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


SCHEDULE = [
    # (game_id, week, gameday, gametime ET, away, home, game_type)
    ("2026_08_NE_SEA", 8, "2026-10-25", "16:05", "NE", "SEA", "REG"),
    ("2026_08_BUF_MIA", 8, "2026-10-26", "20:15", "BUF", "MIA", "REG"),
    ("2026_09_SEA_LA", 9, "2026-11-08", "16:25", "SEA", "LA", "REG"),
    ("2026_10_KC_DEN", 10, "2026-11-12", "20:15", "KC", "DEN", "REG"),
    ("2026_10_SEA_SF", 10, "2026-11-15", "13:00", "SEA", "SF", "REG"),
    ("2026_11_SEA_ARI", 11, "2026-11-22", "16:25", "SEA", "ARI", "REG"),
    ("2024_05_NE_MIA", 5, "2024-10-06", "13:00", "NE", "MIA", "REG"),
    ("2024_06_NE_HOU", 6, "2024-10-13", "13:00", "NE", "HOU", "REG"),
]
CALENDAR = Calendar(
    {
        "game_id": g,
        "old_game_id": None,
        "season": int(g[:4]),
        "week": week,
        "game_type": kind,
        "gameday": day,
        "gametime": clock,
        "away_team": away,
        "home_team": home,
    }
    for g, week, day, clock, away, home, kind in SCHEDULE
)

STATS = "stats_player/stats_player_week_2026"


def stat(game: str, player: str, receptions: int) -> dict:
    team = game.split("_")[3]
    return {
        "game_id": game,
        "season": int(game[:4]),
        "week": int(game[5:7]),
        "team": team,
        "player_id": player,
        "receptions": receptions,
    }


A = stat("2026_08_NE_SEA", "00-A", 5)
L = stat("2026_08_BUF_MIA", "00-L", 7)
B = stat("2026_09_SEA_LA", "00-B", 6)
B_CORRECTED = {**B, "receptions": 7}
C = stat("2026_10_KC_DEN", "00-C", 3)
D = stat("2026_10_SEA_SF", "00-D", 9)

V0 = utc(2026, 11, 6, 3)
V1 = utc(2026, 11, 9, 3)
GAP_START = utc(2026, 11, 10, 4)
V2 = utc(2026, 11, 22, 22, 45)
STATS_FILE = (
    [(V0, [A]), (V1, [A, B]), (V2, [A, L, B_CORRECTED, C, D])],
    [utc(2026, 11, 7, 3), utc(2026, 11, 8, 3), GAP_START],
)


class MemorySource:
    """Versions and reads by key, as the database would hold them."""

    def __init__(self, files):
        self.files = files

    def history(self, key):
        versions, extra_reads = self.files.get(key, ([], []))
        held = tuple(Version(f"{key}#{i}", f"{key}#{i}", at) for i, (at, _) in enumerate(versions))
        reads = tuple(sorted({*extra_reads, *(at for at, _ in versions)}))
        return KeyHistory(key, held, reads)

    def table(self, version, columns):
        key, index = version.parquet.rsplit("#", 1)
        rows = self.files[key][0][int(index)][1]
        return [{c: row.get(c) for c in columns} for row in rows]


def reader(files, **kwargs):
    return PointInTime(MemorySource(files), CALENDAR, **kwargs)


COLUMNS = ("game_id", "player_id", "receptions")


def by_player(reading):
    return {row["player_id"]: row for row in reading.rows}


def test_inside_the_gap_rows_published_before_the_decision_count_from_their_rule():
    # Sunday of week 10, inside the outage: Thursday's game had been published; Sunday's had not.
    at = utc(2026, 11, 15, 18)
    reading = reader({STATS: STATS_FILE}).read(STATS, COLUMNS, at)
    rows = by_player(reading)

    assert set(rows) == {"00-A", "00-B", "00-L", "00-C"}
    # Before Arbit's first read: the family rule, 12:00 UTC the day after the game.
    assert rows["00-A"][BASIS] == "retrospective-rule"
    assert rows["00-A"][KNOWN_FROM] == utc(2026, 10, 26, 12)
    # Held at the decision time, read a day after the previous read.
    assert rows["00-B"][BASIS] == "observed"
    assert rows["00-B"][KNOWN_FROM] == V1
    assert rows["00-B"]["receptions"] == 6  # the version held, not the later correction
    # Published late: the rule says 27 October, but the read just before the gap lacked it.
    assert rows["00-L"][KNOWN_FROM] == GAP_START
    assert rows["00-L"][BASIS] == "retrospective-rule"
    # Thursday's game, fetched after the outage, counts from its rule.
    assert rows["00-C"][KNOWN_FROM] == utc(2026, 11, 13, 12)
    assert reading.lineage["inGap"] is True
    assert reading.lineage["boundedByGapStart"] == 1
    assert reading.lineage["unitsByBasis"] == {"observed": 1, "retrospective-rule": 3}


def test_before_a_rule_time_inside_the_gap_the_unit_waits():
    # Thursday of week 10 before kickoff: game C is not yet played, let alone published.
    reading = reader({STATS: STATS_FILE}).read(STATS, COLUMNS, utc(2026, 11, 12, 20))
    assert set(by_player(reading)) == {"00-A", "00-B", "00-L"}


def test_outside_a_gap_only_the_version_held_counts():
    # 9 November 12:00 UTC: read hours earlier, so nothing later is admitted by rule.
    reading = reader({STATS: STATS_FILE}).read(STATS, COLUMNS, utc(2026, 11, 9, 12))
    assert set(by_player(reading)) == {"00-A", "00-B"}
    assert reading.lineage["inGap"] is False
    assert reading.lineage["fetchedAfter"] is None


def test_after_the_gap_rows_keep_the_basis_of_their_first_holding():
    reading = reader({STATS: STATS_FILE}).read(STATS, COLUMNS, utc(2026, 11, 23))
    rows = by_player(reading)
    assert set(rows) == {"00-A", "00-B", "00-L", "00-C", "00-D"}
    assert rows["00-B"]["receptions"] == 7  # the correction, now held
    assert rows["00-B"][BASIS] == "observed"
    assert rows["00-D"][KNOWN_FROM] == utc(2026, 11, 16, 12)
    assert rows["00-D"][BASIS] == "retrospective-rule"


def test_every_row_is_labeled_and_known_before_the_decision():
    source = {STATS: STATS_FILE}
    for hours in range(0, 24 * 30, 7):
        at = utc(2026, 10, 25) + timedelta(hours=hours)
        for row in reader(source).read(STATS, COLUMNS, at).rows:
            assert row[BASIS] in BASES
            assert row[KNOWN_FROM] < at


def mutate_after(files, key, at, admitted):
    """Change everything published at or after `at`: every unit of a version read then, except
    units the reading admitted by rule (published before `at`), plus a new unit and a version."""
    files = deepcopy(files)
    versions, reads = files[key]
    changed = []
    for observed, rows in versions:
        if observed < at:
            changed.append((observed, rows))
            continue
        new_rows = [
            row if row["game_id"] in admitted else {**row, "receptions": row["receptions"] + 40}
            for row in rows
        ]
        new_rows.append(stat("2026_11_SEA_ARI", "00-NEW", 11))
        changed.append((observed, new_rows))
    last = changed[-1][1]
    changed.append((utc(2026, 11, 24, 3), [*last, stat("2026_11_SEA_ARI", "00-LATE", 2)]))
    files[key] = (changed, [*reads, utc(2026, 11, 23, 3)])
    return files


@pytest.mark.parametrize(
    "at",
    [
        utc(2026, 10, 27, 13),  # before Arbit's first read
        utc(2026, 11, 9, 12),  # observed stretch
        utc(2026, 11, 12, 20),  # inside the outage, before Thursday's game
        utc(2026, 11, 15, 18),  # inside the outage, Sunday
        utc(2026, 11, 23),  # after the outage
    ],
)
def test_changing_every_row_published_after_the_decision_never_changes_the_reading(at):
    files = {STATS: STATS_FILE}
    reading = reader(files).read(STATS, COLUMNS, at)
    admitted = {
        row["game_id"] for row in reading.rows if row[BASIS] != "observed"
    }  # units published before `at` by rule, possibly first held after it
    mutated = reader(mutate_after(files, STATS, at, admitted)).read(STATS, COLUMNS, at)

    assert mutated.rows == reading.rows
    assert mutated.lineage["unitsByBasis"] == reading.lineage["unitsByBasis"]


def test_the_mutation_test_detects_a_change_to_a_unit_published_before_the_decision():
    at = utc(2026, 11, 15, 18)
    files = {STATS: STATS_FILE}
    reading = reader(files).read(STATS, COLUMNS, at)
    # Mutate the Thursday game too: it was published before `at`, so the reading must change.
    mutated = reader(mutate_after(files, STATS, at, admitted=set())).read(STATS, COLUMNS, at)
    assert mutated.rows != reading.rows


SCHEDULES = "schedules/games"


def schedule_row(game_id, home_score=None, spread=None, temp=None):
    return {
        "game_id": game_id,
        "roof": "outdoors",
        "home_score": home_score,
        "spread_line": spread,
        "temp": temp,
    }


def test_a_season_never_observed_uses_rules_and_scores_wait_for_the_game():
    files = {
        SCHEDULES: (
            [(utc(2026, 10, 31, 9), [schedule_row("2024_05_NE_MIA", 27, -3.5, 81)])],
            [],
        )
    }
    pit = reader(files)
    before = utc(2024, 10, 6, 17)  # kickoff
    context = pit.read(SCHEDULES, ("game_id", "roof"), before)
    assert [r[KNOWN_FROM] for r in context.rows] == [utc(2024, 6, 1)]
    assert pit.read(SCHEDULES, ("game_id", "home_score"), before).rows == ()
    # Observed weather is history: it applies the day after the game (R-063 as amended).
    after = pit.read(SCHEDULES, ("game_id", "temp"), utc(2024, 10, 7, 13)).rows
    assert after[0]["temp"] == 81 and after[0][KNOWN_FROM] == utc(2024, 10, 7, 12)


def test_betting_lines_are_refused_without_the_owner_gate_and_apply_only_as_imported():
    files = {
        SCHEDULES: (
            [
                (utc(2026, 10, 31, 9), [schedule_row("2024_05_NE_MIA", 27, -3.5)]),
                (utc(2026, 11, 20, 3), [schedule_row("2026_11_SEA_ARI", None, 2.5)]),
            ],
            [utc(2026, 11, 19, 3)],
        )
    }
    with pytest.raises(PolicyRefused, match="EXCLUDED_FIELD: schedules.spread_line"):
        reader(files).read(SCHEDULES, ("game_id", "spread_line"), utc(2026, 11, 22))
    gated = reader(files, gates={"OWN-067"})
    # A line never observed before the game is not known (Q-014 decides any retrospective rule).
    assert gated.read(SCHEDULES, ("game_id", "spread_line"), utc(2024, 10, 6, 17)).rows == ()
    held = gated.read(SCHEDULES, ("game_id", "spread_line"), utc(2026, 11, 22, 21)).rows
    assert [(r["spread_line"], r[BASIS]) for r in held] == [(2.5, "observed")]


def test_unregistered_tables_and_uncatalogued_fields_are_refused():
    pit = reader({})
    with pytest.raises(LookupError, match="NO_TIMING_RULE: espn_data/qbr_week_level"):
        pit.read("espn_data/qbr_week_level", ("qbr_total",), utc(2026, 11, 22))
    with pytest.raises(LookupError, match="UNCATALOGUED_FIELD: stats_player.made_up"):
        pit.read(STATS, ("made_up",), utc(2026, 11, 22))
    with pytest.raises(ValueError, match="DECISION_TIME_NEEDS_TIMEZONE"):
        pit.read(STATS, COLUMNS, datetime(2026, 11, 22))


def test_injury_reports_count_from_their_own_timestamp_or_from_game_day():
    dated = {
        "season": 2024,
        "week": 5,
        "team": "NE",
        "gsis_id": "00-X",
        "date_modified": utc(2024, 10, 4, 19, 5),
    }
    placed = injury_rows(dated, CALENDAR, 2024)
    assert (placed.known, placed.basis) == (utc(2024, 10, 5, 7), "source-timestamp")
    # 2025 on: no date_modified; the final report counts from 07:00 UTC on game day.
    undated = {**dated, "season": 2026, "week": 9, "team": "SEA", "date_modified": None}
    placed = injury_rows(undated, CALENDAR, 2026)
    assert (placed.known, placed.basis) == (utc(2026, 11, 8, 7), "retrospective-rule")


def test_depth_charts_count_from_the_next_publication_after_their_snapshot():
    placed = depth_rows({"team": "SEA", "dt": "2026-11-21T15:12:52Z"}, CALENDAR, 2026)
    assert placed.unit == ("SEA", "2026-11-21T15:12:52Z")
    assert (placed.known, placed.basis) == (utc(2026, 11, 22, 7), "source-timestamp")
    weekly = depth_rows({"season": 2024, "week": 6, "club_code": "NE"}, CALENDAR, 2024)
    assert weekly.known == utc(2024, 10, 12, 12)  # the day before the week's first game


def test_current_franchise_codes_find_the_season_s_schedule_code():
    calendar = Calendar(
        [
            {
                "game_id": "2016_01_OAK_NO",
                "season": 2016,
                "week": 1,
                "gameday": "2016-09-11",
                "gametime": "13:00",
                "away_team": "OAK",
                "home_team": "NO",
            }
        ]
    )
    assert calendar.team_game(2016, 1, "LV").game_id == "2016_01_OAK_NO"
    assert calendar.team_game(2016, 1, "NO").game_id == "2016_01_OAK_NO"
    assert calendar.team_game(2016, 1, "KC") is None


def test_next_publication_is_strictly_after_the_stamp():
    assert next_publication(utc(2026, 11, 21, 6, 59)) == utc(2026, 11, 21, 7)
    assert next_publication(utc(2026, 11, 21, 7)) == utc(2026, 11, 22, 7)


def test_current_snapshot_fields_apply_only_from_an_observed_import():
    players = "players/players"
    files = {
        players: (
            [(utc(2026, 10, 31, 9), [{"gsis_id": "00-A", "status": "RES", "birth_date": "1999"}])],
            [],
        )
    }
    pit = reader(files)
    # Fixed facts are always known; the current status only from the import that held it.
    assert len(pit.read(players, ("gsis_id", "birth_date"), utc(2024, 9, 1)).rows) == 1
    assert pit.read(players, ("gsis_id", "status"), utc(2024, 9, 1)).rows == ()
    held = pit.read(players, ("gsis_id", "status"), utc(2026, 11, 1)).rows
    assert [(r["status"], r[BASIS]) for r in held] == [("RES", "observed")]


def test_every_registered_table_names_its_catalog_family():
    for key in (
        "pbp/play_by_play_2026",
        "stats_team/stats_team_week_2026",
        "stats_player/stats_player_regpost_2026",
        "snap_counts/snap_counts_2026",
        "nextgen_stats/ngs_receiving",
        "nextgen_stats/ngs_2019_rushing",
        "pfr_advstats/advstats_week_def_2026",
        "pfr_advstats/advstats_season_pass",
        "ftn_charting/ftn_charting_2026",
        "injuries/injuries_2026",
        "weekly_rosters/roster_weekly_2026",
        "rosters/roster_2026",
        "depth_charts/depth_charts_2024",
        "trades/trades",
        "combine/combine",
        "draft_picks/draft_picks",
        "contracts/historical_contracts",
        "teams/teams_colors_logos",
        "officials/officials",
        "pbp_participation/pbp_participation_2025",
    ):
        assert spec_for("nflverse/nflverse-data/" + key).family == key.split("/")[0]
    assert CALENDAR.game("2026_10_SEA_SF").gameday == date(2026, 11, 15)
