"""Durable per-file nflverse import. Raw/Parquet objects precede atomic published manifests."""

import re
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.gate import TRANSIENT, after
from arbit_data.jobs import JobQueue, LeasedJob, LeaseLostError, maintain_lease, require_lease
from arbit_data.nflverse.catalog import Asset, Catalog
from arbit_data.nflverse.crosswalk import apply_crosswalk
from arbit_data.nflverse.normalize import normalize
from arbit_data.nflverse.objects import ObjectRef, ObjectStore
from arbit_data.nflverse.repository import (
    DatasetManifest,
    get_dataset,
    load_catalog,
    publish_dataset,
    register_catalog,
)
from arbit_data.schema import dataset_import, job, provider_budget


class Source(Protocol):
    def download(self, asset: Asset, store: ObjectStore) -> ObjectRef: ...


def enqueue_catalog(
    catalog: Catalog, uow: UnitOfWork, *, retry_failed: bool = False, now: datetime | None = None
) -> str:
    digest = register_catalog(catalog, uow)
    queue = JobQueue(uow, max_attempts=5)
    # Identity/current serving files first; every selected historic/reference file follows.
    assets = sorted(
        enumerate(catalog.assets),
        key=lambda pair: (
            0
            if pair[1].family == "players"
            else 1
            if pair[1].family in ("teams", "schedules")
            else 2
            if pair[1].family == "stats_player" and "week_2026" in pair[1].filename
            else 3,
            pair[1].logical_key,
        ),
    )
    with uow.engine.begin() as c:
        c.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended("catalog-enqueue:" + digest, 0))
            )
        )
        for index, asset in assets:
            if not asset.selected:
                continue
            input_ref = f"{digest}|{index}"
            old = (
                c.execute(
                    select(dataset_import).where(
                        dataset_import.c.catalog_hash == digest,
                        dataset_import.c.logical_key == asset.logical_key,
                    )
                )
                .mappings()
                .first()
            )
            active = c.scalar(
                select(job.c.id).where(
                    job.c.job_type == "nflverse.ingest",
                    job.c.input_ref == input_ref,
                    job.c.status.in_(("queued", "running")),
                )
            )
            if old and (old["status"] in ("published", "unchanged") or active or not retry_failed):
                continue
            key = f"nflverse:{input_ref}" + (":retry:" + uuid4().hex if old else "")
            queued_at = now or datetime.now(UTC)
            queue.enqueue_in_transaction(c, "nflverse.ingest", input_ref, key, queued_at)
            c.execute(
                insert(dataset_import)
                .values(
                    catalog_hash=digest,
                    logical_key=asset.logical_key,
                    asset_id=asset.source_id,
                    status="queued",
                    checked_at=queued_at,
                )
                .on_conflict_do_update(
                    index_elements=[dataset_import.c.catalog_hash, dataset_import.c.logical_key],
                    set_={"status": "queued", "error_code": None, "checked_at": queued_at},
                )
            )
    return digest


def import_status(uow: UnitOfWork, catalog_hash: str) -> dict[str, Any]:
    with uow.engine.connect() as c:
        rows = (
            c.execute(select(dataset_import).where(dataset_import.c.catalog_hash == catalog_hash))
            .mappings()
            .all()
        )
        active = c.scalar(
            select(job.c.id)
            .where(
                job.c.job_type == "nflverse.ingest",
                job.c.input_ref.startswith(catalog_hash + "|"),
                job.c.status.in_(("queued", "running")),
            )
            .limit(1)
        )
    statuses = [r["status"] for r in rows]
    return {
        "catalog_hash": catalog_hash,
        "files": len(rows),
        "statuses": {s: statuses.count(s) for s in sorted(set(statuses))},
        "active_work": active is not None,
        "paused": any(r["error_code"] == "ACCESS_DENIED" for r in rows),
        "errors": [
            {"logical_key": r["logical_key"], "error_code": r["error_code"]}
            for r in rows
            if r["error_code"]
        ],
        "recommendations_enabled": False,
    }


