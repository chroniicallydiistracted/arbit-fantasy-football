import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from arbit_data.errors import SourceError
from arbit_data.espn.transport import SourceReceipt
from arbit_data.nflverse.objects import ObjectStore
from sqlalchemy import select

T = datetime(2026, 10, 31, tzinfo=UTC)


class Transport:
    def __init__(self):
        self.calls = 0
        self.fail = False

    def fetch(self, request):
        from arbit_data.public_sources.transport import PublicResponse

        self.calls += 1
        if self.fail:
            raise SourceError("SCHEMA_DRIFT")
        body = b'{"season":"2026"}'
        return PublicResponse(
            body,
            json.loads(body),
            SourceReceipt(request.url, T, hashlib.sha256(body).hexdigest(), len(body)),
        )


def test_eligible_source_is_cached_across_services_without_renewing_observation(uow, tmp_path):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.service import SourceService

    transport = Transport()
    store = ObjectStore(tmp_path)
    service = SourceService(uow, store, transport, clock=lambda: T)
    req = build_source_request("espn.summary", event_id="123")
    first = service.acquire(req, lambda p: p)
    second = SourceService(uow, store, transport, clock=lambda: T + timedelta(seconds=23)).acquire(
        req, lambda p: p
    )
    assert transport.calls == 1 and second.cached
    assert first.observed_at == second.observed_at == T
    assert first.hash == second.hash


def test_only_one_process_reserves_refresh(uow):
    from arbit_data.public_sources.repository import reserve
    from arbit_data.public_sources.requests import build_source_request

    req = build_source_request("espn.summary", event_id="123")

    def claim():
        try:
            return reserve(uow, req, T)
        except SourceError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(x is not None for x in results) == 1


def test_failed_refresh_preserves_last_good_and_attempt_reservation(uow, tmp_path):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.service import SourceService

    transport = Transport()
    store = ObjectStore(tmp_path)
    req = build_source_request("espn.summary", event_id="123")
    first = SourceService(uow, store, transport, clock=lambda: T).acquire(req, lambda p: p)
    transport.fail = True
    later = T + timedelta(seconds=31)
    result = SourceService(uow, store, transport, clock=lambda: later).acquire(req, lambda p: p)
    assert result.stale and result.error == "SCHEMA_DRIFT" and result.hash == first.hash
    again = SourceService(
        uow, store, transport, clock=lambda: later + timedelta(seconds=1)
    ).acquire(req, lambda p: p)
    assert again.stale and transport.calls == 2


def test_expired_reservation_cannot_publish(uow, tmp_path):
    from arbit_data.public_sources.repository import publish, reserve
    from arbit_data.public_sources.requests import build_source_request

    req = build_source_request("espn.summary", event_id="123")
    token = reserve(uow, req, T)
    with pytest.raises(SourceError, match="RESERVATION_LOST"):
        publish(
            uow,
            ObjectStore(tmp_path),
            req,
            token,
            Transport().fetch(req),
            {},
            T + timedelta(minutes=6),
        )


def test_corrupt_saved_body_is_not_served_from_cache(uow, tmp_path):
    from arbit_data.public_sources.requests import build_source_request
    from arbit_data.public_sources.service import SourceService
    from arbit_data.schema import public_source_observation

    store = ObjectStore(tmp_path)
    service = SourceService(uow, store, Transport(), clock=lambda: T)
    first = service.acquire(build_source_request("espn.summary", event_id="123"), lambda p: p)
    with uow.engine.connect() as c:
        payload = c.scalar(
            select(public_source_observation.c.payload).where(
                public_source_observation.c.hash == first.hash
            )
        )
    store.path(payload["body_hash"]).write_bytes(b"{}")
    with pytest.raises(ValueError, match="CHECKSUM"):
        service.acquire(build_source_request("espn.summary", event_id="123"), lambda p: p)
