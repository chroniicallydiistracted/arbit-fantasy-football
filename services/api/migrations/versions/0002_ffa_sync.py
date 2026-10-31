"""Canonical FFA identities, immutable documents/rules/captures and durable synchronization."""

from alembic import op

revision = "0002_ffa_sync"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE canonical_entity (
        id uuid PRIMARY KEY, kind text NOT NULL CHECK (kind IN
        ('athlete','nfl_team','defense_unit','fantasy_team','manager','fantasy_matchup')),
        created_at timestamptz NOT NULL, UNIQUE(id,kind)
    );
    CREATE TABLE entity_alias (
        provider text NOT NULL, kind text NOT NULL, scope text NOT NULL, external_id text NOT NULL,
        entity_id uuid NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz,
        method text NOT NULL CHECK (method='source_native'), evidence_manifest varchar(64) NOT NULL,
        PRIMARY KEY(provider,kind,scope,external_id,valid_from),
        FOREIGN KEY(entity_id,kind) REFERENCES canonical_entity(id,kind),
        CHECK(valid_to IS NULL OR valid_to>valid_from)
    );
    CREATE UNIQUE INDEX alias_current ON entity_alias(provider,kind,scope,external_id) WHERE valid_to IS NULL;
    CREATE INDEX alias_entity ON entity_alias(entity_id);
    CREATE TABLE team_affiliation (
        entity_id uuid NOT NULL REFERENCES canonical_entity(id),
        team_id uuid NOT NULL REFERENCES canonical_entity(id),
        valid_from timestamptz NOT NULL, valid_to timestamptz,
        PRIMARY KEY(entity_id,valid_from), CHECK(valid_to IS NULL OR valid_to>valid_from)
    );
    CREATE UNIQUE INDEX affiliation_current ON team_affiliation(entity_id) WHERE valid_to IS NULL;
    CREATE TABLE scoring_verification (
        key varchar(64) PRIMARY KEY, season integer NOT NULL, verified_at timestamptz NOT NULL,
        manifest_hash varchar(64) NOT NULL, payload jsonb NOT NULL
    );
    CREATE TABLE rule_version (
        hash varchar(64) PRIMARY KEY, season integer NOT NULL,
        scoring_key varchar(64) NOT NULL REFERENCES scoring_verification(key), payload jsonb NOT NULL
    );
    CREATE TABLE league_document (
        snapshot_id uuid PRIMARY KEY REFERENCES league_snapshot(id),
        previous_snapshot_id uuid REFERENCES league_snapshot(id), state_hash varchar(64) NOT NULL,
        rules_hash varchar(64) NOT NULL REFERENCES rule_version(hash),
        kind text NOT NULL CHECK(kind IN ('initial','update','correction')),
        changes jsonb NOT NULL, payload jsonb NOT NULL, published_at timestamptz NOT NULL
    );
    CREATE TABLE source_capture (
        manifest_hash varchar(64) PRIMARY KEY, season integer NOT NULL,
        adapter_version text NOT NULL, observed_at timestamptz NOT NULL, finished_at timestamptz NOT NULL,
        receipts jsonb NOT NULL, status text NOT NULL CHECK(status IN ('captured','published','unchanged','quarantined')),
        snapshot_id uuid REFERENCES league_snapshot(id), error_code text,
        CHECK(finished_at>=observed_at)
    );
    CREATE INDEX capture_season_observed ON source_capture(season,observed_at);
    CREATE TABLE sync_state (
        season integer PRIMARY KEY, next_due_at timestamptz NOT NULL, paused boolean NOT NULL DEFAULT false,
        consecutive_failures integer NOT NULL DEFAULT 0, last_attempt_at timestamptz,
        last_success_at timestamptz, last_snapshot_id uuid REFERENCES league_snapshot(id),
        last_manifest_hash varchar(64), error_code text
    );
    CREATE UNIQUE INDEX one_active_espn_sync ON job(job_type,input_ref)
        WHERE job_type='espn.sync' AND status IN ('queued','running');
    CREATE TABLE provider_budget (
        provider text PRIMARY KEY, next_allowed_at timestamptz NOT NULL,
        blocked_until timestamptz NOT NULL, failures integer NOT NULL DEFAULT 0
    );
    """)


def downgrade():
    op.execute("""
    DROP TABLE provider_budget; DROP INDEX one_active_espn_sync; DROP TABLE sync_state;
    DROP TABLE source_capture; DROP TABLE league_document; DROP TABLE rule_version;
    DROP TABLE scoring_verification; DROP TABLE team_affiliation; DROP TABLE entity_alias;
    DROP TABLE canonical_entity;
    """)
