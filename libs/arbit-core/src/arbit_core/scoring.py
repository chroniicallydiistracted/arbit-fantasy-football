"""Pure exact-rule scoring with explicit missing/unsupported diagnostics."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext

from arbit_core.rules import (
    LinearRule,
    RangeRule,
    RuleSet,
    StatLine,
    ThresholdRule,
    UnsupportedRule,
)


class UnsupportedRuleError(ValueError):
    def __init__(self, rule_ids: tuple[str, ...]) -> None:
        self.rule_ids = rule_ids
        super().__init__("Unsupported scoring rule IDs: " + ", ".join(rule_ids))


class MissingStatError(ValueError):
    def __init__(self, stat_ids: tuple[str, ...]) -> None:
        self.stat_ids = stat_ids
        super().__init__("Required statistics unavailable: " + ", ".join(stat_ids))


@dataclass(frozen=True)
class ScoreContribution:
    rule_id: str
    stat_id: str
    points: Decimal


@dataclass(frozen=True)
class ScoreBreakdown:
    total: Decimal
    contributions: tuple[ScoreContribution, ...]
    rules_hash: str


def score(stat_line: StatLine, rules: RuleSet) -> ScoreBreakdown:
    if stat_line.scope != rules.scope:
        raise ValueError("statistical scope does not match rule scope")
    unsupported = tuple(rule.id for rule in rules.rules if isinstance(rule, UnsupportedRule))
    if unsupported:
        raise UnsupportedRuleError(unsupported)
    supported = [rule for rule in rules.rules if not isinstance(rule, UnsupportedRule)]
    missing = tuple(
        sorted({rule.stat for rule in supported if stat_line.values.get(rule.stat) is None})
    )
    if missing:
        raise MissingStatError(missing)
    contributions = []
    with localcontext() as context:
        context.prec = 50
        for rule in supported:
            value = stat_line.values[rule.stat]
            assert value is not None
            points = Decimal(0)
            if isinstance(rule, LinearRule):
                points = value * rule.rate
            elif isinstance(rule, ThresholdRule):
                points = rule.points if value >= rule.threshold else Decimal(0)
            elif isinstance(rule, RangeRule):
                if (rule.lower is None or value >= rule.lower) and (
                    rule.upper is None or value < rule.upper
                ):
                    points = rule.points
            contributions.append(ScoreContribution(rule.id, rule.stat, points))
        total = sum((item.points for item in contributions), Decimal(0))
        total = total.quantize(
            rules.quantum.normalize(),
            rounding=ROUND_HALF_UP if rules.rounding == "half_up" else ROUND_HALF_EVEN,
        )
    return ScoreBreakdown(total, tuple(contributions), rules.content_hash)
