"""Bounded completed-period scoring verification; never enables recommendations."""

from dataclasses import dataclass
from typing import Any

from arbit_data.espn.endpoints import Endpoint, EndpointOptions
from arbit_data.espn.scoring_lineups import SUPPORTED_SLOTS, reconcile_period
from arbit_data.espn.scoring_mapping import CATEGORIES, MAPPING_SOURCE, MAPPING_VERSION
from arbit_data.espn.scoring_rules import NormalizedScoring, normalize_scoring
from arbit_data.espn.scoring_stats import ZERO_POLICY, ScoringDataError
from arbit_data.espn.transport import EspnError, SourceReceipt, utc_now
from arbit_data.espn.verification import SourceClient


@dataclass(frozen=True)
class Context:
    normalized: NormalizedScoring
    slots: dict[int, int]
    mapping: dict[int, tuple[int, ...]]
    size: int
    first: int
    latest: int
    final: int

    @property
    def fingerprint(self) -> tuple[Any, ...]:
        return (
            self.normalized.config_hash,
            self.slots,
            self.mapping,
            self.size,
            self.first,
            self.latest,
            self.final,
        )


def _integer(value: Any) -> int:
    if type(value) is not int:
        raise ScoringDataError("SCORING_SCHEMA_DRIFT")
    return value


def _context(payload: dict[str, Any], season: int) -> Context:
    try:
        settings = payload["settings"]
        status = payload["status"]
        raw_slots = settings["rosterSettings"]["lineupSlotCounts"]
        raw_mapping = settings["scheduleSettings"]["matchupPeriods"]
        if not isinstance(raw_slots, dict) or not raw_slots or not isinstance(raw_mapping, dict):
            raise ScoringDataError("SCORING_SCHEMA_DRIFT")
        slots = {int(key): _integer(value) for key, value in raw_slots.items()}
        if any(
            value < 0 or value > 0 and key not in SUPPORTED_SLOTS for key, value in slots.items()
        ):
            raise ScoringDataError("UNSUPPORTED_LINEUP_CONFIGURATION")
        mapping = {
            int(key): tuple(_integer(period) for period in periods)
            for key, periods in raw_mapping.items()
            if isinstance(periods, list)
        }
        if len(mapping) != len(raw_mapping):
            raise ScoringDataError("SCORING_SCHEMA_DRIFT")
        normalized = normalize_scoring(settings["scoringSettings"], season)
        size = _integer(settings["size"])
        first = _integer(status["firstScoringPeriod"])
        latest = _integer(status["latestScoringPeriod"])
        final = _integer(status["finalScoringPeriod"])
        if size <= 0 or not 1 <= first <= latest <= final <= 99:
            raise ScoringDataError("SCORING_SCHEMA_DRIFT")
        return Context(normalized, slots, mapping, size, first, latest, final)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ScoringDataError):
            raise
        raise ScoringDataError("SCORING_SCHEMA_DRIFT") from None


def _periods(context: Context, requested: tuple[int, ...] | None) -> tuple[tuple[int, int], ...]:
    selected = tuple(range(context.first, context.latest)) if requested is None else requested
    if (
        not selected
        or len(selected) > 17
        or len(set(selected)) != len(selected)
        or any(
            type(period) is not int or not context.first <= period < context.latest
            for period in selected
        )
    ):
        raise ScoringDataError("INVALID_COMPLETED_PERIOD")
    result = []
    for period in sorted(selected):
        matches = [(key, values) for key, values in context.mapping.items() if period in values]
        if len(matches) != 1:
            raise ScoringDataError("INVALID_PERIOD_MAPPING")
        matchup, values = matches[0]
        if len(values) != 1:
            raise ScoringDataError("MULTIWEEK_MATCHUPS_UNSUPPORTED")
        result.append((period, matchup))
    return tuple(result)


def _receipt(receipt: SourceReceipt) -> dict[str, Any]:
    return {
        "url": receipt.url,
        "observedAt": receipt.observed_at.isoformat(),
        "sha256": receipt.sha256,
        "bytes": receipt.byte_count,
    }


