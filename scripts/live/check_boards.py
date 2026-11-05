"""Check the stadium board's state against ESPN's own scoreboard, over every captured game (slice 5).

The board is built from the plays alone (`arbit_data.live.board`). ESPN's scoreboard is a
separate source: each captured read gives the score and, while a game is on, its `situation`
after the last play, with the down, distance, possession and each team's timeouts left. So:
- each finished game's last board must show the scoreboard's final score;
- where a captured scoreboard names the play just finished, the board after that play must
  show the same score, timeouts, down, distance and possession;
- scores never go down within a game, and timeouts stay from 0 to 3.
A board value that is unknown is counted, not compared. Reads only private data in data/.

Usage: uv run python scripts/live/check_boards.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/live"))
import play_facts_coverage as coverage  # noqa: E402
import positions as depth  # noqa: E402
from arbit_data.live.board import BoardState, GameBoard  # noqa: E402
from arbit_data.live.normalize import normalize_play  # noqa: E402
from arbit_data.live.play_facts import GameTeams, interpret, text_codes  # noqa: E402

CAPTURES = ROOT / "data/live-captures"
ENDS = ("End Period", "End of Half", "End of Game", "End of Regulation")


def snapshots() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Every captured scoreboard read of each game, oldest first, and the newest one."""
    reads: dict[str, list[tuple[str, dict]]] = {}
    for log in sorted(CAPTURES.glob("*.jsonl")):
        for line in log.read_text().splitlines():
            entry = json.loads(line)
            if entry["kind"].startswith("espn.scoreboard"):
                for event in coverage.load(CAPTURES, entry["sha256"]).get("events", []):  # type: ignore[union-attr]
                    reads.setdefault(event["id"], []).append((entry["at"], event))
    ordered = {event: [data for _at, data in sorted(items, key=lambda item: item[0])] for event, items in reads.items()}
    return ordered, {event: items[-1] for event, items in ordered.items()}


