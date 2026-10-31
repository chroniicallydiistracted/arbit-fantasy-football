"""Bounded request filters observed in the audit; unsupported shapes fail before I/O."""

import re
from typing import Any


def validate_filter(value: dict[str, Any], *, directory: bool) -> None:
    if directory:
        active = value.get("filterActive")
        if (
            set(value) != {"filterActive"}
            or not isinstance(active, dict)
            or set(active) != {"value"}
            or type(active["value"]) is not bool
        ):
            raise ValueError("Unsupported directory filter")
        return
    players = value.get("players")
    if set(value) != {"players"} or not isinstance(players, dict):
        raise ValueError("Unsupported player filter")
    allowed = {
        "limit",
        "offset",
        "sortPercOwned",
        "filterStatus",
        "filterIds",
        "filterSlotIds",
        "filterRanksForScoringPeriodIds",
        "filterStatsForTopScoringPeriodIds",
    }
    if set(players) - allowed:
        raise ValueError("Unobserved player filter")
    for key, item in players.items():
        if key in {"limit", "offset"}:
            low, high = (1, 300) if key == "limit" else (0, 1_000_000)
            if type(item) is not int or not low <= item <= high:
                raise ValueError("Invalid filter bounds")
        elif key == "sortPercOwned":
            if (
                not isinstance(item, dict)
                or set(item) != {"sortPriority", "sortAsc"}
                or type(item["sortPriority"]) is not int
                or not 1 <= item["sortPriority"] <= 10
                or type(item["sortAsc"]) is not bool
            ):
                raise ValueError("Invalid sort filter")
        elif key == "filterStatsForTopScoringPeriodIds":
            if (
                not isinstance(item, dict)
                or set(item) != {"value", "additionalValue"}
                or type(item["value"]) is not int
                or not 1 <= item["value"] <= 100
            ):
                raise ValueError("Invalid stat period filter")
            codes = item["additionalValue"]
            if (
                not isinstance(codes, list)
                or not 1 <= len(codes) <= 10
                or any(
                    not isinstance(code, str) or re.fullmatch(r"\d{6}", code) is None
                    for code in codes
                )
            ):
                raise ValueError("Invalid stat source/season codes")
        else:
            if (
                not isinstance(item, dict)
                or set(item) != {"value"}
                or not isinstance(item["value"], list)
                or not 1 <= len(item["value"]) <= 300
            ):
                raise ValueError("Invalid value filter")
            entries = item["value"]
            if key == "filterStatus":
                if any(entry not in ("FREEAGENT", "WAIVERS", "ONTEAM") for entry in entries):
                    raise ValueError("Unsupported availability status")
            elif any(
                type(entry) is not int
                or (entry == 0 if key == "filterIds" else not 0 <= entry <= 99)
                for entry in entries
            ):
                raise ValueError("Invalid filter identifiers")
            if len(set(entries)) != len(entries):
                raise ValueError("Duplicate filter values")
