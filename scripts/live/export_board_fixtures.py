"""Write tests/fixtures/live/board-plays.example.json from the private captures (slice 5).

The stadium board's state at a play depends on every play before it in the game: the score
before it and the timeouts each team has used in the half. So each case is a whole real game, in
ESPN's order, each play trimmed to the fields the normalizer and the board read. Each game also
has its teams, with the names its text uses for a team (such as "Dallas challenged"), and its
final score from the last captured scoreboard. Each play keeps the players ESPN names as
penalized, and each game both teams' rosters for its week from nflverse, with jersey numbers
(OWN-039: the board shows who committed a foul). The games were chosen for what they hold:
- CHI at SEA: touchdowns, a missed try, a two-point try, field goals, an interception, a lost
  fumble and a turnover on downs.
- ARI at DAL: overtime and a lost challenge.
- IND at JAX: an interception returned for a touchdown, and two lost challenges.

Usage: uv run python scripts/live/export_board_fixtures.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import play_facts_coverage as coverage  # noqa: E402
import positions as depth  # noqa: E402

OUT = Path("tests/fixtures/live/board-plays.example.json")
GAMES = ("401873036", "401873024", "401873028")
KEEP = (
    "id",
    "sequenceNumber",
    "text",
    "homeScore",
    "awayScore",
    "scoringPlay",
    "scoreValue",
    "isTurnover",
    "isPenalty",
    "pointAfterAttempt",
)
SPOT = ("down", "distance", "yardLine", "yardsToEndzone")
QUIET = ("scoringPlay", "scoreValue", "isTurnover", "isPenalty")


def trim(raw: dict, event: str) -> dict:
    # A false flag or a zero score value reads the same as a missing one, so they're left out.
    play = {k: raw[k] for k in KEEP if k in raw and not (k in QUIET and not raw[k])}
    play["type"] = {"text": raw.get("type", {}).get("text")}
    play["period"] = {"number": raw.get("period", {}).get("number")}
    play["clock"] = {"displayValue": raw.get("clock", {}).get("displayValue")}
    for side in ("start", "end"):
        point = raw.get(side) or {}
        trimmed = {k: point[k] for k in SPOT if k in point}
        team = point.get("team") or {}
        if "$ref" in team:  # the team's ID alone, as ESPN also sends it
            trimmed["team"] = {"id": team["$ref"].split("?")[0].rstrip("/").rsplit("/", 1)[1]}
        play[side] = trimmed
    penalized = [
        {"athlete": {"id": person["athlete"]["$ref"].split("?")[0].rsplit("/", 1)[1]}, "type": "penalized"}
        for person in raw.get("participants", [])
        if person.get("type") == "penalized" and "$ref" in person.get("athlete", {})
    ]
    if penalized:
        play["participants"] = penalized
    return play


def scoreboards(root: Path) -> dict[str, dict]:
    """Each game's competitors as the newest captured scoreboard has them."""
    found: dict[str, tuple[str, dict]] = {}
    for log in sorted(root.glob("*.jsonl")):
        for line in log.read_text().splitlines():
            entry = json.loads(line)
            if not entry["kind"].startswith("espn.scoreboard"):
                continue
            for event in coverage.load(root, entry["sha256"]).get("events", []):  # type: ignore[union-attr]
                if event["id"] not in found or entry["at"] >= found[event["id"]][0]:
                    found[event["id"]] = (entry["at"], event)
    return {event: data for event, (_at, data) in found.items()}


def main() -> None:
    root = Path("data/live-captures")
    plays, teams = coverage.captured(root)
    boards = scoreboards(root)
    weeks = depth.game_weeks()
    games = []
    for event in GAMES:
        home, away, home_code, away_code = teams[event]
        sides = {c["homeAway"]: c for c in boards[event]["competitions"][0]["competitors"]}
        status = boards[event]["competitions"][0]["status"]["type"]
        assert status.get("completed"), f"{event} isn't final in the newest capture"
        ordered = sorted(plays[event].values(), key=lambda raw: float(raw.get("sequenceNumber") or 0))
        trimmed = [trim(raw, event) for raw in ordered]
        roster = depth.week_rosters(weeks[event], {home: home_code, away: away_code})
        games.append(
            {
                "event_id": event,
                "home": home,
                "away": away,
                "home_code": home_code,
                "away_code": away_code,
                "names": {
                    side["team"]["id"]: [side["team"]["location"], side["team"]["displayName"]]
                    for side in sides.values()
                },
                "final": {"home": int(sides["home"]["score"]), "away": int(sides["away"]["score"])},
                "week": weeks[event],
                "roster": {team: [list(player) for player in sorted(players, key=lambda p: p[1])] for team, players in roster.items()},
                "plays": trimmed,
            }
        )
    text = json.dumps(
        {
            "synthetic": False,
            "source": "ESPN core API plays and scoreboard, captured 2026-11-01 to 2026-11-05",
            "games": games,
        },
        separators=(",", ":"),
    )
    # One play to a line, so a diff shows which plays changed.
    OUT.write_text(text.replace(',{"id"', ',\n{"id"') + "\n")
    print(f"wrote {OUT}: {sum(len(g['plays']) for g in games)} plays, {OUT.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
