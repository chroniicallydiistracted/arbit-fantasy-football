"""FFA league history that the current-state league document doesn't keep (R-055, R-058, R-027).

`fantasy_lineup_capture` holds one reconciled ESPN read of every team's lineup for a scoring
period. Captures are append-only: a stat correction adds a capture and the older one stays.
`fantasy_transaction` holds league transactions by ESPN's ID with canonical team and player
identities; `fantasy_transaction_read` records which scoring periods have been read.
"""

from alembic import op

revision = "0010_league_history"
down_revision = "0009_nfl_detail_phase"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE fantasy_lineup_capture (
        id uuid PRIMARY KEY, season integer NOT NULL, scoring_period integer NOT NULL,
        matchup_period integer NOT NULL, content_hash varchar(64) NOT NULL,
        receipt_sha256 varchar(64) NOT NULL, captured_at timestamptz NOT NULL,
        verification jsonb NOT NULL
    );
    CREATE INDEX fantasy_lineup_capture_period
        ON fantasy_lineup_capture(season, scoring_period, captured_at DESC);
    CREATE TABLE fantasy_lineup_entry (
        capture_id uuid NOT NULL REFERENCES fantasy_lineup_capture(id),
        player_id uuid NOT NULL, team_id uuid NOT NULL, slot text NOT NULL,
        official_points numeric, display_name text NOT NULL, position text NOT NULL,
        nfl_team_espn_id integer,
        PRIMARY KEY (capture_id, player_id)
    );
    CREATE TABLE fantasy_transaction (
        season integer NOT NULL, espn_id text NOT NULL, scoring_period integer NOT NULL,
        type text NOT NULL, status text NOT NULL, team_id uuid,
        proposed_at timestamptz, processed_at timestamptz, related_espn_id text,
        items jsonb NOT NULL, content_hash varchar(64) NOT NULL,
        first_observed_at timestamptz NOT NULL, last_changed_at timestamptz NOT NULL,
        PRIMARY KEY (season, espn_id)
    );
    CREATE INDEX fantasy_transaction_recent
        ON fantasy_transaction(season, (coalesce(processed_at, proposed_at)) DESC);
    CREATE TABLE fantasy_transaction_read (
        season integer NOT NULL, scoring_period integer NOT NULL,
        last_read_at timestamptz NOT NULL, transaction_count integer NOT NULL,
        PRIMARY KEY (season, scoring_period)
    );
    """)


def downgrade():
    op.execute("""
    DROP TABLE fantasy_transaction_read;
    DROP TABLE fantasy_transaction;
    DROP TABLE fantasy_lineup_entry;
    DROP TABLE fantasy_lineup_capture;
    """)
