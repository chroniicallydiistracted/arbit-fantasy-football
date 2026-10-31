"""Local operator reads require a secret and actual loopback peer; no provider requests."""

import pytest
from arbit_api.main import create_app
from arbit_api.settings import RuntimeSettings
from arbit_data.archives import CaptureArchive
from arbit_data.league_store import publish_capture
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
TOKEN = "synthetic-operator-secret-32-characters-long"


def client(uow, *, token=TOKEN, peer="127.0.0.1"):
    return TestClient(
        create_app(RuntimeSettings(operator_token=token), engine=uow.engine), client=(peer, 50100)
    )


def test_default_api_does_not_register_operator_or_member_data_routes(uow):
    with client(uow, token=None) as api:
        assert api.get("/internal/league/current").status_code == 404
        assert api.get("/api/v1/league").status_code == 404


def test_token_and_loopback_are_required_even_with_forwarded_headers(uow):
    with client(uow) as api:
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Bearer ünicode"}):
            # HTTP header values use latin1; encode the non-ASCII negative explicitly.
            if "ünicode" in headers.get("Authorization", ""):
                headers = {"Authorization": b"Bearer \xfc"}
            response = api.get("/internal/league/current", headers=headers)
            assert response.status_code == 401
            assert response.headers["cache-control"] == "no-store"
    with client(uow, peer="192.0.2.50") as api:
        response = api.get(
            "/internal/league/current",
            headers={"Authorization": "Bearer " + TOKEN, "X-Forwarded-For": "127.0.0.1"},
        )
        assert response.status_code == 403 and response.headers["cache-control"] == "no-store"


def test_current_history_snapshot_and_sync_read_only_persisted_facts(uow, tmp_path, captured_input):
    digest = CaptureArchive(tmp_path).write(captured_input)
    published = publish_capture(
        captured_input, digest, uow, now=captured_input.acquisition.capture_finished_at
    )
    with client(uow) as api:
        headers = {"Authorization": "Bearer " + TOKEN}
        response = api.get("/internal/league/current", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_id"] == str(published.snapshot_id)
        assert len(data["league"]["teams"]) == 2
        assert data["league"]["teams"][0]["points_for"] == "939.04"
        assert data["league"]["recommendations_enabled"] is False
        assert response.headers["cache-control"] == "no-store"
        history = api.get("/internal/league/history", headers=headers).json()
        assert history["revisions"][0]["snapshot_id"] == data["snapshot_id"]
        assert (
            api.get("/internal/league/snapshots/" + data["snapshot_id"], headers=headers).json()[
                "league"
            ]
            == data["league"]
        )
        assert (
            api.get("/internal/league/sync", headers=headers).json()["last_manifest_hash"] == digest
        )
        for path in ("/internal/league/history?limit=101", "/internal/league/snapshots/not-a-uuid"):
            invalid = api.get(path, headers=headers)
            assert invalid.status_code == 422 and invalid.headers["cache-control"] == "no-store"


def test_local_token_cannot_enable_remote_bind_or_production():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RuntimeSettings(operator_token=TOKEN, bind_host="0.0.0.0")
    with pytest.raises(ValidationError):
        RuntimeSettings(operator_token=TOKEN, environment="production")


def test_operator_errors_are_safe_and_no_store(uow):
    with client(uow) as api:
        headers = {"Authorization": "Bearer " + TOKEN}
        missing = api.get("/internal/league/current", headers=headers)
        assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"
    settings = RuntimeSettings(operator_token=TOKEN)
    with TestClient(create_app(settings), client=("127.0.0.1", 50000)) as api:
        unavailable = api.get(
            "/internal/league/current", headers={"Authorization": "Bearer " + TOKEN}
        )
        assert unavailable.status_code == 503
        assert unavailable.json() == {"error": "DATABASE_NOT_CONFIGURED"}
        assert unavailable.headers["cache-control"] == "no-store"


def test_nflverse_operator_coverage_route_is_protected_and_no_store(uow):
    with client(uow) as api:
        assert api.get("/internal/league/nflverse/coverage").status_code == 401
        response = api.get(
            "/internal/league/nflverse/coverage", headers={"Authorization": "Bearer " + TOKEN}
        )
        assert response.status_code == 200
        assert response.json()["families"] == {}
        assert response.json()["recommendations_enabled"] is False
        assert response.headers["cache-control"] == "no-store"
