"""Stage hashless files until an observed catalog bracket binds source identities."""

from alembic import op

revision = "0004_source_provenance"
down_revision = "0003_nflverse"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE dataset_import DROP CONSTRAINT dataset_import_status_check;
    ALTER TABLE dataset_import ADD CONSTRAINT dataset_import_status_check
        CHECK(status IN ('queued','staged','published','unchanged','retrying','failed'));
    CREATE TABLE dataset_stage (
        catalog_hash varchar(64) NOT NULL REFERENCES nflverse_catalog(hash), logical_key text NOT NULL,
        manifest_hash varchar(64) NOT NULL, staged_at timestamptz NOT NULL,
        PRIMARY KEY(catalog_hash,logical_key)
    );
    CREATE TABLE source_revision_proof (
        hash varchar(64) PRIMARY KEY, catalog_hash varchar(64) NOT NULL REFERENCES nflverse_catalog(hash),
        verified_at timestamptz NOT NULL, payload jsonb NOT NULL
    );
    CREATE TABLE dataset_provenance (
        manifest_hash varchar(64) PRIMARY KEY REFERENCES dataset_manifest(hash),
        proof_hash varchar(64) NOT NULL REFERENCES source_revision_proof(hash),
        verified_at timestamptz NOT NULL
    );
    """)


def downgrade():
    if op.get_bind().exec_driver_sql("SELECT 1 FROM dataset_stage LIMIT 1").first():
        raise RuntimeError(
            "Restore a backup or forward-fix before removing staged source provenance"
        )
    op.execute("""DROP TABLE dataset_provenance; DROP TABLE source_revision_proof; DROP TABLE dataset_stage;
    ALTER TABLE dataset_import DROP CONSTRAINT dataset_import_status_check;
    ALTER TABLE dataset_import ADD CONSTRAINT dataset_import_status_check
        CHECK(status IN ('queued','published','unchanged','retrying','failed'));""")
