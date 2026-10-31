"""Recompute scoped actual scores from raw statistics, then compare source references."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, DecimalException
from typing import Any, Literal

from arbit_core.rules import LinearRule, RangeRule, StatLine
from arbit_core.scoring import score
from pydantic import StrictInt, ValidationError

from arbit_data.espn.contracts import ProviderModel, StatBlock
from arbit_data.espn.scoring_mapping import CATEGORIES
from arbit_data.espn.scoring_rules import CENT, NormalizedScoring, Role, role_for_position

ZERO_POLICY = "espn-complete-actual-gp1-sparse-counters-v1"


class ScoringDataError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ScoringPlayer(ProviderModel):
    id: StrictInt
    default_position_id: StrictInt
    stats: tuple[StatBlock, ...]


@dataclass(frozen=True)
class ContributionDifference:
    rule_id: str
    computed: Decimal
    official: Decimal


@dataclass(frozen=True)
class PlayerReconciliation:
    status: Literal["verified", "provider_zero", "mismatch"]
    role: Role
    position: int
    computed_total: Decimal | None
    official_total: Decimal
    pool_total: Decimal
    total_delta: Decimal
    pool_delta: Decimal
    reference_sum_delta: Decimal
    contribution_differences: tuple[ContributionDifference, ...]
    zero_suppressed_ids: tuple[int, ...]
    observed_rule_ids: tuple[int, ...]


def cents(value: Decimal) -> Decimal:
    try:
        if not value.is_finite():
            raise ScoringDataError("INVALID_NUMERIC")
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    except DecimalException:
        raise ScoringDataError("INVALID_NUMERIC") from None


def _provider_zero(role: Role, position: int) -> PlayerReconciliation:
    return PlayerReconciliation(
        "provider_zero",
        role,
        position,
        None,
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(0),
        Decimal(0),
        (),
        (),
        (),
    )


def reconcile_player(
    player: dict[str, Any], period: int, normalized: NormalizedScoring, official_pool_total: Decimal
) -> PlayerReconciliation:
    if not normalized.supported:
        raise ScoringDataError("UNSUPPORTED_RULES")
    if type(period) is not int or not 1 <= period <= 99:
        raise ScoringDataError("INVALID_PERIOD")
    try:
        parsed = ScoringPlayer.model_validate(player)
    except ValidationError:
        raise ScoringDataError("SCHEMA_DRIFT") from None
    try:
        role = role_for_position(parsed.default_position_id)
    except ValueError:
        raise ScoringDataError("UNSUPPORTED_POSITION") from None
    if parsed.id == 0 or (parsed.id < 0) != (role == "defense_unit"):
        raise ScoringDataError("UNSUPPORTED_ENTITY")
    if not isinstance(official_pool_total, Decimal):
        raise ScoringDataError("MISSING_OFFICIAL_TOTAL")
    pool_total = cents(official_pool_total)
    blocks = [
        block
        for block in parsed.stats
        if block.season_id == normalized.season
        and block.scoring_period_id == period
        and block.stat_source_id == 0
        and block.stat_split_type_id == 1
    ]
    if len(blocks) > 1:
        raise ScoringDataError("AMBIGUOUS_ACTUAL_BLOCK")
    if not blocks:
        if pool_total == 0:
            return _provider_zero(role, parsed.default_position_id)
        raise ScoringDataError("MISSING_ACTUAL_BLOCK")
    block = blocks[0]
    if block.stats is None:
        raise ScoringDataError("MISSING_STAT_MAP")
    if block.applied_stats is None:
        raise ScoringDataError("MISSING_APPLIED_STATS")
    if block.applied_total is None:
        raise ScoringDataError("MISSING_OFFICIAL_TOTAL")
    official = cents(block.applied_total)
    stats = block.stats
    applied = block.applied_stats
    games = stats.get("210")
    if games != 1:
        if (
            pool_total == 0
            and official == 0
            and not any(applied.values())
            and (not stats or games == 0 and not any(stats.values()))
        ):
            return _provider_zero(role, parsed.default_position_id)
        raise ScoringDataError("MISSING_GAME_MARKER" if games is None else "MULTI_GAME_UNSUPPORTED")
    values: dict[str, Decimal | None] = {}
    suppressed = []
    rules = normalized.rules_for(role)
    for rule in rules.rules:
        category = CATEGORIES[int(rule.id)]
        raw = stats.get(category.raw)
        if isinstance(rule, LinearRule):
            if raw is None:
                if applied.get(rule.id, Decimal(0)) != 0:
                    raise ScoringDataError("MISSING_SCORED_STAT")
                raw = Decimal(0)
                suppressed.append(int(rule.id))
            values[category.stat] = raw
        elif isinstance(rule, RangeRule):
            if raw is None:
                raise ScoringDataError("MISSING_RANGE_TOTAL")
            values[category.stat] = raw
            expected = Decimal(
                int(
                    (rule.lower is None or raw >= rule.lower)
                    and (rule.upper is None or raw < rule.upper)
                )
            )
            indicator = stats.get(rule.id)
            if indicator is None and expected != 0:
                raise ScoringDataError("MISSING_RANGE_INDICATOR")
            if indicator is not None and indicator != expected:
                raise ScoringDataError("STAT_RANGE_MISMATCH")
    try:
        computed = score(StatLine(scope="game", values=values), rules)
    except (ValueError, ArithmeticError):
        raise ScoringDataError("STAT_ARITHMETIC_FAILED") from None
    differences = []
    observed = []
    computed_ids = {item.rule_id for item in computed.contributions}
    for contribution in computed.contributions:
        reference = cents(applied.get(contribution.rule_id, Decimal(0)))
        calculated = cents(contribution.points)
        if calculated != reference:
            differences.append(ContributionDifference(contribution.rule_id, calculated, reference))
        if calculated != 0:
            observed.append(int(contribution.rule_id))
    for key, value in applied.items():
        if not key.isascii() or not key.isdigit():
            raise ScoringDataError("INVALID_APPLIED_CATEGORY")
        if key not in computed_ids and value != 0:
            differences.append(ContributionDifference(key, Decimal(0), cents(value)))
    try:
        sum_delta = cents(sum(applied.values(), Decimal(0))) - official
    except DecimalException:
        raise ScoringDataError("INVALID_NUMERIC") from None
    total_delta = computed.total - official
    pool_delta = computed.total - pool_total
    status: Literal["verified", "mismatch"] = (
        "verified"
        if not differences and total_delta == 0 and pool_delta == 0 and sum_delta == 0
        else "mismatch"
    )
    return PlayerReconciliation(
        status,
        role,
        parsed.default_position_id,
        computed.total,
        official,
        pool_total,
        total_delta,
        pool_delta,
        sum_delta,
        tuple(differences),
        tuple(sorted(suppressed)),
        tuple(sorted(observed)),
    )
