"""The prospective adapter (arbit_model.dvp.shadow) and harness (scripts/model/dvp_prospective.py).

Owner audit AUD-01 and AUD-05:
- targets come from the schedule, so an unplayed week can be forecast and the target set never
  depends on which labels later turn out valid;
- the adapter runs the frozen estimator unchanged (it equals `walkforward.walk` on its targets);
- stored forecasts carry no label;
- labels are attached later without dropping a target;
- the archive is write-once, its ledger hash-chained;
- missed and reconstructed weeks are kept apart;
- the frozen method is verified before anything runs.

On the main machine, docs/research/dvp/prospective/rehearsal-2025.json records the same
equivalence on the real 2025 holdout.
"""

import importlib.util
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from arbit_model.dvp import asof, shadow
from arbit_model.dvp import walkforward as wf
from arbit_model.dvp.provenance import LineageError
from test_dvp_walkforward import POSITIONS, season_data

ROOT = Path(__file__).resolve().parents[3]
HARNESS = ROOT / "scripts/model/dvp_prospective.py"
KEYS = list(shadow.KEYS)


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("dvp_prospective", HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def with_teams(observations: pl.DataFrame, schedule: pl.DataFrame) -> pl.DataFrame:
    teams = (
        observations.filter(pl.col("position") == "WR")
        .group_by("game_id")
        .agg(
            pl.col("offense").sort().first().alias("home"),
            pl.col("offense").sort().last().alias("away"),
        )
    )
    return schedule.join(teams, on="game_id")


def setup(season=2018, **kwargs):
    observations, schedule = season_data(**kwargs)
    schedule = with_teams(observations, schedule)
    rows = wf.prepare(observations)
    params = wf.fit_fold(rows, season, POSITIONS)
    return observations, schedule, rows, params


def test_scheduled_targets_need_no_score_status_or_label():
    _, schedule, _, _ = setup()
    bare = schedule.select("game_id", "season", "week", "kickoff", "home", "away")
    targets = shadow.scheduled_targets(bare, 2018, [3], POSITIONS)
    games = bare.filter((pl.col("season") == 2018) & (pl.col("week") == 3)).height
    assert targets.height == games * 2 * len(POSITIONS)
    assert not {"points", "status", "home_score"} & set(targets.columns)
    dst = targets.filter(pl.col("position") == "DST")
    wr = targets.filter(pl.col("position") == "WR")
    # D/ST: the scoring side is the D/ST facing the offense; WR: the offense scores.
    assert (dst.get_column("side") == dst.get_column("defense")).all()
    assert (dst.get_column("opp") == dst.get_column("offense")).all()
    assert (wr.get_column("side") == wr.get_column("offense")).all()
    with pytest.raises(LineageError, match="SCHEDULE_TEAMS"):
        shadow.scheduled_targets(
            bare.with_columns(pl.col("home").alias("away")), 2018, [3], POSITIONS
        )


def test_the_adapter_is_the_frozen_walk_on_the_frozen_walks_targets():
    _, schedule, rows, params = setup()
    frozen = wf.walk(rows, schedule, params, POSITIONS, wf.Settings()).frame
    targets = shadow.scheduled_targets(schedule, 2018, None, POSITIONS)
    adapter = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings()).frame
    assert adapter.columns == frozen.columns
    assert adapter.equals(frozen)  # same rows, order and random stream: bit for bit


def test_an_unplayed_week_is_forecast_from_the_schedule_alone():
    """AUD-01: the frozen walk cannot forecast a week without observation rows; the adapter can."""
    observations, schedule, _, _ = setup()
    unplayed = observations.filter(~((pl.col("season") == 2018) & (pl.col("week") == 14)))
    rows = wf.prepare(unplayed)
    params = wf.fit_fold(rows, 2018, POSITIONS)
    frozen = wf.walk(rows, schedule, params, POSITIONS, wf.Settings()).frame
    assert frozen.filter(pl.col("week") == 14).is_empty()
    targets = shadow.scheduled_targets(schedule, 2018, range(1, 15), POSITIONS)
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings())
    week14 = shadow.forecast_only(out, targets).filter(pl.col("week") == 14)
    assert week14.height == schedule.filter(
        (pl.col("season") == 2018) & (pl.col("week") == 14)
    ).height * 2 * len(POSITIONS)
    assert week14.select("b00", "b06").null_count().sum_horizontal().item() == 0
    # Same forecasts as with the week's results present: they were never inputs.
    full = setup()[2]
    reference = shadow.walk_targets(full, targets, schedule, params, POSITIONS, wf.Settings())
    expected = shadow.forecast_only(reference, targets).filter(pl.col("week") == 14)
    assert week14.select(KEYS, "b00", "b06").equals(expected.select(KEYS, "b00", "b06"))


