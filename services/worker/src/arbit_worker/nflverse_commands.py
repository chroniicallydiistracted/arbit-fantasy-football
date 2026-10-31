"""Complete local nflverse import and integrity inspection. No provider writes or model enablement."""

import argparse
import json
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.espn.gate import DatabaseGate
from arbit_data.nflverse.catalog import Catalog
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.nflverse.repository import DatasetManifest, register_catalog
from arbit_data.nflverse.service import DatasetService, enqueue_catalog, import_status
from arbit_data.nflverse.transport import NflverseTransport, discover
from arbit_data.schema import dataset_manifest, nflverse_catalog
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from arbit_worker.sync_commands import local_database_url


def add_commands(subcommands: Any) -> None:
    catalog = subcommands.add_parser(
        "nflverse-catalog",
        help="Inspect saved catalog or explicitly discover all published source files",
    )
    catalog.add_argument("--live", action="store_true")
    ingest = subcommands.add_parser(
        "nflverse-import",
        help="Import every selected historical/current dataset in a registered catalog",
    )
    ingest.add_argument("--catalog", required=True)
    ingest.add_argument("--workers", type=int, choices=(1, 2), default=2)
    ingest.add_argument("--retry-failed", action="store_true")
    status = subcommands.add_parser(
        "nflverse-status", help="Read persisted import progress and safe gaps"
    )
    status.add_argument("--catalog", required=True)
    verify = subcommands.add_parser(
        "nflverse-verify",
        help="Verify stored source/Parquet/manifests independently of source HTTP",
    )
    scope = verify.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true")
    scope.add_argument("--manifest")


def verify_datasets(
    uow: UnitOfWork, store: ObjectStore, digest: str | None = None
) -> dict[str, Any]:
    with uow.engine.connect() as c:
        query = select(dataset_manifest.c.hash, dataset_manifest.c.payload)
        if digest:
            query = query.where(dataset_manifest.c.hash == digest)
        rows = c.execute(query).mappings().all()
    checked = set()
    table_rows = 0
    tables = 0
    for row in rows:
        manifest = DatasetManifest.model_validate(row["payload"])
        if manifest.hash != row["hash"]:
            raise ValueError("MANIFEST_CHECKSUM_MISMATCH")
        if (
            store.read(manifest.hash)
            != json.dumps(
                manifest.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ):
            raise ValueError("MANIFEST_CHECKSUM_MISMATCH")
        for ref in (manifest.raw_hash, manifest.parquet_hash):
            if ref and ref not in checked:
                store.verify(ref)
                checked.add(ref)
        if manifest.parquet_hash:
            data = pq.ParquetFile(store.path(manifest.parquet_hash))
            if data.metadata.num_rows != manifest.row_count or data.schema_arrow.names != [
                column["name"] for column in manifest.columns
            ]:
                raise ValueError("PARQUET_PROFILE_MISMATCH")
            tables += 1
            table_rows += manifest.row_count
    if digest and not rows:
        raise ValueError("UNKNOWN_MANIFEST")
    return {
        "verified": True,
        "manifests": len(rows),
        "unique_data_objects": len(checked),
        "tables": tables,
        "stored_table_rows": table_rows,
        "network_requests": 0,
    }


def _run_import(
    uow: UnitOfWork, store: ObjectStore, digest: str, workers: int, retry_failed: bool
) -> dict[str, Any]:
    from arbit_data.nflverse.repository import load_catalog

    catalog = load_catalog(digest, uow)
    enqueue_catalog(catalog, uow, retry_failed=retry_failed)
    stop = threading.Event()
    previous = {
        sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    progress = [0]
    lock = threading.Lock()

    def run() -> None:
        source = NflverseTransport(DatabaseGate(uow, provider="nflverse"))
        service = DatasetService(uow, store, source, digest)
        while not stop.is_set():
            outcome = service.run_one()
            if outcome is not None:
                with lock:
                    progress[0] += 1
                    if outcome["status"] != "published" or progress[0] % 25 == 0:
                        print(
                            json.dumps(
                                {"processed_this_run": progress[0], **outcome}, sort_keys=True
                            ),
                            flush=True,
                        )
                if outcome.get("error_code") in ("ACCESS_DENIED", "DATABASE_UNAVAILABLE"):
                    stop.set()
            else:
                status = import_status(uow, digest)
                if not status["active_work"] or status["paused"]:
                    return
                stop.wait(2)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(run) for _ in range(workers)]
            for future in futures:
                future.result()
    finally:
        stop.set()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return import_status(uow, digest)


def execute(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        url = local_database_url()
    except ValueError:
        parser.exit(2, '{"error":"LOCAL_DATABASE_REQUIRED"}\n')
    engine = create_engine(
        url, hide_parameters=True, connect_args={"connect_timeout": 3}, pool_pre_ping=True
    )
    try:
        uow = UnitOfWork(engine)
        store = ObjectStore(
            Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects"
        )
        if arguments.command == "nflverse-catalog":
            if arguments.live:
                catalog = discover(NflverseTransport(DatabaseGate(uow, provider="nflverse")))
                store.put_json(catalog.model_dump(mode="json"))
                digest = register_catalog(catalog, uow)
            else:
                with engine.connect() as c:
                    row = (
                        c.execute(
                            select(nflverse_catalog)
                            .order_by(nflverse_catalog.c.observed_at.desc())
                            .limit(1)
                        )
                        .mappings()
                        .first()
                    )
                if row is None:
                    raise ValueError("CATALOG_NOT_DISCOVERED")
                catalog = Catalog.model_validate(row["payload"])
                digest = row["hash"]
            selected = [a for a in catalog.assets if a.selected]
            print(
                json.dumps(
                    {
                        "catalog_hash": digest,
                        "physical_assets": len(catalog.assets),
                        "logical_files": len(selected),
                        "download_bytes": sum(a.size for a in selected),
                        "families": sorted({a.family for a in selected}),
                        "excluded": catalog.excluded,
                    },
                    sort_keys=True,
                )
            )
        elif arguments.command == "nflverse-import":
            status = _run_import(
                uow, store, arguments.catalog, arguments.workers, arguments.retry_failed
            )
            print(json.dumps(status, sort_keys=True))
            if status["active_work"] or status["statuses"].get("failed", 0):
                parser.exit(1)
        elif arguments.command == "nflverse-status":
            print(json.dumps(import_status(uow, arguments.catalog), sort_keys=True))
        else:
            print(json.dumps(verify_datasets(uow, store, arguments.manifest), sort_keys=True))
    except SourceError as error:
        parser.exit(
            1,
            json.dumps(
                {
                    "error": error.code,
                    "status": error.status,
                    "retry_after_seconds": error.retry_after_seconds,
                }
            )
            + "\n",
        )
    except (ValueError, OSError, SQLAlchemyError):
        parser.exit(1, '{"error":"NFLVERSE_OPERATION_FAILED"}\n')
    finally:
        engine.dispose()
