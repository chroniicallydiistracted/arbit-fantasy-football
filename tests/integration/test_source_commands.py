import hashlib
import json
from datetime import UTC, datetime

from arbit_data.espn.transport import SourceReceipt
from arbit_data.nflverse.objects import ObjectStore
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
        payload = (
            {"101": {"player_id": "101", "first_name": "SYNTHETIC-DO-NOT-PRINT"}}
            if request.kind == "sleeper.players"
            else {"season": "2026", "week": 8, "season_type": "regular"}
            if request.kind == "sleeper.state"
            else [{"player_id": "101", "count": 2}]
        )
        body = json.dumps(payload).encode()
        return PublicResponse(
            body,
            payload,
            SourceReceipt(request.url, T, hashlib.sha256(body).hexdigest(), len(body)),
        )


def test_documented_sync_cache_and_offline_verify_do_not_mutate_ffa(uow, tmp_path):
    from arbit_worker.source_commands import sync_sleeper, verify_sources

    source = Sources()
    store = ObjectStore(tmp_path, max_bytes=32 * 1024 * 1024)
    service = SourceService(uow, store, source, clock=lambda: T)
    first = sync_sleeper(service, uow, 2026)
    second = sync_sleeper(service, uow, 2026)
    assert first["success"] and second["success"] and source.calls == 4
    assert all(r["cached"] for r in second["resources"])
    assert "SYNTHETIC-DO-NOT-PRINT" not in json.dumps(first)
    assert verify_sources(uow, store)["observations"] == 4
    with uow.engine.connect() as c:
        assert c.scalar(select(func.count()).select_from(league_snapshot)) == 0
        assert c.scalar(select(func.count()).select_from(entity_alias)) == 0


def test_failed_resource_reports_safe_partial_result(uow, tmp_path):
    from arbit_data.errors import SourceError
    from arbit_worker.source_commands import sync_sleeper

    class Partial(Sources):
        def fetch(self, request):
            if request.kind == "sleeper.players":
                raise SourceError("UNAVAILABLE", status=503)
            return super().fetch(request)

    service = SourceService(uow, ObjectStore(tmp_path), Partial(), clock=lambda: T)
    report = sync_sleeper(service, uow, 2026)
    assert not report["success"] and report["resources"][0]["error"] == "UNAVAILABLE"
    assert len(report["resources"]) == 4
