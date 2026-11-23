"""The actual-score and projection firewall of the DvP research: T30-T33, T37 and T40.

Admission follows lineage: a source must be allowlisted, name its ancestry and carry the league's
scoring hash, and every column it holds must be known. Planted projections, under their own names
or renamed, either fail closed or never reach an observation.
"""

import json
from pathlib import Path

import polars as pl
import pytest
from arbit_model.dvp import provenance, results
from arbit_model.dvp.provenance import LineageError, SourceSpec, SourceType, admit, scan_code
from test_dvp_observations import ATHLETE, DEFENSE, SCHEDULE, SCORING, build, frames

ROOT = Path(__file__).resolve().parents[3]
RECEIPTS = ROOT / "docs/research/dvp"


def athlete_frame(rows=ATHLETE) -> pl.DataFrame:
    return frames(rows)[0]


def admit_athlete(frame: pl.DataFrame, **overrides):
    arguments = {
        "ancestry": "fixture",
        "scoring_hash": SCORING["athlete"],
        "expected_scoring": SCORING,
    } | overrides
    return admit(frame, "ffa_targets.athlete", **arguments)


def test_t30_ffa_actuals_enter_only_under_the_league_scoring_hash_and_unchanged():
    admitted = admit_athlete(athlete_frame())
    assert admitted.source_type is SourceType.FFA_ACTUAL_FINAL
    assert admitted.frame.get_column("points").to_list() == athlete_frame()["points"].to_list()
    # nflverse's generic fantasy points are dropped on admission, never a substitute for FFA's.
    schedule = frames()[2].with_columns(pl.lit(12.5).alias("fantasy_points_ppr"))
    entered = admit(schedule, "nflverse.schedules", ancestry="fixture")
    assert entered.dropped == {"fantasy_points_ppr": "generic-fantasy-points"}
    assert "fantasy_points_ppr" not in entered.frame.columns


def test_t31_scoring_path_and_dvp_code_hold_no_provider_projection():
    receipt = json.loads((RECEIPTS / "PROJECTION_EXCLUSION_AUDIT.json").read_text())
    assert receipt["forbidden_vendor_projection_dependencies"] == 0
    assert receipt["status"] == "PASSED"
    for path in receipt["codeScan"]["files"]:
        assert scan_code(ROOT / path) == [], path
    assert {f["action"] for f in receipt["forbiddenInventory"]} == {"REJECT"}


def test_t31_the_scan_finds_a_planted_projection(tmp_path):
    planted = tmp_path / "planted.py"
    planted.write_text(
        "from arbit_data.espn.reader import read\nframe = frame.join(espn, on='id')\n"
        "value = row['projected_points']\n"
    )
    found = scan_code(planted)
    assert any("projected_" in f for f in found)
    assert any("imports arbit_data.espn.reader" in f for f in found)


@pytest.mark.parametrize(
    "column", ["projected_points", "opponent_expected", "espn_projection", "proj"]
)
def test_t32_a_planted_projection_column_fails_closed_under_any_name(column):
    planted = athlete_frame().with_columns(pl.lit(99.0).alias(column))
    with pytest.raises(LineageError) as error:
        admit_athlete(planted)
    assert error.value.code == "UNKNOWN_COLUMN"


def test_t32_planted_projection_rows_fail_closed_and_observations_do_not_change():
    baseline = build().rows
    rows = [*ATHLETE, {**ATHLETE[0], "basis": "espn_projection", "points": 99.0}]
    with pytest.raises(LineageError) as error:
        admit_athlete(athlete_frame(rows))
    assert error.value.code == "UNKNOWN_VALUE"
    with pytest.raises(LineageError) as error:
        admit(athlete_frame(), "espn.projections", ancestry="fixture")
    assert error.value.code == "UNKNOWN_SOURCE"
    assert build().rows.equals(baseline)


def test_t32_a_projection_source_type_is_refused_even_if_registered(monkeypatch):
    spec = SourceSpec(
        "vendor.projections",
        SourceType.EXTERNAL_FANTASY_PROJECTION_FORBIDDEN,
        "vendor",
        "a provider's projected points",
        used=("game_id",),
        known=frozenset({"game_id"}),
    )
    monkeypatch.setitem(provenance.SOURCES, spec.source_id, spec)  # type: ignore[arg-type]
    with pytest.raises(LineageError) as error:
        admit(pl.DataFrame({"game_id": ["g"]}), "vendor.projections", ancestry="fixture")
    assert error.value.code == "FORBIDDEN_SOURCE_TYPE"


def test_t33_unknown_category_or_missing_ancestry_fails_closed():
    with pytest.raises(LineageError) as error:
        admit_athlete(athlete_frame(), ancestry=None)
    assert error.value.code == "MISSING_ANCESTRY"
    schedule = frames()[2].with_columns(pl.lit(1).alias("opponent_outlook"))
    with pytest.raises(LineageError) as error:
        admit(schedule, "nflverse.schedules", ancestry="fixture")
    assert error.value.code == "UNKNOWN_COLUMN"
    with pytest.raises(LineageError) as error:
        admit_athlete(athlete_frame(), schema=[*athlete_frame().columns, "opponent_expected"])
    assert error.value.code == "UNKNOWN_COLUMN"  # a column outside the read still counts


def test_t37_a_changed_scoring_hash_stops_the_pipeline():
    for given, expected in (("b" * 64, SCORING), (SCORING["athlete"], {}), (None, SCORING)):
        with pytest.raises(LineageError) as error:
            admit_athlete(athlete_frame(), scoring_hash=given, expected_scoring=expected)
        assert error.value.code == "SCORING_HASH_MISMATCH"
    defense = frames(defense=DEFENSE)[1]
    with pytest.raises(LineageError):
        admit(
            defense,
            "ffa_targets.defense",
            ancestry="fixture",
            scoring_hash=SCORING["athlete"],  # the athlete rules, not the D/ST rules
            expected_scoring=SCORING,
        )


def test_t40_a_projection_dependency_invalidates_a_result():
    clean = results.record(
        "M3-3-X", "EXECUTED", forbidden_vendor_projection_dependencies=0, decision="INCONCLUSIVE"
    )
    assert (clean["status"], clean["decision"]) == ("EXECUTED", "INCONCLUSIVE")
    tainted = results.record(
        "M3-3-Y", "EXECUTED", forbidden_vendor_projection_dependencies=1, decision="PROMISING"
    )
    assert (tainted["status"], tainted["decision"]) == ("INVALID", None)
    assert results.problems([clean]) == []
    assert any("forbidden" in p for p in results.problems([tainted]))
    with pytest.raises(ValueError):
        results.record("M3-3-Z", "EXECUTED")  # the dependency count is required


def test_t40_the_committed_registry_has_no_projection_dependency():
    registry = json.loads((RECEIPTS / "experiment-registry.json").read_text())
    assert results.problems(registry["experiments"]) == []
    v0 = next(e for e in registry["experiments"] if e["experiment_id"] == "M3-3-v0")
    assert v0["status"] == "REPRODUCED"


def test_schedule_betting_lines_are_dropped_and_recorded():
    schedule = frames(schedule=SCHEDULE)[2].with_columns(pl.lit(-3.5).alias("spread_line"))
    entered = admit(schedule, "nflverse.schedules", ancestry="fixture")
    assert entered.dropped == {"spread_line": "betting-lines"}
    assert entered.record()["columnsDropped"] == {"spread_line": "betting-lines"}
