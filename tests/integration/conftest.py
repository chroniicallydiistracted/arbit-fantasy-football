"""Real PostgreSQL per-test schemas; never drop a shared database or public tables."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture
def engine():
    url = os.environ.get(
        "ARBIT_TEST_DATABASE_URL",
        "postgresql+psycopg://arbit_local:arbit-local-dev-only@127.0.0.1:55439/arbit_test",
    )
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Integration database name must end in _test")
    schema = "test_" + uuid4().hex
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = create_engine(
        url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        yield isolated
    finally:
        isolated.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def uow(engine):
    from alembic import command
    from alembic.config import Config
    from arbit_data.db import UnitOfWork

    config = Config("alembic.ini")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return UnitOfWork(engine)


@pytest.fixture
def candidate():
    from datetime import UTC, datetime
    from uuid import UUID

    from arbit_data.contracts import LeagueSnapshotCandidate, RosterEntry

    return LeagueSnapshotCandidate(
        league_id="1729878439",
        season=2026,
        observed_at=datetime(2026, 10, 30, tzinfo=UTC),
        complete=True,
        rules_hash="a" * 64,
        manifest_hash="b" * 64,
        teams=(UUID(int=1), UUID(int=2)),
        roster=(RosterEntry(entity_id=UUID(int=3), team_id=UUID(int=1), slot="fixture-slot"),),
        available=(UUID(int=4),),
    )
