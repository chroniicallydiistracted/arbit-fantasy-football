"""How often each changing source is read. Pure policy, driven by the observed NFL slate.

These are Arbit's targets, not provider guarantees. See docs/superpowers/plans/2026-10-31-realtime-sync.md.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Literal

Mode = Literal["active", "pregame", "idle"]

ACTIVE_PHASES = frozenset({"in_progress", "halftime", "overtime", "delayed"})
PREGAME_WINDOW = timedelta(minutes=30)
# One NFL host request per second. Scoreboard reads are 4 a minute at the fastest cadence.
NFL_REQUESTS_PER_MINUTE = 60
SCOREBOARD_REQUESTS_PER_MINUTE = 4
FASTEST_PLAY_SECONDS = 15
SUMMARY_SECONDS = 60
PLAY_STALE_SECONDS = 90
SUMMARY_STALE_SECONDS = 180
# Provider stat corrections arrive after a game ends: read again at these delays after final.
FINAL_CHECK_DELAYS = (timedelta(0), timedelta(hours=1), timedelta(hours=12))

LEAGUE_SECONDS: dict[Mode, int] = {"active": 60, "pregame": 120, "idle": 300}
SCOREBOARD_SECONDS: dict[Mode, int] = {"active": 15, "pregame": 60, "idle": 900}
DIRECTORY_SECONDS = 6 * 3600
DIRECTORY_STALE_SECONDS = 24 * 3600
STATISTICS_SECONDS = 24 * 3600
STATISTICS_STALE_SECONDS = 36 * 3600


@dataclass(frozen=True)
class GamePhase:
    phase: str
    kickoff: datetime | None


def live_mode(games: Iterable[GamePhase], now: datetime) -> Mode:
    pregame = False
    for game in games:
        if game.phase in ACTIVE_PHASES:
            return "active"
        if (
            game.phase == "scheduled"
            and game.kickoff is not None
            and game.kickoff - PREGAME_WINDOW <= now
        ):
            pregame = True
    return "pregame" if pregame else "idle"


def play_seconds(active_games: int) -> int:
    """Per-game play cadence that keeps a full slate inside the NFL host budget."""
    if active_games <= 0:
        return FASTEST_PLAY_SECONDS
    # Budget per minute: scoreboard + one summary per game + plays per game.
    available = NFL_REQUESTS_PER_MINUTE - SCOREBOARD_REQUESTS_PER_MINUTE - active_games
    if available <= 0:
        raise ValueError("ACTIVE_GAMES_EXCEED_BUDGET")
    return max(FASTEST_PLAY_SECONDS, ceil(60 * active_games / available))


def league_seconds(mode: Mode) -> int:
    return LEAGUE_SECONDS[mode]


def scoreboard_seconds(mode: Mode) -> int:
    return SCOREBOARD_SECONDS[mode]


def stale_after(cadence_seconds: int, *, floor_seconds: int) -> int:
    """A source is behind after three missed reads, never sooner than its floor."""
    return max(3 * cadence_seconds, floor_seconds)


def league_stale_seconds(mode: Mode) -> int:
    return stale_after(league_seconds(mode), floor_seconds=180)


def scoreboard_stale_seconds(mode: Mode) -> int:
    return stale_after(scoreboard_seconds(mode), floor_seconds=60)


def backoff_seconds(cadence_seconds: int, failures: int, *, ceiling_seconds: int = 900) -> int:
    """Failed reads wait longer each time, starting at the normal cadence."""
    if failures <= 0:
        return cadence_seconds
    return min(ceiling_seconds, max(cadence_seconds, cadence_seconds * (1 << min(failures, 10))))


def final_check_due(final_at: datetime, checks_done: int, now: datetime) -> bool:
    if checks_done >= len(FINAL_CHECK_DELAYS):
        return False
    return now >= final_at + FINAL_CHECK_DELAYS[checks_done]
