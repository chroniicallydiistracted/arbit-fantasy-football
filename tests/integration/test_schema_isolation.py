from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def migrate(engine):
    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def test_migration_and_readiness_never_inherit_fallback_tables(engine, candidate):
    from arbit_api.main import create_app
    from arbit_api.settings import RuntimeSettings
    from arbit_data.db import UnitOfWork
    from arbit_data.snapshots import get_current_snapshot, publish_snapshot

    with engine.begin() as connection:
        child = connection.scalar(text("SELECT current_schema()"))
        fallback = "fallback_" + uuid4().hex
        connection.execute(text(f'CREATE SCHEMA "{fallback}"'))
    parent_engine = create_engine(engine.url, connect_args={"options": f"-csearch_path={fallback}"})
    child_engine = create_engine(
        engine.url, connect_args={"options": f"-csearch_path={child},{fallback}"}
    )
    try:
        migrate(parent_engine)
        parent_ref = publish_snapshot(candidate, UnitOfWork(parent_engine))
        with TestClient(create_app(RuntimeSettings(), engine=child_engine)) as client:
            assert client.get("/health/ready").status_code == 503
        migrate(child_engine)
        assert get_current_snapshot(2026, UnitOfWork(child_engine)) is None
        child_ref = publish_snapshot(candidate, UnitOfWork(child_engine))
        assert child_ref.id != parent_ref.id
        newer = candidate.model_copy(
            update={"observed_at": candidate.observed_at + timedelta(seconds=1)}
        )
        publish_snapshot(newer, UnitOfWork(child_engine))
        assert get_current_snapshot(2026, UnitOfWork(parent_engine)).id == parent_ref.id
        with TestClient(create_app(RuntimeSettings(), engine=child_engine)) as client:
            assert client.get("/health/ready").status_code == 200
    finally:
        parent_engine.dispose()
        child_engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{fallback}" CASCADE'))
