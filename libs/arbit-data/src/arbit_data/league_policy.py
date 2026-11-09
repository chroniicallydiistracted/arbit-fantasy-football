"""One typed reading of a stored rule version's league settings for every consumer.

Rule versions keep ESPN's settings as observed (`provider_policy`). This module turns the parts
members and later advisors need into plain values. Anything absent or of an unexpected shape stays
unknown; nothing here substitutes a default for a league rule.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Lineup order for display; slots the league doesn't use are left out.
SLOT_ORDER = ("QB", "RB", "RB_WR", "WR", "WR_TE", "TE", "FLEX", "OP", "DST", "K", "BENCH", "IR")
WEEKDAYS = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


@dataclass(frozen=True)
class LeaguePolicy:
    lineup_slots: tuple[str, ...]
    waiver_type: str | None
    waiver_hours: int | None
    waiver_days: tuple[str, ...]
    uses_bidding: bool | None
    trade_deadline: datetime | None
    trade_veto_votes: int | None
    trade_review_hours: int | None
    regular_season_matchups: int | None
    playoff_team_count: int | None
    playoff_tiebreaker: str | None


def _int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _section(rules: dict[str, Any] | None, name: str) -> dict[str, Any]:
    policy = (rules or {}).get("provider_policy") or {}
    section = policy.get(name) if isinstance(policy, dict) else None
    return section if isinstance(section, dict) else {}


def read_policy(rules: dict[str, Any] | None) -> LeaguePolicy:
    slots = (rules or {}).get("lineup_slots")
    used = set(slots) if isinstance(slots, dict) else set()
    acquisition = _section(rules, "acquisitionSettings")
    trade = _section(rules, "tradeSettings")
    schedule = _section(rules, "scheduleSettings")
    deadline = trade.get("deadlineDate")
    days = acquisition.get("waiverProcessDays")
    budget = acquisition.get("isUsingAcquisitionBudget")
    playoff_teams = _int(schedule.get("playoffTeamCount"))
    tiebreaker = schedule.get("playoffSeedingRule")
    veto = _int(trade.get("vetoVotesRequired"))
    return LeaguePolicy(
        lineup_slots=tuple(slot for slot in SLOT_ORDER if slot in used),
        waiver_type=acquisition.get("acquisitionType")
        if isinstance(acquisition.get("acquisitionType"), str)
        else None,
        waiver_hours=_int(acquisition.get("waiverHours")),
        waiver_days=tuple(day for day in WEEKDAYS if isinstance(days, list) and day in days),
        uses_bidding=budget if isinstance(budget, bool) else None,
        # ESPN states the deadline in epoch milliseconds.
        trade_deadline=datetime.fromtimestamp(deadline / 1000, UTC)
        if type(deadline) is int and deadline > 0
        else None,
        trade_veto_votes=veto,
        trade_review_hours=_int(trade.get("revisionHours")),
        regular_season_matchups=_int(schedule.get("matchupPeriodCount")) or None,
        playoff_team_count=playoff_teams or None,
        playoff_tiebreaker=tiebreaker if isinstance(tiebreaker, str) else None,
    )