class DatasetService:
    def __init__(
        self,
        uow: UnitOfWork,
        store: ObjectStore,
        source: Source,
        catalog_hash: str,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        jitter: Callable[[], float] = lambda: secrets.randbelow(1000) / 1000,
    ):
        self.uow, self.store, self.source, self.catalog_hash = uow, store, source, catalog_hash
        self.catalog = load_catalog(catalog_hash, uow)
        self.queue = JobQueue(uow, lease_seconds=180, max_attempts=5)
        self.clock, self.jitter = clock, jitter
        self.worker = "nflverse-" + uuid4().hex

    def _asset(self, input_ref: str) -> Asset:
        prefix, index = input_ref.split("|")
        if (
            prefix != self.catalog_hash
            or not index.isascii()
            or not index.isdigit()
            or int(index) >= len(self.catalog.assets)
        ):
            raise ValueError("INVALID_JOB_INPUT")
        asset = self.catalog.assets[int(index)]
        if not asset.selected:
            raise ValueError("INVALID_JOB_INPUT")
        return asset

    def _recover(self) -> None:
        with self.uow.engine.begin() as c:
            rows = (
                c.execute(
                    select(job)
                    .where(
                        job.c.job_type == "nflverse.ingest",
                        job.c.input_ref.startswith(self.catalog_hash + "|"),
                        job.c.status == "running",
                        job.c.lease_until <= self.clock(),
                        job.c.attempts >= job.c.max_attempts,
                    )
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .all()
            )
            for row in rows:
                asset = self._asset(row["input_ref"])
                c.execute(
                    update(job)
                    .where(job.c.id == row["id"])
                    .values(
                        status="failed",
                        error_code="LEASE_EXHAUSTED",
                        lease_token=None,
                        lease_until=None,
                    )
                )
                c.execute(
                    update(dataset_import)
                    .where(
                        dataset_import.c.catalog_hash == self.catalog_hash,
                        dataset_import.c.logical_key == asset.logical_key,
                    )
                    .values(status="failed", error_code="LEASE_EXHAUSTED", checked_at=self.clock())
                )

    def _raw(self, asset: Asset) -> ObjectRef:
        if asset.provider_sha256 is not None and self.store.path(asset.provider_sha256).exists():
            ref = self.store.verify(asset.provider_sha256)
            if ref.size != asset.size:
                raise ValueError("SOURCE_SIZE_MISMATCH")
            return ref
        existing = get_dataset(self.uow, asset.logical_key)
        if existing is not None and existing["source"] == asset.model_dump(mode="json"):
            return self.store.verify(existing["raw_hash"])
        return self.source.download(asset, self.store)

    def run_one(self) -> dict[str, Any] | None:
        self._recover()
        with self.uow.engine.connect() as c:
            blocked = c.scalar(
                select(provider_budget.c.blocked_until).where(
                    provider_budget.c.provider == "nflverse"
                )
            )
            denied = c.scalar(
                select(dataset_import.c.logical_key)
                .where(
                    dataset_import.c.catalog_hash == self.catalog_hash,
                    dataset_import.c.error_code == "ACCESS_DENIED",
                )
                .limit(1)
            )
        if denied or blocked is not None and blocked > self.clock():
            return None
        lease = self.queue.claim_job(
            self.worker,
            self.clock(),
            job_type="nflverse.ingest",
            input_prefix=self.catalog_hash + "|",
        )
        if lease is None:
            return None
        asset = self._asset(lease.input_ref)
        try:
            with maintain_lease(self.queue, lease, clock=self.clock):
                raw = self._raw(asset)
                normalized = normalize(asset, raw, self.store)
                manifest = DatasetManifest(
                    **normalized.model_dump(),
                    logical_key=asset.logical_key,
                    family=asset.family,
                    observed_at=self.clock(),
                    source=asset.model_dump(mode="json"),
                )
                self.store.put_json(manifest.model_dump(mode="json"))
                directory = None
                if (
                    asset.family == "players"
                    and asset.release == "players"
                    or asset.family == "ff_playerids"
                ):
                    if normalized.parquet_hash is not None:
                        table = pq.read_table(self.store.verify(normalized.parquet_hash).path)
                        if {"gsis_id", "espn_id"} <= set(table.column_names):
                            directory = table.select(["gsis_id", "espn_id"]).to_pylist()

            def attach(c: Any, key: str) -> None:
                if directory is not None:
                    apply_crosswalk(c, directory, key, manifest.observed_at)

            key = publish_dataset(
                manifest,
                self.uow,
                lease=lease,
                catalog_hash=self.catalog_hash,
                clock=self.clock,
                on_publish=attach,
            )
            return {
                "status": "published",
                "manifest_hash": key,
                "logical_key": asset.logical_key,
                "rows": manifest.row_count,
                "archive_only": manifest.status == "archive_only",
            }
        except LeaseLostError:
            return {
                "status": "lease_lost",
                "logical_key": asset.logical_key,
                "error_code": "LEASE_LOST",
            }
        except SourceError as error:
            return self._fail(
                lease,
                asset,
                error.code,
                error.code in TRANSIENT
                or error.code in ("SOURCE_CHANGED", "SOURCE_INTEGRITY_FAILED"),
                error.retry_after_seconds,
            )
        except (ValueError, OSError) as error:
            code = (
                str(error)
                if isinstance(error, ValueError)
                and re.fullmatch("[A-Z][A-Z0-9_]{0,63}", str(error))
                else "DATASET_VALIDATION_FAILED"
            )
            return self._fail(lease, asset, code, False, None)
        except SQLAlchemyError:
            return {"status": "database_unavailable", "error_code": "DATABASE_UNAVAILABLE"}

    def _fail(
        self, lease: LeasedJob, asset: Asset, code: str, retryable: bool, retry_after: int | None
    ) -> dict[str, Any]:
        try:
            return self._record_failure(lease, asset, code, retryable, retry_after)
        except LeaseLostError:
            return {
                "status": "lease_lost",
                "logical_key": asset.logical_key,
                "error_code": "LEASE_LOST",
            }
        except SQLAlchemyError:
            return {"status": "database_unavailable", "error_code": "DATABASE_UNAVAILABLE"}

    def _record_failure(
        self, lease: LeasedJob, asset: Asset, code: str, retryable: bool, retry_after: int | None
    ) -> dict[str, Any]:
        code = code if re.fullmatch("[A-Z][A-Z0-9_]{0,63}", code) else "SOURCE_FAILED"
        with self.uow.engine.begin() as c:
            require_lease(c, lease.id, lease.lease_token, self.clock())
            row = c.execute(select(job).where(job.c.id == lease.id)).mappings().one()
            retry = retryable and row["attempts"] < row["max_attempts"]
            c.execute(
                update(job)
                .where(job.c.id == lease.id)
                .values(
                    status="queued" if retry else "failed",
                    ready_at=after(
                        self.clock(),
                        max(
                            retry_after or 0,
                            min(900, 5 * 2 ** (row["attempts"] - 1)) + 2 * self.jitter(),
                        ),
                    ),
                    error_code=code,
                    lease_token=None,
                    lease_until=None,
                )
            )
            c.execute(
                update(dataset_import)
                .where(
                    dataset_import.c.catalog_hash == self.catalog_hash,
                    dataset_import.c.logical_key == asset.logical_key,
                )
                .values(
                    status="retrying" if retry else "failed",
                    error_code=code,
                    checked_at=self.clock(),
                )
            )
        return {
            "status": "retrying" if retry else "failed",
            "logical_key": asset.logical_key,
            "error_code": code,
        }
