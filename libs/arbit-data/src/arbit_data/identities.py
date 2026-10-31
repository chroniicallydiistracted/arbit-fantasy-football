"""Transactional exact native aliases. No names, fuzzy matches or unreviewed alias merges."""

from collections.abc import Iterable, Mapping
from datetime import datetime
from uuid import UUID, uuid4

from arbit_core.identity import ProviderRef, require_aware
from sqlalchemy import Connection, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.schema import canonical_entity, entity_alias, team_affiliation


def resolve_native(
    connection: Connection, refs: Iterable[ProviderRef], observed_at: datetime, manifest_hash: str
) -> dict[ProviderRef, UUID]:
    require_aware(observed_at)
    refs = set(refs)
    if not refs:
        return {}
    connection.execute(select(func.pg_advisory_xact_lock(1729878439, -1)))
    rows = (
        connection.execute(
            select(entity_alias).where(
                tuple_(
                    entity_alias.c.provider,
                    entity_alias.c.kind,
                    entity_alias.c.scope,
                    entity_alias.c.external_id,
                ).in_(
                    [(ref.provider, ref.entity_kind, ref.scope, ref.external_id) for ref in refs]
                ),
                entity_alias.c.valid_to.is_(None),
            )
        )
        .mappings()
        .all()
    )
    resolved: dict[ProviderRef, UUID] = {}
    for row in rows:
        if row["valid_from"] > observed_at:
            raise ValueError("ALIAS_PREDATES_VERIFIED_EVIDENCE")
        resolved[
            ProviderRef(
                provider=row["provider"],
                entity_kind=row["kind"],
                scope=row["scope"],
                external_id=row["external_id"],
            )
        ] = row["entity_id"]
    missing = refs - resolved.keys()
    entities, aliases = [], []
    for ref in sorted(missing, key=lambda r: (r.provider, r.entity_kind, r.scope, r.external_id)):
        entity_id = uuid4()
        resolved[ref] = entity_id
        entities.append({"id": entity_id, "kind": ref.entity_kind, "created_at": observed_at})
        aliases.append(
            {
                "provider": ref.provider,
                "kind": ref.entity_kind,
                "scope": ref.scope,
                "external_id": ref.external_id,
                "entity_id": entity_id,
                "valid_from": observed_at,
                "method": "source_native",
                "evidence_manifest": manifest_hash,
            }
        )
    if entities:
        connection.execute(insert(canonical_entity), entities)
        connection.execute(insert(entity_alias), aliases)
    return resolved


def observe_affiliations(
    connection: Connection, observed: Mapping[UUID, UUID | None], at: datetime
) -> None:
    """Intervals describe observation times, not asserted real-world transfer effective times."""
    rows = (
        connection.execute(
            select(team_affiliation).where(
                team_affiliation.c.entity_id.in_(observed), team_affiliation.c.valid_to.is_(None)
            )
        )
        .mappings()
        .all()
    )
    current = {row["entity_id"]: row for row in rows}
    additions = []
    for entity_id, team_id in observed.items():
        previous = current.get(entity_id)
        if previous is not None:
            if previous["team_id"] == team_id:
                continue
            if at <= previous["valid_from"]:
                raise ValueError("AMBIGUOUS_AFFILIATION_TIME")
            connection.execute(
                update(team_affiliation)
                .where(
                    team_affiliation.c.entity_id == entity_id, team_affiliation.c.valid_to.is_(None)
                )
                .values(valid_to=at)
            )
        if team_id is not None:
            additions.append({"entity_id": entity_id, "team_id": team_id, "valid_from": at})
    if additions:
        connection.execute(insert(team_affiliation), additions)
