"""Track the phase of the NFL detail that owns the published play snapshot."""

from alembic import op

revision = "0009_nfl_detail_phase"
down_revision = "0008_nfl_api"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE nfl_api_game ADD COLUMN details_phase text")


def downgrade():
    op.execute("ALTER TABLE nfl_api_game DROP COLUMN details_phase")
