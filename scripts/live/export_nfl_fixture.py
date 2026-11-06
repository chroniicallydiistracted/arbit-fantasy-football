"""Write tests/fixtures/live/nfl-api-chi-at-sea.example.json from the private NFL API fetch.

CHI at SEA (2026-11-02, ESPN 401873036) as the NFL API's v2 game details gave it on 2026-11-05,
fetched with the owner's script (OWN-041). The game's identity, summary and every play record
are kept; each play's stats keep the fields the converter reads. The GSIS → ESPN player IDs for
the game's players come from nflverse's players table. The same game's ESPN plays are in
board-plays.example.json, so tests compare the two sources play by play.

Usage: uv run python scripts/live/export_nfl_fixture.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import positions as depth  # noqa: E402

SOURCE = Path(
    "data/nfl-api/2026-11-05-chi-at-sea/expanded/direct_only_results/"
    "direct_by_slug_chi_at_sea_2026_reg_8_raw.json"
)
OUT = Path("tests/fixtures/live/nfl-api-chi-at-sea.example.json")
STAT_KEYS = ("gsisPlayerId", "gsisPlayerName", "gsisPlayerJerseyNumber", "statType", "teamId", "yards")


def main() -> None:
    game = json.loads(SOURCE.read_text())
    plays = []
    for play in game["driveChart"]["plays"]:
        trimmed = {k: v for k, v in play.items() if k != "stats"}
        trimmed["stats"] = [{k: s.get(k) for k in STAT_KEYS} for s in play.get("stats") or []]
        plays.append(trimmed)
    players = {s["gsisPlayerId"] for p in plays for s in p["stats"] if s["gsisPlayerId"]}
    ids = {
        row["gsis_id"]: str(row["espn_id"])
        for row in depth._table("players/players")
        if row.get("gsis_id") in players and row.get("espn_id")
    }
    fixture = {
        "synthetic": False,
        "source": "NFL API /experience/v1/gamedetailsbyslug/bears-at-seahawks-2026-reg-8, 2026-11-05",
        "event_id": "401873036",
        "home": "26",
        "away": "3",
        "home_code": "SEA",
        "away_code": "CHI",
        "ids": dict(sorted(ids.items())),
        "game": {
            "id": game["id"],
            "homeTeam": {k: game["homeTeam"][k] for k in ("id", "currentLogo", "fullName")},
            "awayTeam": {k: game["awayTeam"][k] for k in ("id", "currentLogo", "fullName")},
            "externalIds": game["externalIds"],
            "summary": game["summary"],
            "driveChart": {"plays": plays},
        },
    }
    text = json.dumps(fixture, separators=(",", ":"))
    OUT.write_text(text.replace(',{"playId"', ',\n{"playId"') + "\n")
    print(f"wrote {OUT}: {len(plays)} plays, {len(ids)} players, {OUT.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
