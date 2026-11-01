"""Existing foundation rows survive applying the additive canonical migration."""

import pytest
from alembic import command
from alembic.config import Config
from arbit_data.db import UnitOfWork
from arbit_data.snapshots import get_current_snapshot, publish_snapshot
from sqlalchemy import text

pytestmark = pytest.mark.integration


def test_upgrade_preserves_existing_snapshots_jobs_and_outbox(engine, candidate):
    from arbit_data.jobs import JobQueue

    config = Config("alembic.ini")
    with engine.begin() as c:
        config.attributes["connection"] = c
        command.upgrade(config, "0001_foundation")
    uow = UnitOfWork(engine)
    published = publish_snapshot(candidate, uow)
    queued = JobQueue(uow).enqueue("fixture", "fixture://legacy", "legacy", candidate.observed_at)
    with engine.begin() as c:
        config.attributes["connection"] = c
        command.upgrade(config, "head")
    assert get_current_snapshot(2026, uow).id == published.id
    assert JobQueue(uow).get_job(queued.id).status == "queued"
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM outbox_event")) == 1
        assert c.scalar(text("SELECT count(*) FROM league_document")) == 0
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0007_realtime"
