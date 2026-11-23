"""The point-in-time reader against PostgreSQL and the object store (M3 slice 3, ADR-007 A1/A3).

Versions come from `dataset_manifest` and reads from `dataset_import`; only successful checks are
reads. One 2026 statistics file is read daily, then not for twelve days (as in R-068).
"""

from datetime import UTC, datetime

import pyarrow as pa  # type: ignore[import-untyped]
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import dataset_import, dataset_manifest, nflverse_catalog
from arbit_model.point_in_time import BASIS, KNOWN_FROM, PointInTime
from arbit_model.storage import write_parquet
from arbit_model.vintages import StoredVintages
from sqlalchemy import insert

PREFIX = "nflverse/nflverse-data/"
STATS = "stats_player/stats_player_week_2026"


def utc(*parts):
    return datetime(*parts, tzinfo=UTC)


GAMES = [
    ("2026_08_NE_SEA", 8, "2026-10-25", "16:05", "NE", "SEA"),
    ("2026_09_SEA_LA", 9, "2026-11-08", "16:25", "SEA", "LA"),
    ("2026_10_SEA_SF", 10, "2026-11-15", "13:00", "SEA", "SF"),
]


def stat(game, player, receptions=None):
    row = {
        "game_id": game,
        "season": 2026,
        "week": int(game[5:7]),
        "team": "SEA",
        "player_id": player,
    }
    if receptions is not None:
        row["receptions"] = receptions
    return row


def publish(c, store, key, at, rows, n):
    digest = write_parquet(store, pa.Table.from_pylist(rows)).sha256
    manifest = f"{n:064x}"
    c.execute(
        insert(dataset_manifest).values(
            hash=manifest,
            logical_key=PREFIX + key,
            family=key.split("/")[0],
            observed_at=at,
            raw_hash=digest,
            parquet_hash=digest,
            state_hash=digest,
            payload={},
        )
    )
    check(c, key, at, "published", manifest, n)
    return manifest


def check(c, key, at, status, manifest, n):
    catalog = f"{1000 + n:064x}"  # each run registers its own catalog
    c.execute(insert(nflverse_catalog).values(hash=catalog, observed_at=at, payload={}))
    c.execute(
        insert(dataset_import).values(
            catalog_hash=catalog,
            logical_key=PREFIX + key,
            asset_id=str(n),
            status=status,
            manifest_hash=manifest,
            checked_at=at,
        )
    )


def seed(uow, tmp_path):
    store = ObjectStore(tmp_path / "objects")
    schedule = [
        {
            "game_id": g,
            "old_game_id": None,
            "season": 2026,
            "week": week,
            "game_type": "REG",
            "gameday": day,
            "gametime": clock,
            "away_team": away,
            "home_team": home,
        }
        for g, week, day, clock, away, home in GAMES
    ]
    with uow.engine.begin() as c:
        publish(c, store, "schedules/games", utc(2026, 10, 31, 9), schedule, 1)
        # The first version predates the receptions column: it reads as unknown, not zero.
        v0 = publish(c, store, STATS, utc(2026, 11, 8, 3), [stat("2026_08_NE_SEA", "00-A")], 2)
        rows = [stat("2026_08_NE_SEA", "00-A", 5), stat("2026_09_SEA_LA", "00-B", 6)]
        v1 = publish(c, store, STATS, utc(2026, 11, 9, 3), rows, 3)
        check(c, STATS, utc(2026, 11, 10, 4), "unchanged", v1, 4)
        check(c, STATS, utc(2026, 11, 16, 6), "failed", None, 5)  # not a read
        rows = [*rows, stat("2026_10_SEA_SF", "00-D", 9)]
        publish(c, store, STATS, utc(2026, 11, 22, 22, 45), rows, 6)
    return store, v0


def test_versions_and_successful_reads_come_from_the_database(uow, tmp_path):
    store, v0 = seed(uow, tmp_path)
    source = StoredVintages(uow, store)
    history = source.history(PREFIX + STATS)

    assert [v.observed_at for v in history.versions] == [
        utc(2026, 11, 8, 3),
        utc(2026, 11, 9, 3),
        utc(2026, 11, 22, 22, 45),
    ]
    assert utc(2026, 11, 16, 6) not in history.reads
    assert [(g.start, g.end) for g in history.gaps()] == [
        (None, utc(2026, 11, 8, 3)),
        (utc(2026, 11, 10, 4), utc(2026, 11, 22, 22, 45)),
    ]
    first = source.table(history.versions[0], ("player_id", "receptions")).to_dicts()
    assert first == [{"player_id": "00-A", "receptions": None}]
    assert history.versions[0].manifest == v0


def test_a_decision_inside_the_gap_admits_what_was_published_before_it(uow, tmp_path):
    store, _ = seed(uow, tmp_path)
    pit = PointInTime.from_store(uow, store)
    columns = ("game_id", "player_id", "receptions")

    before = pit.read(STATS, columns, utc(2026, 11, 15, 17))
    assert {r["player_id"]: r[BASIS] for r in before.rows} == {
        "00-A": "retrospective-rule",
        "00-B": "observed",
    }
    after = pit.read(STATS, columns, utc(2026, 11, 16, 13))
    rows = {r["player_id"]: r for r in after.rows}
    assert rows["00-D"][KNOWN_FROM] == utc(2026, 11, 16, 12)
    assert rows["00-D"][BASIS] == "retrospective-rule"
    assert after.lineage["inGap"] is True
    assert after.lineage["fetchedAfter"] is not None
