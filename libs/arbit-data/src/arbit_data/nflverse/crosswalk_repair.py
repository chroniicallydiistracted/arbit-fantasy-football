"""Narrow, evidence-preserving correction of the reviewed supplemental-alias import defect."""

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import uuid4

from arbit_core.identity import require_aware
from sqlalchemy import Connection, func, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.league import content_hash
from arbit_data.schema import dataset_manifest, entity_alias, mapping_review


def _plan(connection: Connection) -> dict[str, Any]:
    rows = (
        connection.execute(
            select(entity_alias).where(
                entity_alias.c.provider == "espn",
                entity_alias.c.kind == "athlete",
                entity_alias.c.scope == "global",
                entity_alias.c.valid_to.is_(None),
            )
        )
        .mappings()
        .all()
    )
    groups: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        groups[str(row["entity_id"])].append(row)
    candidates = [r for group in groups.values() if len(group) > 1 for r in group]
    if not candidates:
        return {"hash": content_hash([]), "aliases": []}
    manifests = (
        connection.execute(
            select(dataset_manifest.c.hash, dataset_manifest.c.payload).where(
                dataset_manifest.c.hash.in_({r["evidence_manifest"] for r in candidates})
            )
        )
        .mappings()
        .all()
    )
    source = {r["hash"]: r["payload"]["source"] for r in manifests}
    changes = []
    for entity_id, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        later = [
            r
            for r in group
            if source.get(r["evidence_manifest"], {}).get("family") == "ff_playerids"
        ]
        retained = [r for r in group if r not in later]
        if (
            len(later) != 1
            or len(retained) != 1
            or later[0]["valid_from"] <= retained[0]["valid_from"]
            or later[0]["method"] != "verified_crosswalk"
        ):
            raise ValueError("MANUAL_MAPPING_REVIEW_REQUIRED")
        row = later[0]
        changes.append(
            {
                "entity_id": entity_id,
                "external_id": row["external_id"],
                "valid_from": row["valid_from"].isoformat(),
                "manifest_hash": row["evidence_manifest"],
                "retained_external_id": retained[0]["external_id"],
            }
        )
    return {"hash": content_hash(changes), "aliases": changes}


def plan_repairs(uow: UnitOfWork) -> dict[str, Any]:
    with uow.engine.connect() as c:
        return _plan(c)


def apply_repairs(uow: UnitOfWork, expected_plan_hash: str, now: datetime) -> dict[str, Any]:
    require_aware(now)
    with uow.engine.begin() as c:
        c.execute(select(func.pg_advisory_xact_lock(1729878439, -1)))
        plan = _plan(c)
        if plan["hash"] != expected_plan_hash:
            raise ValueError("CORRECTION_PLAN_CHANGED")
        for row in plan["aliases"]:
            start = datetime.fromisoformat(row["valid_from"])
            if now <= start:
                raise ValueError("INVALID_CORRECTION_TIME")
            result = c.execute(
                update(entity_alias)
                .where(
                    entity_alias.c.provider == "espn",
                    entity_alias.c.kind == "athlete",
                    entity_alias.c.scope == "global",
                    entity_alias.c.external_id == row["external_id"],
                    entity_alias.c.valid_from == start,
                    entity_alias.c.valid_to.is_(None),
                )
                .values(valid_to=now)
            )
            if result.rowcount != 1:
                raise ValueError("CORRECTION_PLAN_CHANGED")
            c.execute(
                insert(mapping_review).values(
                    id=uuid4(),
                    manifest_hash=row["manifest_hash"],
                    source_key="correction:espn:" + row["external_id"],
                    reason="SUPPLEMENTAL_PROVIDER_ID_CONFLICT",
                    payload={**row, "closed_at": now.isoformat(), "plan_hash": expected_plan_hash},
                )
            )
        return {
            "closed": len(plan["aliases"]),
            "plan_hash": expected_plan_hash,
            "preserved_original_alias_rows": True,
        }
