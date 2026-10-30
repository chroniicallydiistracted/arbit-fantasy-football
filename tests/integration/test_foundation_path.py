import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_fixture_worker_publishes_one_snapshot_and_matching_rules(uow, candidate, tmp_path):
    from arbit_data.snapshots import get_current_snapshot
    from arbit_worker.main import run_fixture

    path = tmp_path / "fixture.json"
    path.write_text(json.dumps({"synthetic": True, "snapshot": candidate.model_dump(mode="json")}))
    result = run_fixture(path, uow)
    current = get_current_snapshot(2026, uow)
    assert current.id == result.id
    assert current.candidate.rules_hash == "a" * 64
    assert current.candidate.manifest_hash == "b" * 64
    assert run_fixture(path, uow) == result
    with uow.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM outbox_event")) == 1


def test_readiness_requires_current_migration_without_exposing_database_details(engine):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    with TestClient(
        create_app(RuntimeSettings(espn_s2="fixture-private-cookie"), engine=engine)
    ) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "fixture-private-cookie" not in response.text
        assert "postgresql" not in response.text
        assert response.headers["cache-control"] == "no-store"


def test_migrated_health_ready_and_no_unprotected_league_api(uow):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    with TestClient(create_app(RuntimeSettings(), engine=uow.engine)) as client:
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.get("/api/v1/league").status_code == 404
        assert client.get("/docs").status_code == 404


def test_missing_database_has_safe_health_state():
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings

    with TestClient(create_app(RuntimeSettings(database_url=None))) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_worker_refuses_unlabeled_input(uow, candidate, tmp_path):
    from arbit_worker.main import run_fixture

    path = tmp_path / "unlabeled.json"
    path.write_text(candidate.model_dump_json())
    with pytest.raises(ValueError):
        run_fixture(path, uow)