def test_t16_t17_t20_outcomes_after_a_cutoff_change_neither_targets_nor_forecasts():
    """AUD-05: deleting later results, flipping their validity, changing their points or
    correcting them retroactively leaves earlier targets and forecasts unchanged."""
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, range(1, 9), POSITIONS)
    base = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings())
    reference = shadow.forecast_only(base, targets)
    later = (pl.col("season") == 2018) & (pl.col("week") >= 9)
    variants = {
        "deleted": observations.filter(~later),
        "invalid": observations.with_columns(
            pl.when(later).then(pl.lit("invalid_refused_line")).otherwise("status").alias("status")
        ),
        "changed": observations.with_columns(
            pl.when(later).then(pl.col("points") * 3 + 40).otherwise("points").alias("points")
        ),
        "corrected": observations.with_columns(
            pl.when(later).then(pl.col("points") + 0.5).otherwise("points").alias("points"),
        ),
    }
    for name, changed in variants.items():
        rows2 = wf.prepare(changed)
        params2 = wf.fit_fold(rows2, 2018, POSITIONS)
        targets2 = shadow.scheduled_targets(schedule, 2018, range(1, 9), POSITIONS)
        assert targets2.equals(targets), name
        out = shadow.walk_targets(rows2, targets2, schedule, params2, POSITIONS, wf.Settings())
        got = shadow.forecast_only(out, targets2)
        assert got.drop("b09_shuffle", "b09_noise", "b09_lastopp").equals(
            reference.drop("b09_shuffle", "b09_noise", "b09_lastopp")
        ), name
        assert got.equals(reference), name  # the random stream too: same batches, same draws


def test_stored_forecasts_hold_no_label_and_labels_never_drop_a_target():
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, range(1, 4), POSITIONS)
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings())
    stored = shadow.forecast_only(out, targets)
    assert not asof.LABEL_COLUMNS & set(stored.columns)
    with pytest.raises(LineageError, match="LABEL_IN_FORECAST"):
        shadow.forecast_only(
            asof.FrozenForecasts(
                out.frozen_at, out.frame.with_columns(pl.lit(1.0).alias("points"))
            ),
            targets,
        )
    labels = observations.filter(pl.col("season") == 2018)
    week3 = labels.filter(pl.col("week") == 3)
    drop = week3.head(2).select(KEYS)
    flip = week3.slice(2, 3).select(KEYS)
    labels = labels.join(drop, on=KEYS, how="anti").with_columns(
        pl.when(pl.struct(KEYS).is_in(flip.to_struct().implode()))
        .then(pl.lit("invalid_refused_line"))
        .otherwise("status")
        .alias("status")
    )
    labelled = shadow.attach_labels(stored, labels)
    assert labelled.height == stored.height
    counts = dict(labelled.group_by("label_status").len().iter_rows())
    assert counts["missing"] == 2 and counts["invalid_refused_line"] == 3
    assert labelled.filter(pl.col("label_status") != "valid").get_column("points").null_count() == 5
    coverage = shadow.coverage(labelled)
    assert sum(v["targets"] for v in coverage.values()) == stored.height
    late = stored.with_columns(pl.col("kickoff") - timedelta(days=30))
    with pytest.raises(LineageError, match="FEATURE_AFTER_KICKOFF"):
        shadow.attach_labels(late, labels)


