"""The NFL API as the primary live source (OWN-041): each NFL game linked to ESPN's event.

Plays from the NFL API are stored in `nfl_play_revision` under ESPN's play IDs, like ESPN's, so
this adds only the link from each NFL game to its ESPN event and the game's latest live summary.
"""

from alembic import op

revision = "0008_nfl_api"
down_revision = "0007_realtime"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE nfl_api_game (
        game_id text PRIMARY KEY, season integer NOT NULL, season_type text NOT NULL,
        week integer NOT NULL, event_id text, slug text, kickoff timestamptz,
        phase text, summary jsonb, summary_hash varchar(64),
        details_hash varchar(64), details_observed_at timestamptz,
        observed_at timestamptz NOT NULL
    );
    CREATE INDEX nfl_api_game_week ON nfl_api_game(season, season_type, week);
    CREATE UNIQUE INDEX nfl_api_game_event ON nfl_api_game(event_id) WHERE event_id IS NOT NULL;
    """)


def downgrade():
    op.execute("""
    DROP TABLE nfl_api_game;
    """)
