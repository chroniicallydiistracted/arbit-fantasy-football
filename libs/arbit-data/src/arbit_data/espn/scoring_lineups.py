"""Reconcile archived period rosters; bench/IR scores never enter starting totals."""

from collections import Counter
from decimal import Decimal, DecimalException
from typing import Any

from arbit_data.espn.scoring_rules import NormalizedScoring
from arbit_data.espn.scoring_stats import ScoringDataError, cents, reconcile_player

BENCH_IR = {20, 21}
SUPPORTED_SLOTS = {0, 2, 4, 6, 16, 17, 20, 21, 23}


def amount(value: Any) -> Decimal:
    try:
        if value is None or isinstance(value, bool):
            raise ScoringDataError("MISSING_OFFICIAL_TOTAL")
        result = Decimal(str(value))
        if not result.is_finite():
            raise ScoringDataError("INVALID_NUMERIC")
        return result
    except DecimalException:
        raise ScoringDataError("INVALID_NUMERIC") from None


def reconcile_period(
    payload: dict[str, Any],
    period: int,
    matchup: int,
    normalized: NormalizedScoring,
    slots: dict[int, int],
    team_count: int,
) -> dict[str, Any]:
    schedule = payload.get("schedule")
    if not isinstance(schedule, list):
        raise ScoringDataError("MISSING_SCHEDULE")
    selected = [
        game
        for game in schedule
        if isinstance(game, dict) and game.get("matchupPeriodId") == matchup
    ]
    if not selected:
        raise ScoringDataError("MISSING_MATCHUP")
    counts = {
        "rosterEntries": 0,
        "verifiedPlayerGames": 0,
        "providerZeroEntries": 0,
        "lineupsChecked": 0,
        "lineupsMatched": 0,
        "mismatches": 0,
        "errors": 0,
    }
    issues = []
    positions: Counter[str] = Counter()
    observed: set[int] = set()
    teams: set[int] = set()
    starters: set[int] = set()
    for game in selected:
        for side in [game.get("home"), game.get("away")]:
            if side is None:
                continue
            lineup_index = counts["lineupsChecked"]
            counts["lineupsChecked"] += 1
            total = Decimal(0)
            complete = True
            seen: set[int] = set()
            used: Counter[int] = Counter()
            try:
                if not isinstance(side, dict) or type(side.get("teamId")) is not int:
                    raise ScoringDataError("INVALID_TEAM")
                if side["teamId"] in teams:
                    raise ScoringDataError("DUPLICATE_TEAM")
                teams.add(side["teamId"])
                roster = side.get("rosterForCurrentScoringPeriod")
                if not isinstance(roster, dict) or not isinstance(roster.get("entries"), list):
                    raise ScoringDataError("MISSING_MATCHUP_ROSTER")
                entries = roster["entries"]
                official = cents(amount(side.get("totalPoints")))
                roster_total = cents(amount(roster.get("appliedStatTotal")))
            except ScoringDataError as error:
                counts["errors"] += 1
                issues.append({"code": error.code, "lineupIndex": lineup_index})
                continue
            for entry_index, entry in enumerate(entries):
                counts["rosterEntries"] += 1
                active = False
                try:
                    if not isinstance(entry, dict) or type(entry.get("lineupSlotId")) is not int:
                        raise ScoringDataError("INVALID_LINEUP_ENTRY")
                    slot = entry["lineupSlotId"]
                    if slot not in SUPPORTED_SLOTS or slots.get(slot, 0) <= 0:
                        raise ScoringDataError("UNSUPPORTED_LINEUP_SLOT")
                    active = slot not in BENCH_IR
                    identity = entry.get("playerId")
                    pool = entry.get("playerPoolEntry")
                    if (
                        type(identity) is not int
                        or not isinstance(pool, dict)
                        or not isinstance(pool.get("player"), dict)
                        or pool.get("id") != identity
                        or pool["player"].get("id") != identity
                    ):
                        raise ScoringDataError("INVALID_PLAYER_IDENTITY")
                    if identity in seen:
                        raise ScoringDataError("DUPLICATE_ROSTER_PLAYER")
                    seen.add(identity)
                    if active:
                        if identity in starters:
                            raise ScoringDataError("DUPLICATE_STARTER")
                        starters.add(identity)
                        used[slot] += 1
                        if used[slot] > slots[slot]:
                            raise ScoringDataError("LINEUP_SLOT_OVERFILLED")
                    result = reconcile_player(
                        pool["player"], period, normalized, amount(pool.get("appliedStatTotal"))
                    )
                    if result.status == "provider_zero":
                        counts["providerZeroEntries"] += 1
                    elif result.status == "verified":
                        counts["verifiedPlayerGames"] += 1
                        positions[str(result.position)] += 1
                    else:
                        counts["mismatches"] += 1
                        issues.append(
                            {
                                "code": "PLAYER_SCORE_MISMATCH",
                                "lineupIndex": lineup_index,
                                "entryIndex": entry_index,
                                "totalDelta": str(result.total_delta),
                                "poolDelta": str(result.pool_delta),
                                "referenceSumDelta": str(result.reference_sum_delta),
                                "contributions": [
                                    {
                                        "statId": difference.rule_id,
                                        "computed": str(difference.computed),
                                        "official": str(difference.official),
                                    }
                                    for difference in result.contribution_differences
                                ],
                            }
                        )
                    observed.update(result.observed_rule_ids)
                    if active:
                        total += (
                            result.computed_total
                            if result.computed_total is not None
                            else result.official_total
                        )
                except ScoringDataError as error:
                    counts["errors"] += 1
                    complete = False
                    issues.append(
                        {"code": error.code, "lineupIndex": lineup_index, "entryIndex": entry_index}
                    )
            if complete and cents(total) == official and roster_total == official:
                counts["lineupsMatched"] += 1
            else:
                counts["mismatches"] += 1
                issues.append(
                    {
                        "code": "LINEUP_SCORE_MISMATCH",
                        "lineupIndex": lineup_index,
                        "computed": str(cents(total)) if complete else None,
                        "official": str(official),
                        "rosterTotal": str(roster_total),
                    }
                )
    if len(teams) != team_count:
        counts["errors"] += 1
        issues.append(
            {"code": "INCOMPLETE_TEAM_COVERAGE", "expected": team_count, "observed": len(teams)}
        )
    return {
        "scoringPeriod": period,
        "matchupPeriod": matchup,
        **counts,
        "verifiedByPosition": dict(positions),
        "nonzeroRuleIds": sorted(observed),
        "issues": issues,
    }
