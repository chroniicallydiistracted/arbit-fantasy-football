"""Explicit synthetic pipeline smoke command; not a live ESPN scheduler."""

import argparse
import json
import os
from pathlib import Path
from typing import Literal

from arbit_data.contracts import LeagueSnapshotCandidate
from arbit_data.db import UnitOfWork
from arbit_data.snapshots import SnapshotRef, publish_snapshot
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


class SyntheticFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    synthetic: Literal[True]
    snapshot: LeagueSnapshotCandidate


def run_fixture(path: Path, unit_of_work: UnitOfWork) -> SnapshotRef:
    database_name = unit_of_work.engine.url.database or ""
    if not database_name.endswith(("_fixture", "_test")):
        raise ValueError("Synthetic publication requires a database ending in _fixture or _test")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Synthetic fixture exceeds size limit")
    fixture = SyntheticFixture.model_validate_json(path.read_bytes())
    return publish_snapshot(fixture.snapshot, unit_of_work)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    fixture_command = subcommands.add_parser(
        "fixture", help="Publish an explicitly synthetic fixture"
    )
    fixture_command.add_argument("path", type=Path)
    arguments = parser.parse_args()
    url = os.environ.get("ARBIT_DATABASE_URL")
    if not url or os.environ.get("ARBIT_ENV", "development") == "production":
        parser.exit(2, "A non-production ARBIT_DATABASE_URL is required.\n")
    engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 3})
    try:
        result = run_fixture(arguments.path, UnitOfWork(engine))
        print(
            json.dumps(
                {
                    "synthetic": True,
                    "snapshotId": str(result.id),
                    "contentHash": result.content_hash,
                }
            )
        )
    except (ValueError, OSError, SQLAlchemyError):
        parser.exit(
            1,
            "Synthetic fixture publication failed; check fixture labeling, target database and migrations.\n",
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