def test_the_ledger_detects_edits_deletions_and_reordering():
    lines, previous = [], None
    for week in (12, 13, 14):
        entry = shadow.ledger_entry(previous, {"week": week, "classification": "PROSPECTIVE"})
        lines.append(entry)
        previous = entry["entrySha256"]
    assert shadow.verify_ledger(lines) == []
    edited = [dict(x) for x in lines]
    edited[0]["generatedAt"] = "backdated"
    assert shadow.verify_ledger(edited)
    assert shadow.verify_ledger([lines[0], lines[2]])
    assert shadow.verify_ledger([lines[1], lines[0], lines[2]])


def test_league_choices_follow_the_declared_rule():
    forecasts = pl.DataFrame(
        {
            "position": ["DST"] * 4,
            "defense": ["AAA", "BBB", "CCC", "DDD"],
            "b00": [5.0, 6.0, 7.0, 7.0],
            "b06": [9.0, 6.0, 4.0, 8.0],
        }
    )
    rosters = {"t1": ["AAA", "BBB"], "t2": ["CCC"], "t3": ["EEE", "AAA"]}  # EEE has a bye
    choices = shadow.league_choices(forecasts, rosters, ["DDD"], ("b00", "b06"))
    rows = {(r["team"], r["decision"]): r for r in choices.iter_rows(named=True)}
    assert ("t2", "start") not in rows  # one D/ST: no start choice
    assert rows[("t1", "start")]["pick_b00"] == "BBB" and rows[("t1", "start")]["pick_b06"] == "AAA"
    assert rows[("t2", "stream")]["pick_b00"] == "CCC"  # a tie at 7.0 breaks by code
    assert rows[("t2", "stream")]["pick_b06"] == "DDD"
    assert ("t3", "start") not in rows and rows[("t3", "stream")]["options"] == 2


def test_the_archive_is_write_once_and_the_ledger_append_only(harness, tmp_path):
    folder = tmp_path / "2026" / "week-12"
    digests = harness.write_once(folder, {"forecasts.csv": b"a,b\n1,2\n"})
    assert (folder / "forecasts.csv").stat().st_mode & 0o222 == 0
    with pytest.raises(SystemExit, match="never overwritten"):
        harness.write_once(folder, {"forecasts.csv": b"other"})
    assert harness.sha256(folder / "forecasts.csv") == digests["forecasts.csv"]
    ledger = tmp_path / "ledger.jsonl"
    harness.append_ledger(ledger, {"week": 12, "classification": "PROSPECTIVE"})
    harness.append_ledger(ledger, {"week": 13, "classification": "MISSED"})
    assert shadow.verify_ledger(harness.read_ledger(ledger)) == []
    text = ledger.read_text().replace('"MISSED"', '"PROSPECTIVE"')
    ledger.write_text(text)
    with pytest.raises(SystemExit, match="ledger is broken"):
        harness.append_ledger(ledger, {"week": 14, "classification": "PROSPECTIVE"})


def test_readiness_waits_for_every_earlier_result(harness):
    kickoff = datetime(2026, 11, 22, 18, tzinfo=UTC)
    schedule = pl.DataFrame(
        {
            "season": [2026] * 3,
            "week": [10, 11, 11],
            "game_id": ["g1", "g2", "g3"],
            "kickoff": [kickoff - timedelta(days=7), kickoff, kickoff],
            "available_at": [kickoff - timedelta(days=6), kickoff + timedelta(days=1)] * 1
            + [kickoff + timedelta(days=1)],
            "status": ["completed", "completed", "not_completed"],
        }
    )
    obs_rows = pl.DataFrame({"season": [2026, 2026], "game_id": ["g1", "g2"]})
    soon = kickoff + timedelta(days=2)
    ready, detail = harness.readiness(schedule, obs_rows, 2026, 12, soon)
    assert not ready and detail["awaitingResult"] == ["g3"]
    later = kickoff + timedelta(days=5)  # g3 never got a result: recorded, no longer blocking
    ready, detail = harness.readiness(schedule, obs_rows, 2026, 12, later)
    assert ready and detail["noResultAfterGrace"] == ["g3"]
    ready, detail = harness.readiness(schedule, obs_rows.head(1), 2026, 12, later)
    assert not ready and detail["completedWithoutFfaLines"] == ["g2"]
    ready, _ = harness.readiness(schedule, obs_rows, 2026, 12, kickoff + timedelta(hours=1))
    assert not ready  # g2's results aren't available until the next day


