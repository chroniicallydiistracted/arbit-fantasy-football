"""Manual public-source inspection and explicitly synthetic pipeline smoke commands."""

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from arbit_core.config import load_league_config
from arbit_data.contracts import LeagueSnapshotCandidate
from arbit_data.db import UnitOfWork
from arbit_data.espn.client import EspnClient
from arbit_data.espn.reader import EspnReader
from arbit_data.espn.scoring_audit import audit_scoring
from arbit_data.espn.transport import EspnError, EspnTransport
from arbit_data.espn.verification import verify_audit
from arbit_data.snapshots import SnapshotRef, publish_snapshot
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from arbit_worker import nflverse_commands, source_commands, sync_commands
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


def _inspect_endpoints(path: Path, live: bool, parser: argparse.ArgumentParser) -> None:
    try:
        with path.open("rb") as source:
            raw = source.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Audit file exceeds size limit")
        audit = json.loads(raw)
        if not isinstance(audit, dict) or not isinstance(audit.get("requests"), list):
            raise ValueError("Invalid audit document")
        client = EspnClient(EspnTransport()) if live else None
        report = verify_audit(audit["requests"], client, live=live)
        report["auditSha256"] = hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, '{"error":"AUDIT_INVALID"}\n')
    print(json.dumps(report, sort_keys=True))
    if not report["success"]:
        parser.exit(1)


def _score_audit(periods: list[int] | None, parser: argparse.ArgumentParser) -> None:
    try:
        config = load_league_config(Path("config/league.json"))
        report = audit_scoring(
            EspnClient(EspnTransport()), config.season, None if periods is None else tuple(periods)
        )
    except (OSError, ValueError):
        parser.exit(2, '{"error":"CONFIG_INVALID"}\n')
    print(json.dumps(report, sort_keys=True))
    if not report["success"]:
        parser.exit(1)


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
    endpoint_command = subcommands.add_parser(
        "espn-endpoints", help="Report audited endpoint wiring; optionally verify every route live"
    )
    endpoint_command.add_argument("--live", action="store_true")
    endpoint_command.add_argument(
        "--audit", type=Path, default=Path("docs/research/espn-public-2026-10-30.json")
    )
    scoring_command = subcommands.add_parser(
        "espn-score-audit", help="Recompute completed FFA player and lineup scores against ESPN"
    )
    scoring_command.add_argument("--periods", nargs="+", type=_scoring_period)
    sync_commands.add_commands(subcommands)
    nflverse_commands.add_commands(subcommands)
    source_commands.add_commands(subcommands)
    arguments = parser.parse_args()
    if arguments.command in source_commands.COMMANDS:
        source_commands.execute(arguments, parser)
        return
    if arguments.command.startswith("nflverse-"):
        nflverse_commands.execute(arguments, parser)
        return
    if arguments.command in ("sync", "sync-status", "sync-replay"):
        sync_commands.execute(arguments, parser)
        return
    if arguments.command == "espn-score-audit":
        _score_audit(arguments.periods, parser)
        return
    if arguments.command == "espn-endpoints":
        _inspect_endpoints(arguments.audit, arguments.live, parser)
        return
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
