"""When the availability lane reads NFL (OWN-063): twice a day, every day, on NFL time.

12:00 ET follows the 1:00 PM inactives (posted about 90 minutes before kickoff) and comes before
those games start. 19:15 ET follows the day's practice report and the 8:15/8:20 PM games'
inactives, and comes before those games start. Two fixed times cannot catch every window: the
Sunday late games' inactives (about 2:35 PM ET) and morning international games' come after one
read and before the next, so those games are projected without them.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from arbit_core.identity import require_aware

ZONE = ZoneInfo("America/New_York")
TIMES = (time(12, 0), time(19, 15))
CADENCE_SECONDS = 12 * 3600
# One missed read leaves the last one up to about 24 hours old; later than that is behind.
STALE_AFTER_SECONDS = 26 * 3600


def _slots(day: datetime) -> list[datetime]:
    return [datetime.combine(day.date(), t, tzinfo=ZONE) for t in TIMES]


def latest_slot(now: datetime) -> datetime:
    """The most recent scheduled read at or before `now`."""
    require_aware(now)
    local = now.astimezone(ZONE)
    for day in (local, local - timedelta(days=1)):
        due = [s for s in _slots(day) if s <= local]
        if due:
            return max(due)
    raise AssertionError("unreachable: yesterday always has a slot")


def next_slot(now: datetime) -> datetime:
    """The first scheduled read after `now`."""
    require_aware(now)
    local = now.astimezone(ZONE)
    for day in (local, local + timedelta(days=1)):
        later = [s for s in _slots(day) if s > local]
        if later:
            return min(later)
    raise AssertionError("unreachable: tomorrow always has a slot")
