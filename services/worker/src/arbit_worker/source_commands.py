"""Local supplemental/live source tools; no provider writes, member output or recommendations."""

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arbit_core.config import load_league_config
from arbit_data.assets import load_manifest, prerequisite_gaps
from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.live.contracts import LiveGame, LivePlay
from arbit_data.live.reader import LiveReader, collect_play_pages, resolve_participants
from arbit_data.live.replay import PlaySnapshot, merge_observations
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.public_sources.repository import ObservationResult, load_observation
from arbit_data.public_sources.service import SourceService
from arbit_data.public_sources.transport import PublicTransport, decode_json
from arbit_data.schema import public_source_observation, public_source_refresh
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from arbit_worker.sync_commands import local_database_url

COMMANDS = {
    "sleeper-sync",
    "sleeper-probe",
    "live-inspect",
    "sources-status",
    "sources-verify",
    "live-replay",
    "assets-check",
}


def _week(value: str) -> int:
    try:
        week = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("NFL week must be1–25") from None
    if not 1 <= week <= 25:
        raise argparse.ArgumentTypeError("NFL week must be1–25")
    return week


def _event(value: str) -> str:
    if not value.isascii() or not value.isdigit() or value.startswith("0") or len(value) > 20:
        raise argparse.ArgumentTypeError("Event ID must be positive digits")
    return value


def add_commands(subparsers: Any) -> None:
    subparsers.add_parser(
        "sleeper-sync", help="Retired: Sleeper is restricted to verified NFL live games/PBP"
    )
    probe = subparsers.add_parser(
        "sleeper-probe", help="Retired: Sleeper fantasy-stat resources are not eligible"
    )
    live = subparsers.add_parser(
        "live-inspect", help="Inspect scoped NFL scoreboard and selected game/play sources"
    )
    probe.add_argument("--season", type=int)
    probe.add_argument("--week", type=_week)
    live.add_argument("--season", type=int, required=True)
    live.add_argument("--week", type=_week, required=True)
    live.add_argument("--events", nargs="+", type=_event)
    subparsers.add_parser(
        "sources-status", help="Read stored source age and safe errors without network"
    )
    subparsers.add_parser(
        "sources-verify", help="Verify all immutable observations without network"
    )
    replay = subparsers.add_parser(
        "live-replay", help="Offline replay one complete set of observed play pages"
    )
    replay.add_argument("--observation", nargs="+", required=True)
    replay.add_argument("--previous", nargs="+")
    assets = subparsers.add_parser(
        "assets-check", help="Check curated Gridiron prerequisites without loading media"
    )
    assets.add_argument("--manifest", type=Path, default=Path("config/gridiron-assets.json"))


def _summary(kind: str, result: ObservationResult) -> dict[str, Any]:
    return {
        "kind": kind,
        "observation_hash": result.hash,
        "observed_at": result.observed_at.isoformat(),
        "cached": result.cached,
        "stale": result.stale,
        "error": result.error,
        "rows": result.payload.get("count"),
        "usage": result.payload.get("usage"),
    }


def verify_sources(uow: UnitOfWork, store: ObjectStore) -> dict[str, Any]:
    with uow.engine.connect() as c:
        refs: list[str] = list(
            c.execute(
                select(public_source_observation.c.hash).where(
                    public_source_observation.c.kind.like("espn.%")
                )
            ).scalars()
        )
    objects = set()
    plays = 0
    for ref in refs:
        manifest, normalized = load_observation(uow, store, ref)
        decode_json(store.read(manifest["body_hash"]))
        objects.update([ref, manifest["body_hash"], manifest["normalized_hash"]])
        if manifest["kind"] == "espn.plays":
            rows = [LivePlay.model_validate(p) for p in normalized["plays"]]
            if any(p.event_id != normalized["event_id"] for p in rows):
                raise ValueError("PLAY_SCOPE_MISMATCH")
            plays += len(rows)
        elif manifest["kind"] == "espn.summary":
            LiveGame.model_validate(normalized["game"])
    return {
        "verified": True,
        "observations": len(refs),
        "unique_objects": len(objects),
        "play_rows_across_observations": plays,
        "network_requests": 0,
    }


def replay_observations(uow: UnitOfWork, store: ObjectStore, refs: list[str]) -> PlaySnapshot:
    if not 1 <= len(refs) <= 20 or len(set(refs)) != len(refs):
        raise ValueError("INVALID_OBSERVATION_SET")
    loaded = [load_observation(uow, store, ref) for ref in refs]
    if any(m["kind"] != "espn.plays" for m, _ in loaded):
        raise ValueError("PLAY_OBSERVATIONS_REQUIRED")
    pages = sorted((p for _, p in loaded), key=lambda p: p["page_index"])
    event_id = pages[0]["event_id"]
    plays = collect_play_pages(pages, event_id, 2026)
    play_times: dict[str, datetime] = {}
    for manifest, page in loaded:
        at = datetime.fromisoformat(manifest["observed_at"])
        for play in page["plays"]:
            key = play["provider_id"]
            play_times[key] = max(play_times.get(key, at), at)
    return PlaySnapshot(
        event_id,
        max(datetime.fromisoformat(m["observed_at"]) for m, _ in loaded),
        plays,
        tuple(sorted(play_times.items())),
    )


