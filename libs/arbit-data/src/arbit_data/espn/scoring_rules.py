"""Compile fetched FFA scoring definitions into the shared exact scoring engine."""

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from typing import Any, Literal

from arbit_core.rules import LinearRule, RangeRule, Rule, RuleSet, UnsupportedRule

from arbit_data.espn.contracts import ScoringItem, ScoringSettings
from arbit_data.espn.scoring_mapping import CATEGORIES, MAPPING_VERSION

CENT = Decimal("0.01")
Role = Literal["athlete", "defense_unit"]


@dataclass(frozen=True)
class NormalizedScoring:
    season: int
    source_items: tuple[ScoringItem, ...]
    athlete_rules: RuleSet
    defense_rules: RuleSet
    unsupported: tuple[str, ...]
    config_hash: str

    @property
    def supported(self) -> bool:
        return not self.unsupported

    def rules_for(self, role: Role) -> RuleSet:
        return self.defense_rules if role == "defense_unit" else self.athlete_rules


def role_for_position(position: int) -> Role:
    if type(position) is not int:
        raise ValueError("Unsupported scoring position")
    if position == 16:
        return "defense_unit"
    if position in (1, 2, 3, 4, 5):
        return "athlete"
    raise ValueError("Unsupported scoring position")


def _decimal_text(value: Decimal) -> str:
    try:
        return str(value.normalize())
    except DecimalException:
        return str(value)


def _zero_control(value: Any) -> bool:
    try:
        number = Decimal(str(value))
        return number.is_finite() and number == 0
    except (DecimalException, ValueError):
        return False


def _cent_rates(values: list[Decimal]) -> bool:
    try:
        return all(value == value.quantize(CENT) for value in values)
    except DecimalException:
        return False


def normalize_scoring(settings: dict[str, Any], season: int) -> NormalizedScoring:
    if type(season) is not int or not 2026 <= season <= 2100:
        raise ValueError("Explicit supported season required")
    parsed = ScoringSettings.model_validate(settings)
    items = tuple(sorted(parsed.scoring_items, key=lambda item: item.stat_id))
    if len({item.stat_id for item in items}) != len(items):
        raise ValueError("Duplicate scoring category")
    recognized = {
        "scoringItems",
        "scoringType",
        "allowOutOfPositionScoring",
        "homeTeamBonus",
        "matchupTieRule",
        "matchupTieRuleBy",
        "playerRankType",
        "playoffHomeTeamBonus",
        "playoffMatchupTieRule",
        "playoffMatchupTieRuleBy",
        "scoringEnhancementType",
    }
    unsupported = []
    for option in (
        "homeTeamBonus",
        "playoffHomeTeamBonus",
        "allowOutOfPositionScoring",
        "scoringEnhancementType",
    ):
        if option not in settings:
            unsupported.append(f"settings.{option}:missing_control")
    for option in set(settings) - recognized:
        unsupported.append(f"settings.{option}:unknown_option")
    if parsed.scoring_type != "H2H_POINTS":
        unsupported.append("settings.scoringType:unsupported")
    for option in ["homeTeamBonus", "playoffHomeTeamBonus"]:
        if not _zero_control(settings.get(option, 0)):
            unsupported.append(f"settings.{option}:unsupported_bonus")
    if settings.get("scoringEnhancementType", "NONE") != "NONE":
        unsupported.append("settings.scoringEnhancementType:unsupported")
    if settings.get("allowOutOfPositionScoring", False) is not False:
        unsupported.append("settings.allowOutOfPositionScoring:unsupported")
    global_unsupported = tuple(unsupported)
    rules: dict[Role, list[Rule]] = {"athlete": [], "defense_unit": []}
    canonical_items = []
    for item in items:
        source = {
            "statId": item.stat_id,
            "points": _decimal_text(item.points),
            "pointsOverrides": {
                key: _decimal_text(value) for key, value in sorted(item.points_overrides.items())
            },
            "isReverseItem": item.is_reverse_item,
        }
        extras = set(item.model_extra or {}) - {"leagueRanking", "leagueTotal"}
        category = CATEGORIES.get(item.stat_id)
        issue = None
        if category is None:
            issue = "unknown_category"
        elif item.is_reverse_item:
            issue = "reverse_item"
        elif set(item.points_overrides) - {"16"}:
            issue = "unsupported_override"
        elif extras:
            issue = "unknown_rule_options"
        elif not _cent_rates([item.points, *item.points_overrides.values()]):
            issue = "unsupported_subcent_rate"
        if issue:
            unsupported.append(f"stat.{item.stat_id}:{issue}")
        source["unknownOptions"] = {key: (item.model_extra or {})[key] for key in extras}
        canonical_items.append(source)
        for role in ("athlete", "defense_unit"):
            role_key: Role = role
            rate = (
                item.points_overrides.get("16", item.points)
                if role == "defense_unit"
                else item.points
            )
            if issue:
                rules[role_key].append(
                    UnsupportedRule(
                        id=str(item.stat_id),
                        source_definition=json.dumps(source, sort_keys=True, default=str),
                    )
                )
            elif rate != 0:
                assert category is not None
                if category.is_range:
                    if role != "defense_unit":
                        unsupported.append(f"stat.{item.stat_id}:range_for_non_defense")
                        rules[role_key].append(
                            UnsupportedRule(
                                id=str(item.stat_id),
                                source_definition=json.dumps(source, sort_keys=True, default=str),
                            )
                        )
                    else:
                        rules[role_key].append(
                            RangeRule(
                                id=str(item.stat_id),
                                stat=category.stat,
                                lower=None if category.lower is None else Decimal(category.lower),
                                upper=None if category.upper is None else Decimal(category.upper),
                                points=rate.normalize(),
                            )
                        )
                else:
                    rules[role_key].append(
                        LinearRule(id=str(item.stat_id), stat=category.stat, rate=rate.normalize())
                    )
    for diagnostic in global_unsupported:
        for role in rules:
            rules[role].append(UnsupportedRule(id=diagnostic, source_definition=diagnostic))
    options = {key: value for key, value in settings.items() if key != "scoringItems"}
    canonical = json.dumps(
        {
            "season": season,
            "mapping": MAPPING_VERSION,
            "options": options,
            "items": canonical_items,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    def compiled(role: Role) -> RuleSet:
        return RuleSet(
            version=f"{MAPPING_VERSION}:{season}:{role}",
            scope="game",
            quantum=CENT,
            rounding="half_up",
            rules=tuple(rules[role]),
        )

    return NormalizedScoring(
        season,
        items,
        compiled("athlete"),
        compiled("defense_unit"),
        tuple(sorted(set(unsupported))),
        hashlib.sha256(canonical.encode()).hexdigest(),
    )
