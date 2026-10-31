"""Explicit local operator commands; process settings come only from the environment."""

import argparse
import json
import os
import signal
import threading
from pathlib import Path
from typing import Any

from arbit_core.config import load_league_config
from arbit_data.archives import CaptureArchive
from arbit_data.db import UnitOfWork
from arbit_data.league_store import read_sync
from arbit_data.sync import EspnSyncSource, SyncService, schedule_sync
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def local_database_url() -> str:
    value = os.environ.get("ARBIT_DATABASE_URL", "")
    try:
        url = make_url(value)
        if (
            os.environ.get("ARBIT_ENV", "development") not in ("development", "test")
            or url.drivername != "postgresql+psycopg"
            or url.host not in ("127.0.0.1", "localhost", "::1")
            or not (url.database or "").endswith(("_local", "_test"))
        ):
            raise ValueError("LOCAL_DATABASE_REQUIRED")
    except (ValueError, SQLAlchemyError):
        raise ValueError("LOCAL_DATABASE_REQUIRED") from None
    return value


def execute(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        url = local_database_url()
        config = load_league_config(Path("config/league.json"))
    except (ValueError, OSError):
        parser.exit(2, '{"error":"LOCAL_DATABASE_REQUIRED"}\n')
    engine = create_engine(
        url, hide_parameters=True, connect_args={"connect_timeout": 3}, pool_pre_ping=True
    )
    try:
        uow = UnitOfWork(engine)
        if arguments.command == "sync-status":
            print(json.dumps(read_sync(uow, config.season), sort_keys=True))
            return
        service = SyncService(
            uow,
            CaptureArchive(Path(os.environ.get("ARBIT_STORAGE_PATH", "data/source-archives"))),
            EspnSyncSource(uow),
            interval_seconds=getattr(arguments, "interval", 300),
        )
        if arguments.command == "sync-replay":
            result = service.replay(arguments.manifest_hash)
            print(
                json.dumps(
                    {
                        "snapshot_id": str(result.snapshot_id),
                        "changed": result.changed,
                        "replayed": result.replayed,
                        "offline": True,
                    },
                    sort_keys=True,
                )
            )
            return
        if arguments.once:
            schedule_sync(uow, config.season, force=True)
            outcome = service.run_one() or {"status": "waiting_for_existing_job"}
            print(json.dumps(outcome, sort_keys=True))
            if outcome["status"] not in ("succeeded", "waiting_for_existing_job"):
                parser.exit(1)
            return
        stop = threading.Event()
        previous = {
            sig: signal.signal(sig, lambda *_: stop.set())
            for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            while not stop.is_set():
                try:
                    schedule_sync(uow, config.season)
                    watched = service.run_one()
                except SQLAlchemyError:
                    watched = {
                        "status": "database_unavailable",
                        "error_code": "DATABASE_UNAVAILABLE",
                    }
                if watched:
                    print(json.dumps(watched, sort_keys=True), flush=True)
                stop.wait(30)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    except (OSError, ValueError, SQLAlchemyError):
        parser.exit(1, '{"error":"LOCAL_SYNC_FAILED"}\n')
    finally:
        engine.dispose()


def add_commands(subcommands: Any) -> None:
    sync = subcommands.add_parser(
        "sync", help="Publish real FFA data once or run durable automatic refreshes"
    )
    mode = sync.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    sync.add_argument(
        "--interval", type=int, default=300, help="Refresh cadence in seconds (minimum 60)"
    )
    subcommands.add_parser("sync-status", help="Read persisted freshness and safe failure state")
    replay = subcommands.add_parser(
        "sync-replay", help="Replay a known private immutable capture offline"
    )
    replay.add_argument("manifest_hash")
