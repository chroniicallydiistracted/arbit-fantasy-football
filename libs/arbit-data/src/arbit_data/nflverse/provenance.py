"""Stable release-identity acquisition brackets for legacy assets without provider hashes."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.league import content_hash
from arbit_data.nflverse.catalog import Catalog
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import (
    dataset_import,
    dataset_manifest,
    dataset_provenance,
    source_revision_proof,
)


def requires_proof(source: dict[str, Any]) -> bool:
    return (
        bool(source.get("source_id"))
        and not source.get("provider_sha256")
        and not source.get("git_blob_sha1")
    )


def source_signature(source: dict[str, Any]) -> str:
    return content_hash(
        {
            k: source.get(k)
            for k in (
                "source_id",
                "filename",
                "size",
                "source_updated_at",
                "source_created_at",
                "repository",
                "release",
            )
        }
    )


def confirm_catalog(
    uow: UnitOfWork, store: ObjectStore, catalog_hash: str, fresh: Catalog
) -> dict[str, Any]:
    from arbit_data.nflverse.repository import load_catalog

    original = load_catalog(catalog_hash, uow)
    if fresh.observed_at < original.observed_at:
        raise ValueError("STALE_SOURCE_PROBE")
    store.put_json(original.model_dump(mode="json"))
    after = store.put_json(fresh.model_dump(mode="json"))
    present = {(a.logical_key, a.source_id, a.filename): a for a in fresh.assets}
    verified = {}
    changed = []
    for asset in original.assets:
        if not asset.selected or not requires_proof(asset.model_dump(mode="json")):
            continue
        current = present.get((asset.logical_key, asset.source_id, asset.filename))
        expected = source_signature(asset.model_dump(mode="json"))
        if current is not None and source_signature(current.model_dump(mode="json")) == expected:
            verified[asset.logical_key] = expected
        else:
            changed.append(asset.logical_key)
    payload = {
        "before_catalog_hash": catalog_hash,
        "after_catalog_hash": after.sha256,
        "before_observed_at": original.observed_at.isoformat(),
        "after_observed_at": fresh.observed_at.isoformat(),
        "assets": verified,
        "changed": changed,
        "confirmed": len(verified),
    }
    store.put_json(payload)
    with uow.engine.begin() as c:
        c.execute(
            insert(source_revision_proof)
            .values(
                hash=content_hash(payload),
                catalog_hash=catalog_hash,
                verified_at=fresh.observed_at,
                payload=payload,
            )
            .on_conflict_do_nothing(index_elements=[source_revision_proof.c.hash])
        )
        proof = (
            c.execute(
                select(source_revision_proof).where(
                    source_revision_proof.c.hash == content_hash(payload)
                )
            )
            .mappings()
            .one()
        )
        # Also attest pre-review imported objects, retaining their original immutable manifests.
        rows = (
            c.execute(
                select(dataset_manifest.c.hash, dataset_manifest.c.payload)
                .join(dataset_import, dataset_import.c.manifest_hash == dataset_manifest.c.hash)
                .where(dataset_import.c.catalog_hash == catalog_hash)
            )
            .mappings()
            .all()
        )
        for row in rows:
            m = row["payload"]
            if requires_proof(m["source"]) and proof["payload"]["assets"].get(
                m["logical_key"]
            ) == source_signature(m["source"]):
                c.execute(
                    insert(dataset_provenance)
                    .values(
                        manifest_hash=row["hash"],
                        proof_hash=proof["hash"],
                        verified_at=proof["verified_at"],
                    )
                    .on_conflict_do_nothing(index_elements=[dataset_provenance.c.manifest_hash])
                )
    return payload
