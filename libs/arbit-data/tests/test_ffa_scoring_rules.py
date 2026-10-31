"""Actual FFA rates, role overrides and hand-calculated rule boundaries."""

import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
from arbit_core.rules import StatLine
from arbit_core.scoring import UnsupportedRuleError, score
from arbit_data.espn.scoring_rules import normalize_scoring

FIXTURE = Path(__file__).resolve().parents[3] / "tests/fixtures/espn/ffa-scoring.observed.json"


def settings():
    return json.loads(FIXTURE.read_bytes())["scoringSettings"]


def test_all_actual_rules_are_mapped_and_overrides_are_role_based():
    normalized = normalize_scoring(settings(), 2026)
    assert normalized.supported and len(normalized.source_items) == 46
    assert len(normalized.athlete_rules.rules) == 26 and len(normalized.defense_rules.rules) == 46
    assert normalized.athlete_rules.content_hash != normalized.defense_rules.content_hash
    assert normalized.unsupported == ()


@pytest.mark.parametrize(
    "points,yards,expected",
    [
        (0, 99, "10"),
        (1, 100, "7"),
        (7, 200, "5"),
        (13, 299, "5"),
        (14, 300, "1"),
        (18, 349, "0"),
        (27, 350, "-1"),
        (28, 399, "-2"),
        (34, 400, "-4"),
        (35, 449, "-6"),
        (45, 450, "-8"),
        (46, 500, "-11"),
        (46, 550, "-12"),
    ],
)
def test_actual_defense_band_boundaries(points, yards, expected):
    normalized = normalize_scoring(settings(), 2026)
    values = {rule.stat: Decimal(0) for rule in normalized.defense_rules.rules}
    values["defense.points_allowed"] = Decimal(points)
    values["defense.yards_allowed"] = Decimal(yards)
    assert score(StatLine(scope="game", values=values), normalized.defense_rules).total == Decimal(
        expected
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["scoringItems"].append(
            {"statId": 9999, "points": 1, "pointsOverrides": {}, "isReverseItem": False}
        ),
        lambda s: s["scoringItems"][0].update(isReverseItem=True),
        lambda s: s["scoringItems"][0].update(pointsOverrides={"0": 1}),
        lambda s: s.update(homeTeamBonus=1),
        lambda s: s.update(scoringEnhancementType="UNKNOWN"),
        lambda s: s.update(newScoringOption=True),
    ],
)
def test_unsupported_definitions_remain_explicit_and_cannot_score(change):
    data = settings()
    change(data)
    normalized = normalize_scoring(data, 2026)
    assert not normalized.supported and normalized.unsupported
    with pytest.raises(UnsupportedRuleError):
        score(StatLine(scope="game", values={}), normalized.athlete_rules)


def test_changed_rates_change_hash_but_order_and_unused_counters_do_not():
    data = settings()
    first = normalize_scoring(data, 2026)
    data["scoringItems"].reverse()
    data["scoringItems"][0]["leagueTotal"] = 999
    assert normalize_scoring(data, 2026).config_hash == first.config_hash
    data["scoringItems"][0]["points"] = "7"
    assert normalize_scoring(data, 2026).config_hash != first.config_hash


def test_duplicate_source_rules_are_rejected():
    data = settings()
    data["scoringItems"].append(deepcopy(data["scoringItems"][0]))
    with pytest.raises(ValueError):
        normalize_scoring(data, 2026)


@pytest.mark.parametrize(
    "option",
    [
        "homeTeamBonus",
        "playoffHomeTeamBonus",
        "allowOutOfPositionScoring",
        "scoringEnhancementType",
    ],
)
def test_missing_scoring_controls_are_unknown_not_zero_defaults(option):
    data = settings()
    data.pop(option)
    assert not normalize_scoring(data, 2026).supported


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(homeTeamBonus="invalid"),
        lambda s: s["scoringItems"][0].update(points="1e100"),
    ],
)
def test_unusable_numeric_configuration_is_unsupported_not_an_unhandled_exception(change):
    data = settings()
    change(data)
    assert not normalize_scoring(data, 2026).supported
