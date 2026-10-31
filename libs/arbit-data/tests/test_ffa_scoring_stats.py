"""Independent actual raw-stat recomputation and safe source scope selection."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_data.espn.scoring_rules import normalize_scoring
from arbit_data.espn.scoring_stats import ScoringDataError, reconcile_player

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"


def fixture():
    return json.loads(FIXTURE.read_bytes())


def one_case(name="quarterback"):
    d = fixture()
    case = next(c for c in d["cases"] if c["case"] == name)
    return normalize_scoring(d["scoringSettings"], 2026), case


@pytest.mark.parametrize(
    "name,expected", [("quarterback", "35.66"), ("kicker", "8.00"), ("defense", "19.00")]
)
def test_observed_player_cases_match_hand_calculation_and_espn(name, expected):
    rules, case = one_case(name)
    result = reconcile_player(case["player"], 1, rules, Decimal(str(case["officialPoolTotal"])))
    assert result.status == "verified"
    assert result.computed_total == Decimal(expected) and result.official_total == Decimal(expected)
    assert result.contribution_differences == ()
    assert result.zero_suppressed_ids


def test_defense_override_applies_on_bench_and_raw_range_fields_drive_math():
    rules, case = one_case("defense")
    case["player"]["lineupSlotId"] = 20
    assert reconcile_player(case["player"], 1, rules, Decimal("19")).computed_total == Decimal("19")


def test_sixty_plus_field_goal_is_not_also_scored_in_fifty_plus_bucket():
    rules, case = one_case("kicker")
    block = case["player"]["stats"][0]
    block.update(
        stats={"74": 1, "198": 0, "201": 1, "210": 1}, appliedStats={"201": 6}, appliedTotal=6
    )
    result = reconcile_player(case["player"], 1, rules, Decimal("6"))
    assert result.status == "verified" and result.computed_total == Decimal("6")


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda b: b.update(statSourceId=1), "MISSING_ACTUAL_BLOCK"),
        (lambda b: b.update(statSplitTypeId=0), "MISSING_ACTUAL_BLOCK"),
        (lambda b: b.update(seasonId=2027), "MISSING_ACTUAL_BLOCK"),
        (lambda b: b.update(scoringPeriodId=2), "MISSING_ACTUAL_BLOCK"),
        (lambda b: b.pop("stats"), "MISSING_STAT_MAP"),
        (lambda b: b.pop("appliedStats"), "MISSING_APPLIED_STATS"),
        (lambda b: b.pop("appliedTotal"), "MISSING_OFFICIAL_TOTAL"),
        (lambda b: b["stats"].update({"210": 2}), "MULTI_GAME_UNSUPPORTED"),
        (lambda b: b["stats"].pop("210"), "MISSING_GAME_MARKER"),
        (lambda b: b["stats"].pop("3"), "MISSING_SCORED_STAT"),
    ],
)
def test_missing_or_wrong_scope_is_not_filled_with_zero(change, code):
    rules, case = one_case()
    change(case["player"]["stats"][0])
    with pytest.raises(ScoringDataError) as caught:
        reconcile_player(case["player"], 1, rules, Decimal("35.66"))
    assert caught.value.code == code


def test_duplicate_actual_blocks_are_ambiguous():
    rules, case = one_case()
    case["player"]["stats"].append(deepcopy(case["player"]["stats"][0]))
    with pytest.raises(ScoringDataError) as caught:
        reconcile_player(case["player"], 1, rules, Decimal("35.66"))
    assert caught.value.code == "AMBIGUOUS_ACTUAL_BLOCK"


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b["stats"].update({"91": 0}),
        lambda b: b["stats"].pop("120"),
    ],
)
def test_defense_range_source_and_indicator_must_be_consistent(change):
    rules, case = one_case("defense")
    change(case["player"]["stats"][0])
    with pytest.raises(ScoringDataError):
        reconcile_player(case["player"], 1, rules, Decimal("19"))


def test_explicit_empty_no_game_maps_are_known_provider_zero_not_verified_stats():
    rules, case = one_case()
    block = case["player"]["stats"][0]
    block.update(stats={}, appliedStats={}, appliedTotal=0)
    result = reconcile_player(case["player"], 1, rules, Decimal(0))
    assert result.status == "provider_zero" and result.computed_total is None


def test_binary_serialization_noise_does_not_hide_real_cent_mismatch():
    rules, case = one_case("kicker")
    block = case["player"]["stats"][0]
    block["appliedTotal"] = "8.000000000000002"
    assert reconcile_player(case["player"], 1, rules, Decimal("8")).status == "verified"
    block["appliedTotal"] = "8.01"
    assert reconcile_player(case["player"], 1, rules, Decimal("8.01")).status == "mismatch"


def test_wrong_applied_contributions_fail_even_if_total_is_unchanged():
    rules, case = one_case("kicker")
    block = case["player"]["stats"][0]
    block["appliedStats"]["77"] = 5
    block["appliedStats"]["80"] = 2
    result = reconcile_player(case["player"], 1, rules, Decimal("8"))
    assert result.status == "mismatch"
    assert {difference.rule_id for difference in result.contribution_differences} == {"77", "80"}


def test_negative_net_yards_still_belong_to_under_100_defense_band():
    rules, case = one_case("defense")
    block = case["player"]["stats"][0]
    block.update(
        stats={"120": 0, "127": -7, "89": 1, "128": 1, "210": 1},
        appliedStats={"89": 5, "128": 5},
        appliedTotal=10,
    )
    result = reconcile_player(case["player"], 1, rules, Decimal("10"))
    assert result.status == "verified" and result.computed_total == Decimal("10")


def test_rare_return_safety_and_fumble_categories_have_hand_calculated_weights():
    rules, case = one_case("defense")
    block = case["player"]["stats"][0]
    block.update(
        stats={
            "63": 1,
            "93": 1,
            "98": 1,
            "101": 1,
            "206": 1,
            "209": 1,
            "120": 0,
            "127": 99,
            "89": 1,
            "128": 1,
            "210": 1,
        },
        appliedStats={"63": 6, "93": 6, "98": 2, "101": 6, "206": 2, "209": 1, "89": 5, "128": 5},
        appliedTotal=33,
    )
    result = reconcile_player(case["player"], 1, rules, Decimal("33"))
    assert result.status == "verified" and result.computed_total == Decimal("33")
