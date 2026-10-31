"""Manual public-source inspection and explicitly synthetic pipeline smoke commands."""

import argparse
import json
import os
from pathlib import Path
from typing import Literal

from arbit_core.config import load_league_config
from arbit_data.contracts import LeagueSnapshotCandidate
from arbit_data.db import UnitOfWork
from arbit_data.espn.reader import EspnReader
from arbit_data.espn.transport import EspnError, EspnTransport
from arbit_data.snapshots import SnapshotRef, publish_snapshot
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from arbit_worker.espn_inspect import acquisition_summary


def _scoring_period(value: str) -> int:
    try:
        period = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("scoring-period must be an integer from 1 to 99") from None
    if not 1 <= period <= 99:
        raise argparse.ArgumentTypeError("scoring-period must be an integer from 1 to 99")
    return period


def _inspect_public(period: int | None, parser: argparse.ArgumentParser) -> None:
    try:
        config = load_league_config(Path("config/league.json"))
        acquisition = EspnReader(EspnTransport()).fetch_league_snapshot(config.season, period)
        print(json.dumps(acquisition_summary(acquisition), sort_keys=True))
    except EspnError as error:
        parser.exit(
            1,
            json.dumps(
                {
                    "error": error.code,
                    "status": error.status,
                    "retryAfterSeconds": error.retry_after_seconds,
                }
            )
            + "\n",
        )
    except (OSError, ValueError):
        parser.exit(1, '{"error":"CONFIG_INVALID"}\n')


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
    inspect_command = subcommands.add_parser(
        "espn-inspect",
        help="Read current public FFA source data and print a safe acquisition summary",
    )
    inspect_command.add_argument("--scoring-period", type=_scoring_period)
    arguments = parser.parse_args()
    if arguments.command == "espn-inspect":
        _inspect_public(arguments.scoring_period, parser)
        return
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
