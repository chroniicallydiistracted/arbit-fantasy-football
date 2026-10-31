"""Atomic canonical league publication, immutable history and read-only serving queries."""

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from arbit_core.identity import require_aware
from sqlalchemy import Connection, func, select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.archives import CapturedInput
from arbit_data.db import UnitOfWork
from arbit_data.espn.normalize import normalize_acquisition, rule_material, scoring_context
from arbit_data.identities import observe_affiliations
from arbit_data.jobs import LeasedJob, require_lease
from arbit_data.league import LeagueDocument
from arbit_data.schema import (
    current_snapshot,
    job,
    league_document,
    league_snapshot,
    outbox_event,
    rule_version,
    scoring_verification,
    source_capture,
    sync_state,
)
from arbit_data.snapshots import StaleSnapshotError, publish_snapshot_in_transaction


@dataclass(frozen=True)
class Publication:
    snapshot_id: UUID
    changed: bool
    replayed: bool = False


def verification_exists(uow: UnitOfWork, key: str) -> bool:
    with uow.engine.connect() as c:
        return (
            c.scalar(select(scoring_verification.c.key).where(scoring_verification.c.key == key))
            is not None
        )


def _ensure_rules(c: Connection, captured: CapturedInput, manifest: str) -> str:
    league = captured.acquisition.league
    digest, payload, key = rule_material(league)
    verified = c.scalar(select(scoring_verification.c.key).where(scoring_verification.c.key == key))
    if verified is None:
        report = captured.verification
        _, support = scoring_context(league)
        if (
            not report
            or report.get("success") is not True
            or report.get("verificationPassed") is not True
            or report.get("season") != league.season_id
            or report.get("lineupContextHash") != key
            or report.get("issues")
            or any(report.get("support", {}).get(k) != v for k, v in support.items())
        ):
            raise ValueError("SCORING_VERIFICATION_REQUIRED")
        totals = report.get("totals", {})
        if (
            not totals.get("verifiedPlayerGames", 0) > 0
            or not totals.get("lineupsMatched", 0) == totals.get("lineupsChecked", 0) > 0
        ):
            raise ValueError("SCORING_VERIFICATION_REQUIRED")
        c.execute(
            insert(scoring_verification).values(
                key=key,
                season=league.season_id,
                verified_at=captured.acquisition.capture_finished_at,
                manifest_hash=manifest,
                payload=report,
            )
        )
    c.execute(
        insert(rule_version)
        .values(hash=digest, season=league.season_id, scoring_key=key, payload=payload)
        .on_conflict_do_nothing(index_elements=[rule_version.c.hash])
    )
    return digest


def register_capture(c: Connection, captured: CapturedInput, manifest: str) -> None:
    c.execute(
        insert(source_capture)
        .values(
            manifest_hash=manifest,
            season=captured.acquisition.league.season_id,
            adapter_version=captured.adapter_version,
            observed_at=captured.acquisition.capture_started_at,
            finished_at=captured.acquisition.capture_finished_at,
            receipts=[
                {**asdict(r), "observed_at": r.observed_at.isoformat()}
                for r in captured.acquisition.receipts
            ],
            status="captured",
        )
        .on_conflict_do_nothing(index_elements=[source_capture.c.manifest_hash])
    )


def _changes(
    previous: LeagueDocument | None, current: LeagueDocument
) -> tuple[str, dict[str, Any]]:
    if previous is None:
        return "initial", {"initial": True}
    changes: dict[str, Any] = {}
    for name in ("teams", "managers", "players", "matchups", "draft_picks"):
        old = {str(getattr(x, "id", getattr(x, "overall", ""))): x for x in getattr(previous, name)}
        new = {str(getattr(x, "id", getattr(x, "overall", ""))): x for x in getattr(current, name)}
        changed = sum(old.get(key) != new.get(key) for key in old.keys() | new.keys())
        if changed:
            changes[name] = changed
    if previous.rules_hash != current.rules_hash:
        changes["rules"] = True
    if (previous.scoring_period, previous.matchup_period) != (
        current.scoring_period,
        current.matchup_period,
    ):
        changes["period"] = True
    prior = {m.id: m for m in previous.matchups}
    corrected = any(
        m.id in prior
        and prior[m.id] != m
        and max(prior[m.id].scoring_periods) < previous.scoring_period
        and max(m.scoring_periods) < current.scoring_period
        for m in current.matchups
    )
    if previous.draft_completed and previous.draft_picks != current.draft_picks:
        corrected = True
    return "correction" if corrected else "update", changes


