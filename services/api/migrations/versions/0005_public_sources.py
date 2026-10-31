"""Immutable supplemental observations and persistent request reservations."""

from alembic import op

revision = "0005_public_sources"
down_revision = "0004_source_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE public_source_observation (
        hash varchar(64) PRIMARY KEY, request_key text NOT NULL, kind text NOT NULL,
        observed_at timestamptz NOT NULL, payload jsonb NOT NULL
    );
    CREATE INDEX public_source_observation_key_time ON public_source_observation(request_key,observed_at);
    CREATE TABLE public_source_refresh (
        request_key text PRIMARY KEY, kind text NOT NULL,
        current_hash varchar(64) REFERENCES public_source_observation(hash),
        next_allowed_at timestamptz NOT NULL, token uuid,
        expires_at timestamptz, last_error text
    );
    """)


def downgrade():
    op.execute("DROP TABLE public_source_refresh; DROP TABLE public_source_observation;")
