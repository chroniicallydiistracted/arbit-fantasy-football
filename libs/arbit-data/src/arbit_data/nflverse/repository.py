"""Atomic dataset release manifests, current pointers, import results and conservative as-of reads."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Self

from arbit_core.identity import require_aware
from pydantic import Field, model_validator
from sqlalchemy import Connection, func, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.jobs import LeasedJob, require_lease
from arbit_data.league import content_hash
from arbit_data.nflverse.catalog import Catalog
from arbit_data.nflverse.normalize import NormalizedDataset
from arbit_data.schema import (
    dataset_current,
    dataset_import,
    dataset_manifest,
    job,
    nflverse_catalog,
)


class DatasetManifest(NormalizedDataset):
    format: Literal["nflverse-dataset-v1"] = "nflverse-dataset-v1"
    adapter_version: Literal["nflverse-v1"] = "nflverse-v1"
    logical_key: str = Field(min_length=1)
    family: str = Field(min_length=1)
    observed_at: datetime
    source: dict[str, Any]

    @model_validator(mode="after")
    def valid_manifest(self) -> Self:
        require_aware(self.observed_at)
        if self.row_count < 0 or self.status == "validated" and self.parquet_hash is None:
            raise ValueError("INVALID_DATASET_MANIFEST")
        for digest in (self.raw_hash, self.parquet_hash, self.schema_hash):
            if digest is not None and (
                len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("INVALID_DATASET_MANIFEST")
        return self

    @property
    def hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))

    @property
    def state_hash(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("observed_at")
        return content_hash(payload)


def register_catalog(catalog: Catalog, uow: UnitOfWork) -> str:
    digest = content_hash(catalog.model_dump(mode="json"))
    with uow.engine.begin() as c:
        c.execute(
            insert(nflverse_catalog)
            .values(
                hash=digest,
                observed_at=catalog.observed_at,
                payload=catalog.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=[nflverse_catalog.c.hash])
        )
    return digest


def load_catalog(digest: str, uow: UnitOfWork) -> Catalog:
    with uow.engine.connect() as c:
        payload = c.scalar(
            select(nflverse_catalog.c.payload).where(nflverse_catalog.c.hash == digest)
        )
    if payload is None or content_hash(payload) != digest:
        raise ValueError("UNKNOWN_CATALOG")
    return Catalog.model_validate(payload)


def publish_dataset(
    manifest: DatasetManifest,
    uow: UnitOfWork,
    *,
    lease: LeasedJob | None = None,
    catalog_hash: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    on_publish: Callable[[Connection, str], None] | None = None,
) -> str:
    manifest = DatasetManifest.model_validate(manifest.model_dump())
    with uow.engine.begin() as c:
        if lease:
            require_lease(c, lease.id, lease.lease_token, clock())
        c.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended(manifest.logical_key, 0)))
        )
        known = c.scalar(
            select(dataset_manifest.c.hash).where(dataset_manifest.c.hash == manifest.hash)
        )
        current = (
            c.execute(
                select(dataset_manifest)
                .join(dataset_current, dataset_current.c.manifest_hash == dataset_manifest.c.hash)
                .where(dataset_current.c.logical_key == manifest.logical_key)
            )
            .mappings()
            .first()
        )
        unchanged = current is not None and current["state_hash"] == manifest.state_hash
        if known is not None:
            digest = str(known)
        elif unchanged:
            assert current is not None
            digest = str(current["hash"])
        else:
            digest = manifest.hash
        if known is None and not unchanged:
            if current is not None and manifest.observed_at <= current["observed_at"]:
                raise ValueError("STALE_DATASET_OBSERVATION")
            if (
                current is not None
                and current["payload"]["row_count"] > 0
                and manifest.row_count == 0
                and manifest.status == "validated"
            ):
                raise ValueError("UNEXPECTED_EMPTY_DATASET")
            c.execute(
                insert(dataset_manifest).values(
                    hash=digest,
                    logical_key=manifest.logical_key,
                    family=manifest.family,
                    observed_at=manifest.observed_at,
                    raw_hash=manifest.raw_hash,
                    parquet_hash=manifest.parquet_hash,
                    state_hash=manifest.state_hash,
                    payload=manifest.model_dump(mode="json"),
                )
            )
            if on_publish:
                on_publish(c, digest)
            c.execute(
                insert(dataset_current)
                .values(logical_key=manifest.logical_key, manifest_hash=digest)
                .on_conflict_do_update(
                    index_elements=[dataset_current.c.logical_key], set_={"manifest_hash": digest}
                )
            )
        if catalog_hash is not None:
            c.execute(
                update(dataset_import)
                .where(
                    dataset_import.c.catalog_hash == catalog_hash,
                    dataset_import.c.logical_key == manifest.logical_key,
                )
                .values(
                    status="unchanged" if unchanged or known else "published",
                    manifest_hash=digest,
                    error_code=None,
                    checked_at=clock(),
                )
            )
        if lease:
            require_lease(c, lease.id, lease.lease_token, clock())
            c.execute(
                update(job)
                .where(job.c.id == lease.id)
                .values(
                    status="succeeded",
                    result_ref=digest,
                    error_code=None,
                    lease_token=None,
                    lease_until=None,
                )
            )
        return str(digest)


def get_dataset(
    uow: UnitOfWork, logical_key: str, *, cutoff: datetime | None = None
) -> dict[str, Any] | None:
    if cutoff:
        require_aware(cutoff)
    with uow.engine.connect() as c:
        query = select(dataset_manifest.c.hash, dataset_manifest.c.payload).where(
            dataset_manifest.c.logical_key == logical_key
        )
        if cutoff is None:
            query = query.join(
                dataset_current, dataset_current.c.manifest_hash == dataset_manifest.c.hash
            )
        else:
            query = (
                query.where(dataset_manifest.c.observed_at <= cutoff)
                .order_by(dataset_manifest.c.observed_at.desc(), dataset_manifest.c.hash)
                .limit(1)
            )
        row = c.execute(query).mappings().first()
        return {"manifest_hash": row["hash"], **row["payload"]} if row else None
