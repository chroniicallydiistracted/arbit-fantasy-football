"""Invite-only member identity, opaque sessions and bounded personal state."""

from alembic import op

revision = "0006_members"
down_revision = "0005_public_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE member_account (
        id uuid PRIMARY KEY, issuer text NOT NULL, subject text NOT NULL,
        display_name varchar(100) NOT NULL, role text NOT NULL CHECK (role IN ('member','admin')),
        suspended boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL,
        UNIQUE (issuer,subject)
    );
    CREATE TABLE member_invitation (
        hash varchar(64) PRIMARY KEY, issuer text NOT NULL, email varchar(320) NOT NULL,
        role text NOT NULL CHECK (role IN ('member','admin')), expires_at timestamptz NOT NULL,
        redeemed_at timestamptz, created_by uuid REFERENCES member_account(id)
    );
    CREATE TABLE member_session (
        hash varchar(64) PRIMARY KEY, account_id uuid NOT NULL REFERENCES member_account(id),
        created_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL,
        expires_at timestamptz NOT NULL, revoked_at timestamptz
    );
    CREATE INDEX member_session_account ON member_session(account_id);
    CREATE TABLE member_flow (
        hash varchar(64) PRIMARY KEY, browser_hash varchar(64) NOT NULL,
        nonce varchar(128) NOT NULL, verifier varchar(128) NOT NULL,
        invitation_hash varchar(64), expires_at timestamptz NOT NULL, consumed_at timestamptz
    );
    CREATE TABLE member_binding (
        account_id uuid NOT NULL REFERENCES member_account(id), season integer NOT NULL,
        manager_id uuid NOT NULL, approved_by uuid NOT NULL REFERENCES member_account(id),
        approved_at timestamptz NOT NULL, revoked_at timestamptz,
        PRIMARY KEY (account_id,season,manager_id)
    );
    CREATE UNIQUE INDEX member_binding_manager ON member_binding(season,manager_id) WHERE revoked_at IS NULL;
    CREATE TABLE member_preferences (
        account_id uuid PRIMARY KEY REFERENCES member_account(id), version integer NOT NULL DEFAULT 0,
        theme text NOT NULL DEFAULT 'system' CHECK(theme IN ('system','light','dark')),
        watchlist jsonb NOT NULL DEFAULT '[]'
    );
    CREATE TABLE member_audit (
        id bigserial PRIMARY KEY, actor_id uuid REFERENCES member_account(id),
        target_id uuid REFERENCES member_account(id), action varchar(40) NOT NULL,
        occurred_at timestamptz NOT NULL
    );
    """)


def downgrade():
    op.execute(
        "DROP TABLE member_audit,member_preferences,member_binding,member_flow,member_session,member_invitation,member_account;"
    )
