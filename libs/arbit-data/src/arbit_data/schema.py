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
    Numeric,
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
    Column("occurred_at", DateTime(timezone=True)),
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

canonical_entity = Table(
    "canonical_entity",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("kind", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
entity_alias = Table(
    "entity_alias",
    metadata,
    Column("provider", String, primary_key=True),
    Column("kind", String, primary_key=True),
    Column("scope", String, primary_key=True),
    Column("external_id", String, primary_key=True),
    Column("valid_from", DateTime(timezone=True), primary_key=True),
    Column("valid_to", DateTime(timezone=True)),
    Column("entity_id", Uuid, nullable=False),
    Column("method", String, nullable=False),
    Column("evidence_manifest", String(64), nullable=False),
)
team_affiliation = Table(
    "team_affiliation",
    metadata,
    Column("entity_id", Uuid, primary_key=True),
    Column("valid_from", DateTime(timezone=True), primary_key=True),
    Column("team_id", Uuid, nullable=False),
    Column("valid_to", DateTime(timezone=True)),
)
scoring_verification = Table(
    "scoring_verification",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("season", Integer, nullable=False),
    Column("verified_at", DateTime(timezone=True), nullable=False),
    Column("manifest_hash", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
)
rule_version = Table(
    "rule_version",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("season", Integer, nullable=False),
    Column("scoring_key", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
)
league_document = Table(
    "league_document",
    metadata,
    Column("snapshot_id", Uuid, primary_key=True),
    Column("previous_snapshot_id", Uuid),
    Column("state_hash", String(64), nullable=False),
    Column("rules_hash", String(64), nullable=False),
    Column("kind", String, nullable=False),
    Column("changes", JSON, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("published_at", DateTime(timezone=True), nullable=False),
)
source_capture = Table(
    "source_capture",
    metadata,
    Column("manifest_hash", String(64), primary_key=True),
    Column("season", Integer, nullable=False),
    Column("adapter_version", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    Column("receipts", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("snapshot_id", Uuid),
    Column("error_code", String),
)
sync_state = Table(
    "sync_state",
    metadata,
    Column("season", Integer, primary_key=True),
    Column("next_due_at", DateTime(timezone=True), nullable=False),
    Column("paused", Boolean, nullable=False),
    Column("consecutive_failures", Integer, nullable=False),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_snapshot_id", Uuid),
    Column("last_manifest_hash", String(64)),
    Column("error_code", String),
)
provider_budget = Table(
    "provider_budget",
    metadata,
    Column("provider", String, primary_key=True),
    Column("next_allowed_at", DateTime(timezone=True), nullable=False),
    Column("blocked_until", DateTime(timezone=True), nullable=False),
    Column("failures", Integer, nullable=False),
)

nflverse_catalog = Table(
    "nflverse_catalog",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
)
dataset_manifest = Table(
    "dataset_manifest",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("logical_key", String, nullable=False),
    Column("family", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("raw_hash", String(64), nullable=False),
    Column("parquet_hash", String(64)),
    Column("state_hash", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
)
dataset_current = Table(
    "dataset_current",
    metadata,
    Column("logical_key", String, primary_key=True),
    Column("manifest_hash", String(64), nullable=False),
)
dataset_import = Table(
    "dataset_import",
    metadata,
    Column("catalog_hash", String(64), primary_key=True),
    Column("logical_key", String, primary_key=True),
    Column("asset_id", String, nullable=False),
    Column("status", String, nullable=False),
    Column("manifest_hash", String(64)),
    Column("error_code", String),
    Column("checked_at", DateTime(timezone=True), nullable=False),
)
mapping_review = Table(
    "mapping_review",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("manifest_hash", String(64), nullable=False),
    Column("source_key", String, nullable=False),
    Column("reason", String, nullable=False),
    Column("payload", JSON, nullable=False),
)
identity_import = Table(
    "identity_import",
    metadata,
    Column("manifest_hash", String(64), primary_key=True),
    Column("payload", JSON, nullable=False),
)

source_revision_proof = Table(
    "source_revision_proof",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("catalog_hash", String(64), nullable=False),
    Column("verified_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
)
dataset_provenance = Table(
    "dataset_provenance",
    metadata,
    Column("manifest_hash", String(64), primary_key=True),
    Column("proof_hash", String(64), nullable=False),
    Column("verified_at", DateTime(timezone=True), nullable=False),
)
dataset_stage = Table(
    "dataset_stage",
    metadata,
    Column("catalog_hash", String(64), primary_key=True),
    Column("logical_key", String, primary_key=True),
    Column("manifest_hash", String(64), nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False),
)

public_source_observation = Table(
    "public_source_observation",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("request_key", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
)
public_source_refresh = Table(
    "public_source_refresh",
    metadata,
    Column("request_key", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("current_hash", String(64), ForeignKey("public_source_observation.hash")),
    Column("next_allowed_at", DateTime(timezone=True), nullable=False),
    Column("token", Uuid),
    Column("expires_at", DateTime(timezone=True)),
    Column("last_error", String),
)

source_health = Table(
    "source_health",
    metadata,
    Column("source", String, primary_key=True),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_change_at", DateTime(timezone=True)),
    Column("cadence_seconds", Integer),
    Column("stale_after_seconds", Integer),
    Column("consecutive_failures", Integer, nullable=False),
    Column("error_code", String),
)
nfl_team = Table(
    "nfl_team",
    metadata,
    Column("espn_id", String, primary_key=True),
    Column("entity_id", Uuid, nullable=False),
    Column("abbreviation", String, nullable=False),
    Column("location", String, nullable=False),
    Column("name", String, nullable=False),
    Column("bye_week", Integer),
    Column("observed_at", DateTime(timezone=True), nullable=False),
)
nfl_schedule_game = Table(
    "nfl_schedule_game",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("season", Integer, nullable=False),
    Column("scoring_period", Integer, nullable=False),
    Column("home_espn_id", String, nullable=False),
    Column("away_espn_id", String, nullable=False),
    Column("kickoff", DateTime(timezone=True)),
    Column("start_tbd", Boolean),
    Column("stats_official", Boolean),
    Column("observed_at", DateTime(timezone=True), nullable=False),
)
nfl_game = Table(
    "nfl_game",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("season", Integer, nullable=False),
    Column("season_type", Integer, nullable=False),
    Column("week", Integer, nullable=False),
    Column("phase", String, nullable=False),
    Column("state_hash", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("boxscore", JSON),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("changed_at", DateTime(timezone=True), nullable=False),
    Column("plays_observed_at", DateTime(timezone=True)),
    Column("plays_body_hash", String(64)),
    Column("summary_observed_at", DateTime(timezone=True)),
    Column("final_at", DateTime(timezone=True)),
    Column("final_checks", Integer, nullable=False),
)
nfl_api_game = Table(
    "nfl_api_game",
    metadata,
    Column("game_id", String, primary_key=True),
    Column("season", Integer, nullable=False),
    Column("season_type", String, nullable=False),
    Column("week", Integer, nullable=False),
    Column("event_id", String),
    Column("slug", String),
    Column("kickoff", DateTime(timezone=True)),
    Column("phase", String),
    Column("summary", JSON),
    Column("summary_hash", String(64)),
    Column("details_hash", String(64)),
    Column("details_observed_at", DateTime(timezone=True)),
    Column("observed_at", DateTime(timezone=True), nullable=False),
)
nfl_play_revision = Table(
    "nfl_play_revision",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("play_id", String, primary_key=True),
    Column("revision_hash", String(64), primary_key=True),
    Column("sequence", Numeric),
    Column("modified_at", DateTime(timezone=True)),
    Column("cancelled", Boolean, nullable=False),
    Column("first_observed_at", DateTime(timezone=True), nullable=False),
    Column("last_observed_at", DateTime(timezone=True), nullable=False),
    Column("is_current", Boolean, nullable=False),
    Column("payload", JSON, nullable=False),
)
