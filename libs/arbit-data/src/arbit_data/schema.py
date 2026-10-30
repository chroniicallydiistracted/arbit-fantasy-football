"""Query definitions. Applied DDL lives in immutable Alembic migrations."""

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
)

metadata = MetaData()
league_snapshot = Table(
    "league_snapshot",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("season", Integer, nullable=False),
    Column("content_hash", String(64), nullable=False, unique=True),
    Column("rules_hash", String(64), nullable=False),
    Column("manifest_hash", String(64), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("complete", Boolean, nullable=False),
    Column("payload", JSON, nullable=False),
)
current_snapshot = Table(
    "current_snapshot",
    metadata,
    Column("season", Integer, primary_key=True),
    Column("snapshot_id", Uuid, ForeignKey("league_snapshot.id"), nullable=False),
)
roster_entry = Table(
    "roster_entry",
    metadata,
    Column("snapshot_id", Uuid, ForeignKey("league_snapshot.id"), primary_key=True),
    Column("entity_id", Uuid, primary_key=True),
    Column("team_id", Uuid, nullable=False),
    Column("slot", String, nullable=False),
)
outbox_event = Table(
    "outbox_event",
    metadata,
    Column("sequence", BigInteger, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("entity_id", Uuid, unique=True, nullable=False),
    Column("payload", JSON, nullable=False),
)
job = Table(
    "job",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("idempotency_key", String, unique=True, nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("job_type", String, nullable=False),
    Column("input_ref", String, nullable=False),
    Column("status", String, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("ready_at", DateTime(timezone=True), nullable=False),
    Column("lease_token", Uuid),
    Column("lease_until", DateTime(timezone=True)),
    Column("worker_id", String),
    Column("result_ref", String),
    Column("error_code", String),
)
