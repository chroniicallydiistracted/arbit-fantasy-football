"""Persistent refresh reservations and immutable observations with late-worker fencing."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from arbit_core.identity import require_aware
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from arbit_data.db import UnitOfWork
from arbit_data.errors import SourceError
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.public_sources.requests import SourceRequest, validate_request
from arbit_data.public_sources.transport import PublicResponse
from arbit_data.schema import public_source_observation as observations
from arbit_data.schema import public_source_refresh as refreshes


@dataclass(frozen=True)
class Reservation:
    token: UUID
    started_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class ObservationResult:
    hash: str
    observed_at: datetime
    payload: dict[str, Any]
    cached: bool = False
    stale: bool = False
    error: str | None = None


def json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NONFINITE_VALUE")
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    return value


def reserve(uow: UnitOfWork, request: SourceRequest, now: datetime) -> Reservation:
    request = validate_request(request)
    require_aware(now)
    with uow.engine.begin() as c:
        c.execute(
            insert(refreshes)
            .values(request_key=request.key, kind=request.kind, next_allowed_at=now)
            .on_conflict_do_nothing()
        )
        row = (
            c.execute(
                select(refreshes).where(refreshes.c.request_key == request.key).with_for_update()
            )
            .mappings()
            .one()
        )
        if row["next_allowed_at"] > now:
            raise SourceError(
                "SOURCE_COOLDOWN",
                retry_after_seconds=max(1, int((row["next_allowed_at"] - now).total_seconds()) + 1),
            )
        if row["token"] is not None and row["expires_at"] > now:
            raise SourceError("PROVIDER_BUSY", retry_after_seconds=5)
        result = Reservation(uuid4(), now, now + timedelta(minutes=5))
        c.execute(
            update(refreshes)
            .where(refreshes.c.request_key == request.key)
            .values(
                token=result.token,
                expires_at=result.expires_at,
                next_allowed_at=now + timedelta(seconds=request.ttl_seconds),
            )
        )
        return result


def load_observation(
    uow: UnitOfWork, store: ObjectStore, digest: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    with uow.engine.connect() as c:
        row = (
            c.execute(select(observations).where(observations.c.hash == digest))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise ValueError("OBSERVATION_NOT_FOUND")
    manifest = json.loads(store.read(digest))
    if manifest != row["payload"]:
        raise ValueError("MANIFEST_MISMATCH")
    raw = store.read(manifest["body_hash"])
    if len(raw) != manifest["byte_count"]:
        raise ValueError("BODY_SIZE_MISMATCH")
    normalized = json.loads(store.read(manifest["normalized_hash"]))
    if not isinstance(normalized, dict):
        raise ValueError("INVALID_NORMALIZED_OBSERVATION")
    return manifest, normalized


def current(
    uow: UnitOfWork, store: ObjectStore, request: SourceRequest, now: datetime
) -> ObservationResult | None:
    require_aware(now)
    with uow.engine.connect() as c:
        row = (
            c.execute(select(refreshes).where(refreshes.c.request_key == request.key))
            .mappings()
            .one_or_none()
        )
    if row is None or row["current_hash"] is None:
        return None
    manifest, normalized = load_observation(uow, store, row["current_hash"])
    observed = datetime.fromisoformat(manifest["observed_at"])
    return ObservationResult(
        row["current_hash"],
        observed,
        normalized,
        True,
        observed > now
        or (now - observed).total_seconds() >= request.ttl_seconds
        or bool(row["last_error"]),
        row["last_error"],
    )


def fail(
    uow: UnitOfWork,
    request: SourceRequest,
    reservation: Reservation,
    error: SourceError,
    now: datetime,
) -> None:
    with uow.engine.begin() as c:
        row = (
            c.execute(
                select(refreshes)
                .where(
                    refreshes.c.request_key == request.key, refreshes.c.token == reservation.token
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            until = max(
                row["next_allowed_at"],
                now + timedelta(seconds=min(error.retry_after_seconds or 0, 31536000)),
            )
            c.execute(
                update(refreshes)
                .where(refreshes.c.request_key == request.key)
                .values(token=None, expires_at=None, last_error=error.code, next_allowed_at=until)
            )


def publish(
    uow: UnitOfWork,
    store: ObjectStore,
    request: SourceRequest,
    reservation: Reservation,
    response: PublicResponse,
    normalized: dict[str, Any],
    now: datetime,
) -> ObservationResult:
    validate_request(request)
    require_aware(now)
    require_aware(response.receipt.observed_at)
    if now >= reservation.expires_at:
        raise SourceError("RESERVATION_LOST")
    if (
        response.receipt.url != request.url
        or not reservation.started_at <= response.receipt.observed_at <= now
    ):
        raise SourceError("INVALID_RECEIPT")
    if hashlib.sha256(response.body).hexdigest() != response.receipt.sha256:
        raise SourceError("SOURCE_CHECKSUM_MISMATCH")
    original = store.write(
        (response.body,),
        expected_size=response.receipt.byte_count,
        expected_sha256=response.receipt.sha256,
    )
    derived = store.put_json(json_ready(normalized))
    payload = {
        "format": "m1e-public-v1",
        "kind": request.kind,
        "provider": request.provider,
        "request_key": request.key,
        "url": request.url,
        "usage": request.usage,
        "body_hash": original.sha256,
        "byte_count": original.size,
        "normalized_hash": derived.sha256,
        "source_observed_at": response.receipt.observed_at.isoformat(),
        "observed_at": now.isoformat(),
        "recommendations_enabled": False,
    }
    manifest = store.put_json(payload)
    with uow.engine.begin() as c:
        row = (
            c.execute(
                select(refreshes).where(refreshes.c.request_key == request.key).with_for_update()
            )
            .mappings()
            .one()
        )
        if row["token"] != reservation.token or row["expires_at"] <= now:
            raise SourceError("RESERVATION_LOST")
        c.execute(
            insert(observations)
            .values(
                hash=manifest.sha256,
                request_key=request.key,
                kind=request.kind,
                observed_at=now,
                payload=payload,
            )
            .on_conflict_do_nothing()
        )
        c.execute(
            update(refreshes)
            .where(refreshes.c.request_key == request.key)
            .values(current_hash=manifest.sha256, token=None, expires_at=None, last_error=None)
        )
    return ObservationResult(manifest.sha256, now, json.loads(store.read(derived.sha256)))