FROZEN_COMMIT = json.loads((ROOT / "config/dvp/frozen.json").read_text())["code"]
HAS_FROZEN = (
    subprocess.run(
        ["git", "cat-file", "-e", f"{FROZEN_COMMIT}:scripts/model/dvp.py"], cwd=ROOT
    ).returncode
    == 0
)


@pytest.mark.skipif(not HAS_FROZEN, reason="shallow checkout without the frozen commit")
def test_the_frozen_method_is_verified_and_loaded_by_hash(harness, monkeypatch):
    fz = harness.load_frozen()
    assert fz.verification["allMatch"] and fz.verification["filesVerified"] >= 20
    # The frozen script, not this checkout's: verify and sitstart came after the freeze.
    assert not hasattr(fz.cli, "verify") and not hasattr(fz.cli, "sitstart")
    assert hasattr(fz.cli, "_contribution_cells")
    real = harness.sha256

    def tampered(path):
        return "0" * 64 if str(path).endswith("walkforward.py") else real(path)

    monkeypatch.setattr(harness, "sha256", tampered)
    with pytest.raises(SystemExit, match="BLOCKED: frozen method does not match"):
        harness.load_frozen()


def test_the_predeclared_config_names_the_frozen_window():
    config = json.loads((ROOT / "config/dvp/prospective.json").read_text())
    frozen = json.loads((ROOT / "config/dvp/frozen.json").read_text())
    assert config["weeks"] == frozen["prospective"]["weeks"]
    assert config["season"] == frozen["prospective"]["season"]
    assert config["write_to_production"] is False
    assert set(config["classification"]) == {"PROSPECTIVE", "MISSED", "RETROSPECTIVE", "REHEARSAL"}


def test_only_the_complete_prospective_window_can_confirm(harness):
    """A rehearsal, a reconstruction or an interim window is descriptive: its rule outcome is
    shown, but its label never says CONFIRMED."""
    observations, schedule, rows, params = setup()
    targets = shadow.scheduled_targets(schedule, 2018, range(1, 15), POSITIONS)
    out = shadow.walk_targets(rows, targets, schedule, params, POSITIONS, wf.Settings())
    stored = shadow.forecast_only(out, targets).filter(pl.col("week") >= 8)
    fz = harness.Frozen(
        cli=None,
        group={
            "protocol": {
                "bootstrapReplicates": 50,
                "seed": 1729,
                "practicalMinimumRelativeRmse": 0.01,
            },
            "periods": {"DST": {"candidate": "b06"}},
        },
        phase_c={
            "parameters": {
                "close": 1.0,
                "waiverPoolRanks": [9, 24],
                "top": 8,
                "bootstrapReplicates": 50,
                "seed": 1729,
            },
            "practicalMinimumAccuracyPp": 1.8,
        },
        base={"position_groups": list(POSITIONS)},
        backtest={},
        candidates={
            "positions": {
                "WR": {"candidate": "b00", "bestDvp": "b06"},
                "DST": {"candidate": "b06", "bestDvp": "b06"},
            }
        },
        sitstart={},
        verification={},
    )
    labels = observations.filter(pl.col("season") == 2018).with_columns(
        pl.col("offense").alias("unit")
    )
    final = harness.evaluate_frame(fz, stored, labels)
    assert final["phaseB"]["DST"]["label"] in ("CONFIRMED", "NOT_CONFIRMED")
    assert final["phaseB"]["WR"]["label"].startswith("NO_CANDIDATE")
    assert final["phaseC"]["label"] in ("CONFIRMED", "NOT_CONFIRMED")
    interim = harness.evaluate_frame(fz, stored, labels, descriptive="INTERIM: not yet")
    for part in (interim["phaseB"]["DST"], interim["phaseB"]["WR"], interim["phaseC"]):
        assert part["label"] == "INTERIM: not yet"
    assert interim["phaseB"]["DST"]["ruleOutcome"] == final["phaseB"]["DST"]["label"]