def _support(normalized: NormalizedScoring) -> dict[str, Any]:
    unsupported_ids = {
        int(issue.split(":")[0].split(".")[1])
        for issue in normalized.unsupported
        if issue.startswith("stat.")
    }
    return {
        "configuredRules": len(normalized.source_items),
        "supportedRules": len(normalized.source_items) - len(unsupported_ids),
        "supported": normalized.supported,
        "unsupported": list(normalized.unsupported),
        "configHash": normalized.config_hash,
        "athleteRulesHash": normalized.athlete_rules.content_hash,
        "defenseRulesHash": normalized.defense_rules.content_hash,
        "mappingVersion": MAPPING_VERSION,
        "mappingSource": MAPPING_SOURCE,
        "rules": [
            {
                "statId": item.stat_id,
                "metric": CATEGORIES[item.stat_id].stat if item.stat_id in CATEGORIES else None,
                "kind": "range"
                if item.stat_id in CATEGORIES and CATEGORIES[item.stat_id].is_range
                else "linear",
                "baseRate": str(item.points),
                "defenseRate": str(item.points_overrides.get("16", item.points)),
            }
            for item in normalized.source_items
        ],
    }


def audit_scoring(
    client: SourceClient, season: int, periods: tuple[int, ...] | None = None
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "leagueId": "1729878439",
        "season": season,
        "success": False,
        "verificationPassed": False,
        "recommendationsEnabled": False,
        "support": {},
        "periods": [],
        "sources": [],
        "issues": [],
        "totals": {
            "rosterEntries": 0,
            "verifiedPlayerGames": 0,
            "providerZeroEntries": 0,
            "lineupsChecked": 0,
            "lineupsMatched": 0,
            "mismatches": 0,
            "errors": 0,
        },
        "nonzeroRuleIds": [],
        "unobservedNonzeroRuleIds": [],
        "sparseZeroPolicy": ZERO_POLICY,
        "comparisonQuantum": "0.01",
        "comparisonRounding": "half_up",
        "startedAt": utc_now().isoformat(),
    }
    try:
        first = client.fetch(
            Endpoint.LEAGUE, EndpointOptions(season=season, views=("mSettings", "mStatus"))
        )
        report["sources"].append(_receipt(first.receipt))
        if first.capability != "available":
            raise ScoringDataError("REQUIRED_SOURCE_CAPABILITY_UNAVAILABLE")
        if not isinstance(first.payload, dict):
            raise ScoringDataError("SCORING_SCHEMA_DRIFT")
        context = _context(first.payload, season)
        report["support"] = _support(context.normalized)
        if not context.normalized.supported:
            raise ScoringDataError("UNSUPPORTED_RULES")
        requested = _periods(context, periods)
        observed: set[int] = set()
        for period, matchup in requested:
            response = client.fetch(
                Endpoint.LEAGUE,
                EndpointOptions(
                    season=season,
                    views=("mRoster", "mBoxscore", "mMatchupScore"),
                    scoring_period=period,
                    matchup_period=matchup,
                ),
            )
            report["sources"].append(_receipt(response.receipt))
            if response.capability != "available":
                raise ScoringDataError("REQUIRED_SOURCE_CAPABILITY_UNAVAILABLE")
            if not isinstance(response.payload, dict):
                raise ScoringDataError("SCORING_SCHEMA_DRIFT")
            result = reconcile_period(
                response.payload, period, matchup, context.normalized, context.slots, context.size
            )
            report["periods"].append(result)
            for key in report["totals"]:
                report["totals"][key] += result[key]
            observed.update(result["nonzeroRuleIds"])
            report["issues"].extend(
                {"scoringPeriod": period, **issue} for issue in result["issues"]
            )
        last = client.fetch(
            Endpoint.LEAGUE, EndpointOptions(season=season, views=("mSettings", "mStatus"))
        )
        report["sources"].append(_receipt(last.receipt))
        if last.capability != "available":
            raise ScoringDataError("REQUIRED_SOURCE_CAPABILITY_UNAVAILABLE")
        if (
            not isinstance(last.payload, dict)
            or _context(last.payload, season).fingerprint != context.fingerprint
        ):
            raise ScoringDataError("SOURCE_CHANGED")
        report["nonzeroRuleIds"] = sorted(observed)
        report["unobservedNonzeroRuleIds"] = sorted(
            {item.stat_id for item in context.normalized.source_items} - observed
        )
        report["success"] = (
            not report["issues"]
            and report["totals"]["verifiedPlayerGames"] > 0
            and report["totals"]["lineupsMatched"] == report["totals"]["lineupsChecked"] > 0
        )
        report["verificationPassed"] = report["success"]
    except ScoringDataError as error:
        report["issues"].append({"code": error.code})
    except EspnError as error:
        report["issues"].append(
            {
                "code": error.code,
                "status": error.status,
                "retryAfterSeconds": error.retry_after_seconds,
            }
        )
    report["finishedAt"] = utc_now().isoformat()
    return report
