"""Players' positions, names and team facts for the play choreographer, from the imported nflverse
data (OWN-036, OWN-037). Reads only the private objects in data/nflverse; makes no requests.
Shared by the scripts and the API's live animation (OWN-042); `ARBIT_REPO_ROOT` names the
repository when the process doesn't run from it.

`load()` gives ESPN ID to position code: each team's depth chart snapshot taken before `before`
(an ISO time, such as a game's kickoff), with the roster filling in players the depth charts
miss. `units()` gives each team's starting center, long snapper and quarterback from the same
snapshots, and `team_colors()` the four colors nflverse lists for each team. Used by
`check_play_scripts.py`, `export_play_fixtures.py` and `scripts/sprites/render_script.py`.
"""

import json
import os
import re
from functools import cache
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from arbit_data.live.alignment import from_depth_charts, from_rosters

ROOT = Path(os.environ.get("ARBIT_REPO_ROOT", Path(__file__).resolve().parents[5]))
INVENTORY = ROOT / "docs/research/nflverse-inventory-2026-10-31.json"


@cache
def _table(name: str) -> list[dict[str, Any]]:
    files = json.loads(INVENTORY.read_text())["files"]
    entry = next(f for f in files if f["logical_key"].endswith(name))
    rows: list[dict[str, Any]] = pq.read_table(
        ROOT / "data/nflverse/objects" / entry["original_sha256"]
    ).to_pylist()
    return rows


def load(before: str | None = None) -> dict[str, tuple[str, ...]]:
    columns = ("dt", "team", "espn_id", "pos_grp", "pos_abb", "pos_rank")
    depth = [{k: row.get(k) for k in columns} for row in _table("depth_charts/depth_charts_2026")]
    found = from_rosters(_table("rosters/roster_2026"))
    found.update(from_depth_charts(depth, before))
    return found


UNITS = {"C": "center", "LS": "long_snapper", "QB": "quarterback"}


def units(before: str | None = None) -> dict[str, dict[str, tuple[str, str]]]:
    """Nflverse team abbreviation to its starting center, long snapper and quarterback, each as
    (ESPN ID, name as the play text writes it, such as "J.Sundell"), from each team's latest depth
    chart snapshot taken before `before`."""
    rows = [
        r
        for r in _table("depth_charts/depth_charts_2026")
        if r.get("espn_id")
        and r.get("pos_abb") in UNITS
        and (before is None or str(r["dt"]) < before)
    ]
    latest: dict[str, str] = {}
    for row in rows:
        latest[row["team"]] = max(latest.get(row["team"], ""), str(row["dt"]))
    best: dict[tuple[str, str], tuple[int, str, str]] = {}
    for row in rows:
        if str(row["dt"]) != latest[row["team"]]:
            continue
        key = (row["team"], UNITS[row["pos_abb"]])
        rank = int(row.get("pos_rank") or 99)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, str(row["espn_id"]), _text_name(row.get("player_name") or ""))
    found: dict[str, dict[str, tuple[str, str]]] = {}
    for (team, unit), (_, espn_id, name) in sorted(best.items()):
        found.setdefault(team, {})[unit] = (espn_id, name)
    return found


def team_colors() -> dict[str, list[str]]:
    """Nflverse team abbreviation to the colors nflverse lists for it, first to fourth."""
    return {
        row["team_abbr"]: [
            row[f"team_color{n}"] for n in ("", "2", "3", "4") if row.get(f"team_color{n}")
        ]
        for row in _table("teams/teams_colors_logos")
    }


def _text_name(full: str) -> str:
    """ "Jalen Sundell" as the play text writes him: "J.Sundell"."""
    import re

    full = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", full.strip())
    first, _, last = full.partition(" ")
    return f"{first[:1]}.{last}" if last else full


ESPN_TO_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}  # ESPN's team codes where nflverse's differ


def game_weeks(season: int = 2026) -> dict[str, int]:
    """ESPN game ID to its week, from nflverse's schedule."""
    return {
        str(g["espn"]): int(g["week"])
        for g in _table("schedules/games")
        if str(g.get("season")) == str(season) and g.get("espn")
    }


def neutral_sites() -> set[str]:
    """ESPN IDs of games nflverse's schedule places at a neutral site, such as international games."""
    return {
        str(g["espn"])
        for g in _table("schedules/games")
        if g.get("espn") and g.get("location") == "Neutral"
    }


def venues() -> dict[str, tuple[str | None, str | None, bool]]:
    """ESPN game ID to where nflverse's schedule plays it: (stadium ID, home team, neutral site)."""
    return {
        str(g["espn"]): (g.get("stadium_id"), g.get("home_team"), g.get("location") == "Neutral")
        for g in _table("schedules/games")
        if g.get("espn")
    }


def week_rosters(week: int, codes: dict[str, str]) -> dict[str, list[tuple[str | None, str, str]]]:
    """Each team's players that week, by ESPN team ID, as (ESPN player ID or None, full name,
    jersey number), from nflverse's weekly roster. `codes` maps ESPN team IDs to ESPN codes. The
    board names a foul's player by number from it (OWN-039)."""
    wanted = {ESPN_TO_NFLVERSE.get(code, code): team for team, code in codes.items()}
    found: dict[str, list[tuple[str | None, str, str]]] = {team: [] for team in codes}
    for row in _table("weekly_rosters/roster_weekly_2026"):
        team = wanted.get(row["team"])
        if (
            row["week"] == week
            and team
            and row.get("full_name")
            and row.get("jersey_number") is not None
        ):
            espn = str(row["espn_id"]) if row.get("espn_id") else None
            found[team].append((espn, row["full_name"], str(int(row["jersey_number"]))))
    return found


class GameUnits:
    """Each team's center, long snapper and quarterback through one game (OWN-037), by ESPN team
    ID for the choreographer. The quarterback is the team's last passer in the game so far, else
    its depth chart starter. Feed plays in game order: `now()` before a play, `saw()` after."""

    def __init__(
        self, units: dict[str, dict[str, tuple[str, str]]], teams: tuple[str, str, str, str]
    ):
        home, away, home_code, away_code = teams
        self.teams = {
            team: dict(units.get(ESPN_TO_NFLVERSE.get(code, code), {}))
            for team, code in ((home, home_code), (away, away_code))
        }

    def now(self) -> dict[str, dict[str, tuple[str, str]]]:
        return {team: dict(found) for team, found in self.teams.items()}

    def saw(self, facts: Any) -> None:
        import re

        passer = next((p.espn_id for p in facts.players if p.role == "passer"), None)
        if (
            passer
            and facts.offense in self.teams
            and facts.template in ("pass", "interception", "sack")
        ):
            lead = re.search(r"([A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]+) (?:pass|sacked)", facts.text)
            self.teams[facts.offense]["quarterback"] = (passer, lead.group(1) if lead else "")


@cache
def roster_names() -> dict[str, str]:
    """ESPN ID to a name in the play text's style ("S.Darnold"), from the stored 2026 roster, with
    the depth charts filling in players the roster has without an ESPN ID."""
    names = {}
    for row in _table("rosters/roster_2026"):
        if row.get("espn_id") and row.get("first_name") and row.get("last_name"):
            last = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", row["last_name"])
            names[str(row["espn_id"])] = f"{row['first_name'][0]}.{last}"
    for row in _table("depth_charts/depth_charts_2026"):
        full = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", row.get("player_name") or "")
        if row.get("espn_id") and str(row["espn_id"]) not in names and " " in full:
            first, last = full.split(" ", 1)
            names[str(row["espn_id"])] = f"{first[0]}.{last}"
    return names