def publish_capture(
    captured: CapturedInput,
    manifest_hash: str,
    uow: UnitOfWork,
    *,
    lease: LeasedJob | None = None,
    now: datetime | None = None,
    interval_seconds: int = 300,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Publication:
    captured = CapturedInput.model_validate(captured.model_dump())
    if hashlib.sha256(captured.model_dump_json().encode()).hexdigest() != manifest_hash:
        raise ValueError("CAPTURE_HASH_MISMATCH")
    timestamp = now or clock()
    require_aware(timestamp)
    acquisition = captured.acquisition
    season = acquisition.league.season_id
    with uow.engine.begin() as c:
        if lease:
            require_lease(c, lease.id, lease.lease_token, timestamp)
        c.execute(select(func.pg_advisory_xact_lock(1729878439, season)))
        replay = c.execute(
            select(source_capture.c.snapshot_id).where(
                source_capture.c.manifest_hash == manifest_hash
            )
        ).scalar_one_or_none()
        if replay is not None:
            if lease:
                _complete(c, lease, replay, now or clock())
            return Publication(replay, False, True)
        # A later successful no-change confirmation also fences older observations.
        last_success = c.scalar(
            select(sync_state.c.last_success_at).where(sync_state.c.season == season)
        )
        current = (
            c.execute(
                select(
                    league_snapshot.c.id,
                    league_snapshot.c.observed_at,
                    league_document.c.payload,
                    league_document.c.state_hash,
                )
                .join(current_snapshot, current_snapshot.c.snapshot_id == league_snapshot.c.id)
                .outerjoin(league_document, league_document.c.snapshot_id == league_snapshot.c.id)
                .where(current_snapshot.c.season == season)
            )
            .mappings()
            .first()
        )
        lower_bound = (
            max(
                t
                for t in (last_success, current["observed_at"] if current else None)
                if t is not None
            )
            if last_success is not None or current
            else None
        )
        if lower_bound is not None and acquisition.capture_started_at <= lower_bound:
            raise StaleSnapshotError(
                "older or ambiguous observation cannot replace a confirmed revision"
            )
        rules_hash = _ensure_rules(c, captured, manifest_hash)
        document, candidate = normalize_acquisition(c, acquisition, manifest_hash, rules_hash)
        unchanged = current is not None and current["state_hash"] == document.state_hash
        if unchanged:
            assert current is not None
            snapshot_id = current["id"]
        else:
            previous = (
                LeagueDocument.model_validate(current["payload"])
                if current and current["payload"]
                else None
            )
            kind, changes = _changes(previous, document)
            snapshot_id = publish_snapshot_in_transaction(c, candidate, now=timestamp).id
            c.execute(
                insert(league_document).values(
                    snapshot_id=snapshot_id,
                    previous_snapshot_id=current["id"] if current else None,
                    state_hash=document.state_hash,
                    rules_hash=rules_hash,
                    kind=kind,
                    changes=changes,
                    payload=document.model_dump(mode="json"),
                    published_at=timestamp,
                )
            )
            c.execute(
                update(outbox_event)
                .where(outbox_event.c.entity_id == snapshot_id)
                .values(
                    payload={
                        "snapshotId": str(snapshot_id),
                        "season": season,
                        "rulesHash": rules_hash,
                        "previousSnapshotId": str(current["id"]) if current else None,
                        "kind": kind,
                        "changes": changes,
                    }
                )
            )
            observe_affiliations(
                c, {p.id: p.nfl_team_id for p in document.players}, acquisition.capture_started_at
            )
        register_capture(c, captured, manifest_hash)
        c.execute(
            update(source_capture)
            .where(source_capture.c.manifest_hash == manifest_hash)
            .values(
                snapshot_id=snapshot_id,
                status="unchanged" if unchanged else "published",
                error_code=None,
            )
        )
        c.execute(
            insert(sync_state)
            .values(
                season=season,
                next_due_at=timestamp + timedelta(seconds=interval_seconds),
                paused=False,
                consecutive_failures=0,
                last_attempt_at=timestamp,
                last_success_at=acquisition.capture_started_at,
                last_snapshot_id=snapshot_id,
                last_manifest_hash=manifest_hash,
                error_code=None,
            )
            .on_conflict_do_update(
                index_elements=[sync_state.c.season],
                set_={
                    "next_due_at": timestamp + timedelta(seconds=interval_seconds),
                    "paused": False,
                    "consecutive_failures": 0,
                    "last_attempt_at": timestamp,
                    "last_success_at": acquisition.capture_started_at,
                    "last_snapshot_id": snapshot_id,
                    "last_manifest_hash": manifest_hash,
                    "error_code": None,
                },
            )
        )
        if lease:
            # Evaluate again at the end for real-time calls; injected time remains deterministic in tests.
            _complete(c, lease, snapshot_id, now or clock())
        return Publication(snapshot_id, not unchanged)


def _complete(c: Connection, lease: LeasedJob, snapshot_id: UUID, timestamp: datetime) -> None:
    require_lease(c, lease.id, lease.lease_token, timestamp)
    c.execute(
        update(job)
        .where(job.c.id == lease.id)
        .values(
            status="succeeded",
            result_ref=str(snapshot_id),
            error_code=None,
            lease_token=None,
            lease_until=None,
        )
    )


def _health(c: Connection, season: int, now: datetime) -> dict[str, Any]:
    row = c.execute(select(sync_state).where(sync_state.c.season == season)).mappings().first()
    if not row:
        return {"status": "never_synced", "stale": True, "recommendations_enabled": False}
    result = {
        k: v.isoformat() if isinstance(v, datetime) else str(v) if isinstance(v, UUID) else v
        for k, v in row.items()
    }
    result["stale"] = (
        row["last_success_at"] is None
        or (now - row["last_success_at"]).total_seconds() > 900
        or now < row["last_success_at"]
    )
    result["status"] = (
        "paused"
        if row["paused"]
        else "degraded"
        if row["error_code"]
        else "stale"
        if result["stale"]
        else "fresh"
    )
    result["recommendations_enabled"] = False
    return result


def read_sync(uow: UnitOfWork, season: int, *, now: datetime | None = None) -> dict[str, Any]:
    with uow.engine.connect() as c:
        return _health(c, season, now or datetime.now(UTC))


def read_current(
    uow: UnitOfWork, season: int, *, now: datetime | None = None
) -> dict[str, Any] | None:
    with uow.engine.connect() as c:
        row = c.execute(
            select(league_snapshot.c.id)
            .join(current_snapshot, current_snapshot.c.snapshot_id == league_snapshot.c.id)
            .join(league_document, league_document.c.snapshot_id == league_snapshot.c.id)
            .where(current_snapshot.c.season == season)
        ).scalar_one_or_none()
        return _read(c, row, now or datetime.now(UTC)) if row else None


def _read(c: Connection, snapshot_id: UUID, now: datetime) -> dict[str, Any] | None:
    row = (
        c.execute(
            select(
                league_snapshot.c.id,
                league_snapshot.c.season,
                league_snapshot.c.observed_at,
                league_snapshot.c.manifest_hash,
                league_document.c.state_hash,
                league_document.c.payload,
                league_document.c.kind,
                league_document.c.changes,
                league_document.c.previous_snapshot_id,
                rule_version.c.payload.label("rules"),
            )
            .join(league_document, league_document.c.snapshot_id == league_snapshot.c.id)
            .join(rule_version, rule_version.c.hash == league_document.c.rules_hash)
            .where(league_snapshot.c.id == snapshot_id)
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    return {
        "snapshot_id": str(row["id"]),
        "observed_at": row["observed_at"].isoformat(),
        "manifest_hash": row["manifest_hash"],
        "state_hash": row["state_hash"],
        "previous_snapshot_id": str(row["previous_snapshot_id"])
        if row["previous_snapshot_id"]
        else None,
        "kind": row["kind"],
        "changes": row["changes"],
        "league": row["payload"],
        "rules": row["rules"],
        "sync": _health(c, row["season"], now),
    }


def read_snapshot(uow: UnitOfWork, snapshot_id: UUID) -> dict[str, Any] | None:
    with uow.engine.connect() as c:
        return _read(c, snapshot_id, datetime.now(UTC))


def read_history(uow: UnitOfWork, season: int, limit: int = 50) -> list[dict[str, Any]]:
    if not 1 <= limit <= 100:
        raise ValueError("history limit must be 1..100")
    with uow.engine.connect() as c:
        rows = (
            c.execute(
                select(
                    league_snapshot.c.id,
                    league_snapshot.c.observed_at,
                    league_document.c.previous_snapshot_id,
                    league_document.c.kind,
                    league_document.c.changes,
                    league_document.c.state_hash,
                )
                .join(league_document, league_document.c.snapshot_id == league_snapshot.c.id)
                .where(league_snapshot.c.season == season)
                .order_by(league_snapshot.c.observed_at.desc(), league_snapshot.c.id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [
            {
                "snapshot_id": str(r["id"]),
                "observed_at": r["observed_at"].isoformat(),
                "previous_snapshot_id": str(r["previous_snapshot_id"])
                if r["previous_snapshot_id"]
                else None,
                "kind": r["kind"],
                "changes": r["changes"],
                "state_hash": r["state_hash"],
            }
            for r in rows
        ]
