"""Initial immutable snapshot, outbox and durable-job schema."""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE league_snapshot (
        id uuid PRIMARY KEY, season integer NOT NULL CHECK (season >= 2026),
        content_hash varchar(64) NOT NULL UNIQUE, rules_hash varchar(64) NOT NULL,
        manifest_hash varchar(64) NOT NULL, observed_at timestamptz NOT NULL,
        complete boolean NOT NULL CHECK (complete), payload jsonb NOT NULL
    );
    CREATE INDEX snapshot_season_observed ON league_snapshot (season, observed_at);
    CREATE TABLE current_snapshot (
        season integer PRIMARY KEY, snapshot_id uuid NOT NULL REFERENCES league_snapshot(id)
    );
    CREATE TABLE roster_entry (
        snapshot_id uuid NOT NULL REFERENCES league_snapshot(id), entity_id uuid NOT NULL,
        team_id uuid NOT NULL, slot text NOT NULL, PRIMARY KEY (snapshot_id, entity_id)
    );
    CREATE TABLE outbox_event (
        sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        event_type text NOT NULL, entity_id uuid NOT NULL UNIQUE, payload jsonb NOT NULL
    );
    CREATE TABLE job (
        id uuid PRIMARY KEY, idempotency_key text NOT NULL UNIQUE, request_hash varchar(64) NOT NULL,
        job_type text NOT NULL, input_ref text NOT NULL, status text NOT NULL,
        attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        max_attempts integer NOT NULL CHECK (max_attempts > 0), ready_at timestamptz NOT NULL,
        lease_token uuid, lease_until timestamptz, worker_id text, result_ref text, error_code text,
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
        CHECK ((status = 'running') = (lease_token IS NOT NULL AND lease_until IS NOT NULL))
    );
    CREATE INDEX job_due ON job (status, ready_at);
    """)


def downgrade():
    op.execute(
        "DROP TABLE job; DROP TABLE outbox_event; DROP TABLE roster_entry; DROP TABLE current_snapshot; DROP TABLE league_snapshot;"
    )
