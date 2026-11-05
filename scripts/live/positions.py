"""Players' positions and team facts for the play choreographer, from the imported nflverse data
(OWN-036, OWN-037). Reads only the private objects in data/nflverse; makes no requests.

`load()` gives ESPN ID to position code: each team's depth chart snapshot taken before `before`
(an ISO time, such as a game's kickoff), with the roster filling in players the depth charts
miss. `units()` gives each team's starting center, long snapper and quarterback from the same
snapshots, and `team_colors()` the four colors nflverse lists for each team. Used by
`check_play_scripts.py`, `export_play_fixtures.py` and `scripts/sprites/render_script.py`.
"""

import json
from pathlib import Path

import pyarrow.parquet as pq
from arbit_data.live.alignment import from_depth_charts, from_rosters

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "docs/research/nflverse-inventory-2026-10-31.json"


def _table(name: str) -> list[dict]:
    files = json.loads(INVENTORY.read_text())["files"]
    entry = next(f for f in files if f["logical_key"].endswith(name))
    return pq.read_table(ROOT / "data/nflverse/objects" / entry["original_sha256"]).to_pylist()


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
        if r.get("espn_id") and r.get("pos_abb") in UNITS and (before is None or str(r["dt"]) < before)
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
        row["team_abbr"]: [row[f"team_color{n}"] for n in ("", "2", "3", "4") if row.get(f"team_color{n}")]
        for row in _table("teams/teams_colors_logos")
    }


def _text_name(full: str) -> str:
    """"Jalen Sundell" as the play text writes him: "J.Sundell"."""
    import re

    full = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", full.strip())
    first, _, last = full.partition(" ")
    return f"{first[:1]}.{last}" if last else full


ESPN_TO_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}  # ESPN's team codes where nflverse's differ


class GameUnits:
    """Each team's center, long snapper and quarterback through one game (OWN-037), by ESPN team
    ID for the choreographer. The quarterback is the team's last passer in the game so far, else
    its depth chart starter. Feed plays in game order: `now()` before a play, `saw()` after."""

    def __init__(self, units: dict[str, dict[str, tuple[str, str]]], teams: tuple[str, str, str, str]):
        home, away, home_code, away_code = teams
        self.teams = {
            team: dict(units.get(ESPN_TO_NFLVERSE.get(code, code), {}))
            for team, code in ((home, home_code), (away, away_code))
        }

    def now(self) -> dict[str, dict[str, tuple[str, str]]]:
        return {team: dict(found) for team, found in self.teams.items()}

    def saw(self, facts) -> None:
        import re

        passer = next((p.espn_id for p in facts.players if p.role == "passer"), None)
        if passer and facts.offense in self.teams and facts.template in ("pass", "interception", "sack"):
            lead = re.search(r"([A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]+) (?:pass|sacked)", facts.text)
            self.teams[facts.offense]["quarterback"] = (passer, lead.group(1) if lead else "")

