"""Member query definitions; additive DDL lives in migration 0006."""

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, MetaData, String, Table, Uuid

metadata = MetaData()
account = Table(
    "member_account",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("issuer", String),
    Column("subject", String),
    Column("display_name", String),
    Column("role", String),
    Column("suspended", Boolean),
    Column("created_at", DateTime(timezone=True)),
)
invitation = Table(
    "member_invitation",
    metadata,
    Column("hash", String, primary_key=True),
    Column("issuer", String),
    Column("email", String),
    Column("role", String),
    Column("expires_at", DateTime(timezone=True)),
    Column("redeemed_at", DateTime(timezone=True)),
    Column("created_by", Uuid),
)
session = Table(
    "member_session",
    metadata,
    Column("hash", String, primary_key=True),
    Column("account_id", Uuid),
    Column("created_at", DateTime(timezone=True)),
    Column("last_seen_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    Column("public_id", Uuid),
    Column("device_label", String),
)
flow = Table(
    "member_flow",
    metadata,
    Column("hash", String, primary_key=True),
    Column("browser_hash", String),
    Column("nonce", String),
    Column("verifier", String),
    Column("invitation_hash", String),
    Column("expires_at", DateTime(timezone=True)),
    Column("consumed_at", DateTime(timezone=True)),
)
binding = Table(
    "member_binding",
    metadata,
    Column("account_id", Uuid, primary_key=True),
    Column("season", Integer, primary_key=True),
    Column("manager_id", Uuid, primary_key=True),
    Column("approved_by", Uuid),
    Column("approved_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
)
preferences = Table(
    "member_preferences",
    metadata,
    Column("account_id", Uuid, primary_key=True),
    Column("version", Integer),
    Column("theme", String),
    Column("watchlist", JSON),
)
audit = Table(
    "member_audit",
    metadata,
    Column("actor_id", Uuid),
    Column("target_id", Uuid),
    Column("action", String),
    Column("occurred_at", DateTime(timezone=True)),
)
