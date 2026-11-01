"""Source health, NFL directory and live game state, and per-device member sessions."""

from alembic import op

revision = "0007_realtime"
down_revision = "0006_members"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE source_health (
        source text PRIMARY KEY,
        last_attempt_at timestamptz, last_success_at timestamptz, last_change_at timestamptz,
        cadence_seconds integer, stale_after_seconds integer,
        consecutive_failures integer NOT NULL DEFAULT 0, error_code text
    );
    CREATE TABLE nfl_team (
        espn_id text PRIMARY KEY, entity_id uuid NOT NULL UNIQUE,
        abbreviation text NOT NULL, location text NOT NULL, name text NOT NULL,
        bye_week integer, observed_at timestamptz NOT NULL
    );
    CREATE TABLE nfl_schedule_game (
        event_id text PRIMARY KEY, season integer NOT NULL, scoring_period integer NOT NULL,
        home_espn_id text NOT NULL, away_espn_id text NOT NULL, kickoff timestamptz,
        start_tbd boolean, stats_official boolean, observed_at timestamptz NOT NULL
    );
    CREATE INDEX nfl_schedule_period ON nfl_schedule_game(season, scoring_period);
    CREATE TABLE nfl_game (
        event_id text PRIMARY KEY, season integer NOT NULL, season_type integer NOT NULL,
        week integer NOT NULL, phase text NOT NULL, state_hash varchar(64) NOT NULL,
        payload jsonb NOT NULL, boxscore jsonb,
        observed_at timestamptz NOT NULL, changed_at timestamptz NOT NULL,
        plays_observed_at timestamptz, plays_body_hash varchar(64), summary_observed_at timestamptz,
        final_at timestamptz, final_checks integer NOT NULL DEFAULT 0
    );
    CREATE INDEX nfl_game_scope ON nfl_game(season, season_type, week);
    CREATE TABLE nfl_play_revision (
        event_id text NOT NULL, play_id text NOT NULL, revision_hash varchar(64) NOT NULL,
        sequence numeric, modified_at timestamptz, cancelled boolean NOT NULL,
        first_observed_at timestamptz NOT NULL, last_observed_at timestamptz NOT NULL,
        is_current boolean NOT NULL, payload jsonb NOT NULL,
        PRIMARY KEY (event_id, play_id, revision_hash)
    );
    CREATE UNIQUE INDEX nfl_play_current ON nfl_play_revision(event_id, play_id) WHERE is_current;
    CREATE INDEX nfl_play_timeline ON nfl_play_revision(event_id, sequence) WHERE is_current;
    ALTER TABLE outbox_event ADD COLUMN occurred_at timestamptz NOT NULL DEFAULT now();
    CREATE INDEX outbox_event_time ON outbox_event(occurred_at);
    ALTER TABLE member_session
        ADD COLUMN public_id uuid NOT NULL DEFAULT gen_random_uuid(),
        ADD COLUMN device_label varchar(80);
    CREATE UNIQUE INDEX member_session_public ON member_session(public_id);
    """)


def downgrade():
    op.execute("""
    DROP INDEX member_session_public;
    ALTER TABLE member_session DROP COLUMN device_label, DROP COLUMN public_id;
    DROP INDEX outbox_event_time;
    ALTER TABLE outbox_event DROP COLUMN occurred_at;
    DROP TABLE nfl_play_revision, nfl_game, nfl_schedule_game, nfl_team, source_health;
    """)