def main() -> None:
    plays, teams = coverage.captured(CAPTURES)
    reads, newest = snapshots()
    weeks = depth.game_weeks()
    fouls: Counter = Counter()
    found: Counter = Counter()
    examples: dict[str, str] = {}
    compared: Counter = Counter()
    unknown: Counter = Counter()

    def flag(kind: str, detail: str) -> None:
        found[kind] += 1
        examples.setdefault(kind, detail)
        if "--all" in sys.argv:
            print(kind, detail)

    espn_differs: Counter = Counter()

    def compare(kind: str, ours: object, espn: object, where: str, espn_end: object) -> None:
        """`espn_end` is what ESPN's own record of the play says, where the board copies it."""
        if ours is None or (isinstance(ours, tuple) and None in ours):
            unknown[kind] += 1
            return
        compared[kind] += 1
        if ours == espn:
            return
        if isinstance(espn_end, list):  # board states one play away
            if espn in espn_end:
                espn_differs[f"{kind} one play out of step"] += 1
                return
        elif espn_end is not None and espn_end != espn:
            espn_differs[kind] += 1  # ESPN's play and its scoreboard disagree, as when it re-spots the ball
            return
        flag(f"{kind} differs from ESPN's scoreboard", f"{where}: board {ours}, ESPN {espn}")

    for event, items in sorted(plays.items()):
        home, away, home_code, away_code = teams[event]
        competition = newest[event]["competitions"][0]
        names = {
            c["team"]["id"]: [c["team"]["location"], c["team"]["displayName"]] for c in competition["competitors"]
        }
        normalized = sorted((normalize_play(raw, event, 2026) for raw in items.values()), key=lambda p: int(p.sequence or 0))
        context = GameTeams.build(home, away, home_code, away_code, seen=text_codes(p.text for p in normalized))
        roster = depth.week_rosters(weeks[event], {home: home_code, away: away_code})
        board = GameBoard(context, home_code, away_code, names, roster)
        afters: dict[str, list[BoardState]] = {}  # by ESPN play ID: after the play, then after its try
        by_id = {play.provider_id: play for play in normalized}
        nearby: dict[str, list[BoardState]] = {}  # one play away: the score before it, and after the next
        order: list[str] = []
        previous = (0, 0)
        final: BoardState | None = None
        for play in normalized:
            facts = interpret(play, context)
            made = board.boards(play, facts)
            for part in made:
                for state in (part.before, part.after):
                    now = (state.away.score, state.home.score)
                    if None in now:
                        unknown["score"] += 1
                    else:
                        if now[0] < previous[0] or now[1] < previous[1]:  # type: ignore[operator]
                            flag("score went down", f"{event} {play.text[:80]}")
                        previous = now  # type: ignore[assignment]
                    for left in (state.away.timeouts, state.home.timeouts):
                        if left is None:
                            unknown["timeouts"] += 1
                        elif not 0 <= left <= 3:
                            flag("timeouts out of range", f"{event} {play.text[:80]}")
            afters[play.provider_id] = [part.after for part in made]
            cards = [r for part in made for r in part.results if r.kind == "penalty"]
            for card, penalty in zip(cards, facts.penalties, strict=True):
                if card.jersey:
                    fouls["numbered"] += 1
                elif penalty.player:
                    fouls["player not on his team's roster that week"] += 1
                    examples.setdefault("unnumbered", f"{penalty.player} ({card.team_id}) in {event}")
                else:
                    fouls["team foul, no player"] += 1
            nearby[play.provider_id] = [made[0].before]
            if order:
                nearby[order[-1]] += [part.after for part in made]  # the next play's score
            order.append(play.provider_id)
            final = made[-1].after
        if competition["status"]["type"].get("completed") and final is not None:
            scores = {c["homeAway"]: int(c["score"]) for c in competition["competitors"]}
            compared["final score"] += 1
            if (final.home.score, final.away.score) != (scores["home"], scores["away"]):
                flag("final score differs", f"{event}: board {final.away.score}-{final.home.score}, ESPN {scores['away']}-{scores['home']}")
        # ESPN's scoreboard settles a little after each play: its first reads can still show the
        # timeouts or score from before it. So each play is compared with the last read naming it.
        settled: dict[str, dict] = {}
        for read in reads.get(event, []):
            named = ((read["competitions"][0].get("situation") or {}).get("lastPlay") or {}).get("id")
            if named:
                settled[str(named)] = read
        for last, read in settled.items():
            situation = read["competitions"][0].get("situation") or {}
            states = afters.get(str(last), []) if last else []
            played = by_id.get(str(last))
            # ESPN gives every team its timeouts back on the play that ends a half.
            if not states or played is None or played.provider_type_text in ENDS:
                continue
            state = states[-1]
            sides = {c["homeAway"]: c for c in read["competitions"][0]["competitors"]}
            where = f"{event} after play {last}"
            scoreboard = (int(sides["home"]["score"]), int(sides["away"]["score"]))
            # A read between a touchdown and its try shows the touchdown's six, as the board does then.
            scores = [(s.home.score, s.away.score) for s in states]
            # ESPN's score and its last play can be out of step by a play: the score still from
            # before it, or already the next one's. The board shows that score one play away.
            near = [(s.home.score, s.away.score) for s in nearby.get(last, [])]
            compare("score", scores[-1] if scoreboard not in scores else scoreboard, scoreboard, where, near)
            compare(
                "timeouts",
                (state.home.timeouts, state.away.timeouts),
                (situation.get("homeTimeouts"), situation.get("awayTimeouts")),
                where,
                None,
            )
            if situation.get("down", 0) in (1, 2, 3, 4):
                end = (played.end.down, played.end.distance)
                compare("down and distance", (state.down, state.distance), (situation["down"], situation.get("distance")), where, end)
                if situation.get("possession"):
                    compare("possession", state.possession, situation["possession"], where, played.end.team_id)
    print("Compared with ESPN's scoreboard: " + ", ".join(f"{kind} {n}" for kind, n in compared.items()))
    print("Unknown on the board, not compared: " + (", ".join(f"{kind} {n}" for kind, n in unknown.items()) or "none"))
    print(
        "Where ESPN's own record of the play disagrees with its scoreboard, so the board can't match both: "
        + (", ".join(f"{kind} {n}" for kind, n in espn_differs.items()) or "none")
    )
    print("Penalty cards: " + ", ".join(f"{kind} {n}" for kind, n in fouls.items()))
    print(f"Problems: {sum(found.values())}")
    for kind, count in found.most_common():
        print(f"- {kind}: {count}, such as {examples[kind]}")


if __name__ == "__main__":
    main()
