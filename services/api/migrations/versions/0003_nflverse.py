"""Versioned statistical datasets, observations and evidence-backed identity reviews."""

from alembic import op

revision = "0003_nflverse"
down_revision = "0002_ffa_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE nflverse_catalog (
        hash varchar(64) PRIMARY KEY, observed_at timestamptz NOT NULL, payload jsonb NOT NULL
    );
    CREATE TABLE dataset_manifest (
        hash varchar(64) PRIMARY KEY, logical_key text NOT NULL, family text NOT NULL,
        observed_at timestamptz NOT NULL, raw_hash varchar(64) NOT NULL,
        parquet_hash varchar(64), state_hash varchar(64) NOT NULL, payload jsonb NOT NULL
    );
    CREATE INDEX dataset_key_observed ON dataset_manifest(logical_key,observed_at);
    CREATE TABLE dataset_current (
        logical_key text PRIMARY KEY, manifest_hash varchar(64) NOT NULL REFERENCES dataset_manifest(hash)
    );
    CREATE TABLE dataset_import (
        catalog_hash varchar(64) NOT NULL REFERENCES nflverse_catalog(hash), logical_key text NOT NULL,
        asset_id text NOT NULL, status text NOT NULL CHECK(status IN ('queued','published','unchanged','retrying','failed')),
        manifest_hash varchar(64) REFERENCES dataset_manifest(hash), error_code text,
        checked_at timestamptz NOT NULL, PRIMARY KEY(catalog_hash,logical_key)
    );
    CREATE TABLE mapping_review (
        id uuid PRIMARY KEY, manifest_hash varchar(64) NOT NULL REFERENCES dataset_manifest(hash),
        source_key text NOT NULL, reason text NOT NULL, payload jsonb NOT NULL,
        UNIQUE(manifest_hash,source_key)
    );
    CREATE TABLE identity_import (
        manifest_hash varchar(64) PRIMARY KEY REFERENCES dataset_manifest(hash), payload jsonb NOT NULL
    );
    ALTER TABLE entity_alias DROP CONSTRAINT entity_alias_method_check;
    ALTER TABLE entity_alias ADD CONSTRAINT entity_alias_method_check CHECK(method IN ('source_native','verified_crosswalk'));
    """)


def downgrade():
    # Do not discard verified mappings when reverting an inspection schema.
    op.execute("""
    DROP TABLE identity_import; DROP TABLE mapping_review; DROP TABLE dataset_import;
    DROP TABLE dataset_current; DROP TABLE dataset_manifest; DROP TABLE nflverse_catalog;
    """)
