"""Exact trusted GSIS/ESPN crosswalks, with ambiguity retained instead of entity merging."""

import re
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from arbit_core.identity import require_aware
from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert

from arbit_data.schema import canonical_entity, entity_alias, identity_import, mapping_review


def apply_crosswalk(
    connection: Connection, rows: list[dict[str, Any]], manifest_hash: str, observed_at: datetime
) -> dict[str, int]:
    require_aware(observed_at)
    connection.execute(select(func.pg_advisory_xact_lock(1729878439, -1)))
    saved = connection.scalar(
        select(identity_import.c.payload).where(identity_import.c.manifest_hash == manifest_hash)
    )
    if saved is not None:
        return dict(saved)
    source: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    valid: set[str] = set()
    reviews: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        gsis, espn = row.get("gsis_id"), row.get("espn_id")
        if not isinstance(gsis, str) or not re.fullmatch(r"[0-9]{2}-[0-9]{7}", gsis):
            reviews["row:" + str(index)] = {
                "reason": "INVALID_OR_MISSING_GSIS",
                "payload": {"row_index": index},
            }
            continue
        if espn is not None and (
            not isinstance(espn, str) or not re.fullmatch(r"[1-9][0-9]*", espn)
        ):
            reviews[gsis] = {"reason": "INVALID_ESPN", "payload": {"gsis_id": gsis}}
            continue
        valid.add(gsis)
        if espn is not None:
            source[gsis].add(espn)
            reverse[espn].add(gsis)
    observed = (
        connection.execute(
            select(entity_alias).where(
                entity_alias.c.kind == "athlete",
                entity_alias.c.scope == "global",
                entity_alias.c.provider.in_(("espn", "gsis")),
            )
        )
        .mappings()
        .all()
    )
    current = {
        (r["provider"], r["external_id"]): dict(r) for r in observed if r["valid_to"] is None
    }
    historic = {(r["provider"], r["external_id"]) for r in observed if r["valid_to"] is not None}
    entities = []
    aliases = []
    report = {
        "linked": 0,
        "created_entities": 0,
        "created_aliases": 0,
        "conflicts": 0,
        "unresolved": len(reviews),
    }
    for gsis in sorted(valid):
        espns = source[gsis]
        espn = next(iter(espns)) if len(espns) == 1 else None
        keys = [("gsis", gsis)] + ([("espn", espn)] if espn is not None else [])
        records = [current[k] for k in keys if k in current]
        distinct = {r["entity_id"] for r in records}
        reason = (
            "AMBIGUOUS_CROSSWALK"
            if len(espns) > 1 or espn is not None and len(reverse[espn]) > 1
            else "EXISTING_ALIAS_CONFLICT"
            if len(distinct) > 1
            else "MAPPING_PREDATES_EVIDENCE"
            if any(r["valid_from"] > observed_at for r in records)
            else "CLOSED_ALIAS_REQUIRES_REVIEW"
            if any(k in historic and k not in current for k in keys)
            else None
        )
        if reason is not None:
            reviews[gsis] = {
                "reason": reason,
                "payload": {
                    "gsis_id": gsis,
                    "espn_ids": sorted(espns),
                    "existing_entity_ids": sorted(str(v) for v in distinct),
                },
            }
            report["conflicts"] += 1
            continue
        entity_id = next(iter(distinct)) if distinct else uuid4()
        if not distinct:
            entities.append({"id": entity_id, "kind": "athlete", "created_at": observed_at})
        for provider, external_id in keys:
            if (provider, external_id) in current:
                continue
            value = {
                "provider": provider,
                "kind": "athlete",
                "scope": "global",
                "external_id": external_id,
                "entity_id": entity_id,
                "valid_from": observed_at,
                "method": "verified_crosswalk"
                if distinct or provider == "espn"
                else "source_native",
                "evidence_manifest": manifest_hash,
            }
            aliases.append(value)
            current[(provider, external_id)] = value
        report["linked"] += 1
    for table, values in ((canonical_entity, entities), (entity_alias, aliases)):
        for start in range(0, len(values), 500):
            connection.execute(insert(table), values[start : start + 500])
    report["created_entities"] = len(entities)
    report["created_aliases"] = len(aliases)
    for key, review in reviews.items():
        connection.execute(
            insert(mapping_review)
            .values(id=uuid4(), manifest_hash=manifest_hash, source_key=key, **review)
            .on_conflict_do_nothing(
                index_elements=[mapping_review.c.manifest_hash, mapping_review.c.source_key]
            )
        )
    connection.execute(insert(identity_import).values(manifest_hash=manifest_hash, payload=report))
    return report
