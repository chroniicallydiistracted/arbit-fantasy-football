"""Eligible game sources preserve cache and offline evidence without changing FFA facts."""

import hashlib
import json
from datetime import UTC, datetime
from functools import partial

from arbit_data.espn.transport import SourceReceipt
from arbit_data.live.reader import normalize_summary
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.public_sources.requests import build_source_request
from arbit_data.public_sources.service import SourceService
from arbit_data.public_sources.transport import PublicResponse
from arbit_data.schema import entity_alias, league_snapshot
from sqlalchemy import func, select

T = datetime(2026, 10, 31, tzinfo=UTC)


class Sources:
    def __init__(self):
        self.calls = 0

    def fetch(self, request):
        self.calls += 1
        payload = {
            "header": {
                "id": "123",
                "season": {"year": 2026, "type": 2},
                "competitions": [
                    {
                        "id": "123",
                        "competitors": [
                            {"homeAway": "home", "id": "1"},
                            {"homeAway": "away", "id": "2"},
                        ],
                    }
                ],
            },
            "private_test_field": "SYNTHETIC-DO-NOT-PRINT",
        }
        body = json.dumps(payload).encode()
        return PublicResponse(
            body,
            payload,
            SourceReceipt(request.url, T, hashlib.sha256(body).hexdigest(), len(body)),
        )


def test_eligible_source_cache_and_offline_verify_do_not_mutate_ffa(uow, tmp_path):
    from arbit_worker.source_commands import verify_sources

    source = Sources()
    store = ObjectStore(tmp_path, max_bytes=32 * 1024 * 1024)
    service = SourceService(uow, store, source, clock=lambda: T)
    request = build_source_request("espn.summary", event_id="123")
    normalize = partial(normalize_summary, event_id="123", season=2026)
    first = service.acquire(request, normalize)
    second = service.acquire(request, normalize)
    assert source.calls == 1 and second.cached and first.observed_at == second.observed_at
    report = verify_sources(uow, store)
    assert report["observations"] == 1 and "SYNTHETIC-DO-NOT-PRINT" not in json.dumps(report)
    with uow.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(league_snapshot)) == 0
        assert c.scalar(select(func.count()).select_from(entity_alias)) == 0