def inspect_live(
    reader: LiveReader, uow: UnitOfWork, season: int, week: int, events: list[str] | None
) -> dict[str, Any]:
    board = reader.scoreboard(season, week)
    games = board.payload["games"]
    known = {g["event_id"] for g in games}
    selected = (
        events
        if events is not None
        else [g["event_id"] for g in games if g["phase"] == "final"][:2]
        + [g["event_id"] for g in games if g["phase"] == "scheduled"][:1]
    )
    if len(selected) > 8 or len(set(selected)) != len(selected) or not set(selected) <= known:
        raise ValueError("EVENTS_MUST_BELONG_TO_SCOPED_SCOREBOARD")
    rows = []
    for event in selected:
        try:
            read = reader.game(event, season)
            snapshot = read.snapshot
            participants = resolve_participants(uow, snapshot)
            rows.append(
                {
                    "event_id": event,
                    "phase": read.game.phase,
                    "home_score": read.game.home_score,
                    "away_score": read.game.away_score,
                    "manifests": list(read.manifests),
                    "play_status": read.play_status,
                    "plays": len(snapshot.plays),
                    "plays_with_participants": sum(bool(p.participants) for p in snapshot.plays),
                    "participant_ids": len(participants),
                    "canonical_participants": sum(p is not None for p in participants.values()),
                    "types": dict(Counter(p.kind for p in snapshot.plays)),
                    "effects": dict(Counter(e for p in snapshot.plays for e in p.effects)),
                    "periods": sorted({p.period for p in snapshot.plays if p.period is not None}),
                    "stale": read.stale,
                }
            )
        except (SourceError, ValueError) as error:
            rows.append(
                {
                    "event_id": event,
                    "error": error.code if isinstance(error, SourceError) else "VALIDATION_FAILED",
                }
            )
    return {
        "scoreboard": _summary("espn.scoreboard", board),
        "season": season,
        "week": week,
        "events": len(games),
        "phases": dict(Counter(g["phase"] for g in games)),
        "games": rows,
        "success": not board.stale and all(not r.get("error") and not r.get("stale") for r in rows),
        "recommendations_enabled": False,
        "limitations": [
            "Selected games only; no latency or full play-class availability guarantee.",
            "No fantasy scoring or tracking routes.",
        ],
    }


def execute(arguments: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if arguments.command in ("sleeper-sync", "sleeper-probe"):
        parser.exit(
            2,
            '{"error":"SLEEPER_LIVE_ONLY","detail":"Sleeper fantasy inputs are retired; no verified eligible live-game/PBP route is enabled."}\n',
        )
    engine = None
    try:
        if arguments.command == "assets-check":
            manifest = load_manifest(arguments.manifest)
            now = datetime.now(UTC)
            print(
                json.dumps(
                    {
                        "assets": len(manifest.assets),
                        "eligible_metadata": sum(
                            not prerequisite_gaps(a, now) for a in manifest.assets
                        ),
                        "gaps": dict(
                            Counter(g for a in manifest.assets for g in prerequisite_gaps(a, now))
                        ),
                        "media_requests": 0,
                        "local_asset_ready": False,
                        "owner_patterns_and_grants_required": True,
                    }
                )
            )
            return
        config = load_league_config(Path("config/league.json"))
        if getattr(arguments, "season", config.season) != config.season:
            raise ValueError("CONFIGURED_SEASON_REQUIRED")
        if getattr(arguments, "events", None) and len(arguments.events) > 8:
            raise ValueError("TOO_MANY_EVENTS")
        engine = create_engine(
            local_database_url(),
            hide_parameters=True,
            connect_args={"connect_timeout": 3},
            pool_pre_ping=True,
        )
        uow = UnitOfWork(engine)
        store = ObjectStore(
            Path(os.environ.get("ARBIT_PUBLIC_SOURCES_PATH", "data/public-sources")) / "objects",
            max_bytes=32 * 1024 * 1024,
        )
        if arguments.command == "sources-status":
            with engine.connect() as c:
                rows = (
                    c.execute(
                        select(
                            public_source_refresh, public_source_observation.c.observed_at
                        ).outerjoin(
                            public_source_observation,
                            public_source_refresh.c.current_hash
                            == public_source_observation.c.hash,
                        )
                    )
                    .mappings()
                    .all()
                )
            report = {
                "sources": [
                    {
                        "kind": r["kind"],
                        "observation_hash": r["current_hash"],
                        "observed_at": r["observed_at"].isoformat() if r["observed_at"] else None,
                        "next_allowed_at": r["next_allowed_at"].isoformat(),
                        "error": r["last_error"],
                    }
                    for r in rows
                ],
                "network_requests": 0,
            }
        elif arguments.command == "sources-verify":
            report = verify_sources(uow, store)
        elif arguments.command == "live-replay":
            current = replay_observations(uow, store, arguments.observation)
            previous = (
                replay_observations(uow, store, arguments.previous) if arguments.previous else None
            )
            replayed = merge_observations(previous, current)
            report = {
                "event_id": replayed.snapshot.event_id,
                "plays": len(replayed.snapshot.plays),
                "changes": dict(Counter(c["type"] for c in replayed.changes)),
                "ignored_older": replayed.ignored_older,
                "network_requests": 0,
                "recommendations_enabled": False,
                "limitations": replayed.limitations,
            }
        else:
            service = SourceService(uow, store, PublicTransport())
            report = inspect_live(
                LiveReader(service), uow, config.season, arguments.week, arguments.events
            )
        print(json.dumps(report, sort_keys=True))
        if report.get("success") is False:
            parser.exit(1)
    except (SourceError, ValueError, OSError, SQLAlchemyError) as error:
        parser.exit(
            1,
            json.dumps(
                {
                    "error": error.code
                    if isinstance(error, SourceError)
                    else "SOURCE_OPERATION_FAILED",
                    "recommendations_enabled": False,
                }
            )
            + "\n",
        )
    finally:
        if engine is not None:
            engine.dispose()
