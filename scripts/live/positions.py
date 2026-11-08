"""Players' positions and team facts for the play choreographer (OWN-036, OWN-037). Moved into the
shared library as `arbit_data.live.context` so the API's live animation uses the same data
(OWN-042); this re-exports it for the scripts."""

from arbit_data.live.context import (  # noqa: F401
    ESPN_TO_NFLVERSE,
    INVENTORY,
    ROOT,
    UNITS,
    GameUnits,
    _table,
    _text_name,
    game_weeks,
    load,
    neutral_sites,
    roster_names,
    team_colors,
    units,
    venues,
    week_rosters,
)
