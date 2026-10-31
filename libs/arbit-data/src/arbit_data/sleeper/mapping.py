"""Read-only exact joins against trusted aliases; supplemental hints create no trust."""

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from arbit_core.identity import require_aware
from sqlalchemy import or_, select

from arbit_data.db import UnitOfWork
from arbit_data.schema import entity_alias


def _ids(row: dict[str, Any]) -> list[tuple[str, str]]:
    result = []
    for provider, field, pattern in [
        ("espn", "espn_id", r"[1-9][0-9]{0,19}"),
        ("gsis", "gsis_id", r"[0-9]{2}-[0-9]{7}"),
    ]:
        value = row.get(field)
        if value is not None and not isinstance(value, bool) and re.fullmatch(pattern, str(value)):
            result.append((provider, str(value)))
    return result


def identity_coverage(
    uow: UnitOfWork, directory: dict[str, Any], cutoff: datetime
) -> dict[str, Any]:
    require_aware(cutoff)
    if directory.get("kind") != "sleeper.players":
        raise ValueError("PLAYER_DIRECTORY_REQUIRED")
    with uow.engine.connect() as c:
        rows = (
            c.execute(
                select(entity_alias).where(
                    entity_alias.c.kind == "athlete",
                    entity_alias.c.scope == "global",
                    entity_alias.c.provider.in_(["espn", "gsis"]),
                    entity_alias.c.valid_from <= cutoff,
                    or_(entity_alias.c.valid_to.is_(None), entity_alias.c.valid_to > cutoff),
                )
            )
            .mappings()
            .all()
        )
    trusted = defaultdict(set)
    entity_ids = defaultdict(set)
    for row in rows:
        trusted[(row["provider"], row["external_id"])].add(row["entity_id"])
        entity_ids[(row["entity_id"], row["provider"])].add(row["external_id"])
    players = directory["data"]
    kinds = directory["entity_kinds"]
    refs = {key: _ids(row) for key, row in players.items() if kinds[key] == "athlete"}
    reused = Counter(ref for pairs in refs.values() for ref in pairs)
    report = []
    for key in players:
        entity = None
        status = "unresolved"
        reason = "no_verified_alias"
        if kinds[key] != "athlete":
            status = "excluded"
            reason = "non_athlete"
        else:
            pairs = refs[key]
            matches = set().union(*(trusted[ref] for ref in pairs)) if pairs else set()
            if any(reused[ref] > 1 for ref in pairs) or len(matches) > 1:
                status = "conflict"
                reason = "ambiguous_or_disagreeing_ids"
            elif len(matches) == 1:
                entity = next(iter(matches))
                if any(
                    entity_ids[(entity, provider)]
                    and external not in entity_ids[(entity, provider)]
                    for provider, external in pairs
                ):
                    status = "conflict"
                    reason = "entity_provider_disagreement"
                    entity = None
                else:
                    status = "linked"
                    reason = "exact_existing_alias"
        report.append(
            {
                "sleeper_id": key,
                "entity_id": str(entity) if entity else None,
                "status": status,
                "reason": reason,
            }
        )
    return {
        "read_only": True,
        "name_matching_used": False,
        "cutoff": cutoff.isoformat(),
        "counts": dict(Counter(row["status"] for row in report)),
        "records": report,
        "recommendations_enabled": False,
    }
