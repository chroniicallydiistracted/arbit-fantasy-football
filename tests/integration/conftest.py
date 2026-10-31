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


@pytest.fixture
def captured_input():
    """Observed shape, synthetic people, explicit verification test double (never live proof)."""
    import json
    from datetime import UTC, datetime
    from decimal import Decimal
    from pathlib import Path

    from arbit_data.archives import CapturedInput
    from arbit_data.espn.contracts import EspnAcquisition, League, PoolEntry
    from arbit_data.espn.normalize import scoring_context
    from arbit_data.espn.scoring_rules import normalize_scoring
    from arbit_data.espn.transport import SourceReceipt

    raw = json.loads(
        Path("tests/fixtures/espn/league.synthetic.json").read_text(), parse_float=Decimal
    )
    raw["settings"]["scoringSettings"]["scoringItems"] = [
        i for i in raw["settings"]["scoringSettings"]["scoringItems"] if i["statId"] != 9999
    ]
    raw["members"] = [{"id": "SYNTHETIC-MANAGER", "displayName": "Synthetic manager"}]
    raw["teams"][1]["roster"]["entries"][0]["playerPoolEntry"]["player"]["stats"] = []
    league = League.model_validate(raw)
    available = PoolEntry.model_validate(
        json.loads(
            Path("tests/fixtures/espn/available.synthetic.json").read_text(), parse_float=Decimal
        )["players"][0]
    )
    t = datetime(2026, 10, 30, 12, tzinfo=UTC)
    normalized = normalize_scoring(raw["settings"]["scoringSettings"], 2026)
    report = {
        "season": 2026,
        "success": True,
        "verificationPassed": True,
        "issues": [],
        "support": {
            "configHash": normalized.config_hash,
            "athleteRulesHash": normalized.athlete_rules.content_hash,
            "defenseRulesHash": normalized.defense_rules.content_hash,
            "supported": True,
        },
        "totals": {"verifiedPlayerGames": 2, "lineupsMatched": 2, "lineupsChecked": 2},
        "synthetic": True,
        "lineupContextHash": scoring_context(league)[0],
    }
    return CapturedInput(
        acquisition=EspnAcquisition(
            league,
            (available,),
            (SourceReceipt("https://lm-api-reads.fantasy.espn.com/synthetic", t, "a" * 64, 100),),
            t,
            t,
        ),
        verification=report,
    )
