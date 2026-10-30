from decimal import Decimal as D

import pytest


def rules(*items, scope="game"):
    from arbit_core.rules import RuleSet

    return RuleSet(
        version="synthetic-v1", scope=scope, quantum=D("0.01"), rounding="half_up", rules=items
    )


def test_hand_calculated_score_and_contributions():
    from arbit_core.rules import LinearRule, StatLine
    from arbit_core.scoring import score

    configured = rules(
        LinearRule(id="p", stat="pass_yards", rate=D("0.04")),
        LinearRule(id="td", stat="pass_td", rate=D("4")),
        LinearRule(id="int", stat="interceptions", rate=D("-2")),
        LinearRule(id="r", stat="rush_yards", rate=D("0.1")),
    )
    result = score(
        StatLine(
            scope="game",
            values={
                "pass_yards": D("250"),
                "pass_td": D("2"),
                "interceptions": D("1"),
                "rush_yards": D("25"),
            },
        ),
        configured,
    )
    assert result.total == D("18.50")
    assert [item.points for item in result.contributions] == [D("10"), D("8"), D("-2"), D("2.5")]
    assert len(result.rules_hash) == 64


@pytest.mark.parametrize(
    ("yards", "expected"), [("299", "11.96"), ("300", "15.00"), ("301", "15.04"), ("-5", "-0.20")]
)
def test_threshold_boundary_and_negative_fractional_yards(yards, expected):
    from arbit_core.rules import LinearRule, StatLine, ThresholdRule
    from arbit_core.scoring import score

    configured = rules(
        LinearRule(id="p", stat="yards", rate=D("0.04")),
        ThresholdRule(id="bonus", stat="yards", threshold=D("300"), points=D("3")),
    )
    assert score(StatLine(scope="game", values={"yards": D(yards)}), configured).total == D(
        expected
    )


@pytest.mark.parametrize("value", [None, "missing"])
def test_unknown_statistics_are_not_zero(value):
    from arbit_core.rules import LinearRule, StatLine
    from arbit_core.scoring import MissingStatError, score

    values = {} if value == "missing" else {"yards": None}
    with pytest.raises(MissingStatError):
        score(
            StatLine(scope="game", values=values),
            rules(LinearRule(id="p", stat="yards", rate=D("0.04"))),
        )
    assert score(
        StatLine(scope="game", values={"yards": D("0")}),
        rules(LinearRule(id="p", stat="yards", rate=D("0.04"))),
    ).total == D("0.00")


def test_unknown_rules_fail_before_generating_any_score():
    from arbit_core.rules import StatLine, UnsupportedRule
    from arbit_core.scoring import UnsupportedRuleError, score

    with pytest.raises(UnsupportedRuleError) as error:
        score(
            StatLine(scope="game", values={}),
            rules(UnsupportedRule(id="9999", source_definition='{"statId":9999}')),
        )
    assert error.value.rule_ids == ("9999",)


@pytest.mark.parametrize(
    ("distance", "expected"), [("39", "3.00"), ("40", "4.00"), ("49", "4.00"), ("50", "5.00")]
)
def test_distance_ranges_are_half_open(distance, expected):
    from arbit_core.rules import RangeRule, StatLine
    from arbit_core.scoring import score

    configured = rules(
        RangeRule(id="short", stat="fg_distance", lower=D("0"), upper=D("40"), points=D("3")),
        RangeRule(id="medium", stat="fg_distance", lower=D("40"), upper=D("50"), points=D("4")),
        RangeRule(id="long", stat="fg_distance", lower=D("50"), points=D("5")),
    )
    assert score(
        StatLine(scope="game", values={"fg_distance": D(distance)}), configured
    ).total == D(expected)


def test_scope_mismatch_and_corrections_do_not_reuse_old_totals():
    from arbit_core.rules import RangeRule, StatLine
    from arbit_core.scoring import score

    configured = rules(
        RangeRule(id="dst", stat="points_allowed", lower=D("0"), upper=D("7"), points=D("10"))
    )
    assert score(StatLine(scope="game", values={"points_allowed": D("6")}), configured).total == D(
        "10.00"
    )
    assert score(StatLine(scope="game", values={"points_allowed": D("7")}), configured).total == D(
        "0.00"
    )
    with pytest.raises(ValueError, match="scope"):
        score(StatLine(scope="season", values={"points_allowed": D("6")}), configured)


def test_bonus_is_per_game_and_rounding_occurs_once_at_end():
    from arbit_core.rules import LinearRule, StatLine, ThresholdRule
    from arbit_core.scoring import score

    bonus = rules(ThresholdRule(id="bonus", stat="yards", threshold=D("300"), points=D("3")))
    assert sum(
        score(StatLine(scope="game", values={"yards": D(x)}), bonus).total for x in ["200", "200"]
    ) == D("0")
    configured = rules(
        LinearRule(id="a", stat="x", rate=D("0.005")), LinearRule(id="b", stat="y", rate=D("0.005"))
    )
    assert score(StatLine(scope="game", values={"x": D("1"), "y": D("1")}), configured).total == D(
        "0.01"
    )
