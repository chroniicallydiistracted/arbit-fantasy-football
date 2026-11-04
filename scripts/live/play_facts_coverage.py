"""Coverage of the play interpreter over every captured game (automation slice 1 evidence).

Reads only the private captures in data/live-captures: for each game, the newest copy of every
play from the core API pages, normalized by the current code and interpreted. Teams come from the
captured scoreboards. Prints Markdown tables; makes no requests and writes nothing.

Usage: uv run python scripts/live/play_facts_coverage.py [captures dir]
"""

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from arbit_data.live.normalize import normalize_play
from arbit_data.live.play_facts import GameTeams, PlayFacts, interpret, text_codes

SEASON = 2026


def load(root: Path, sha: str) -> object:
    raw = (root / "objects" / f"{sha}.json.gz").read_bytes()
    return json.loads(gzip.decompress(raw))


def text_codes_of(texts: list[str]) -> set[str]:
    return text_codes(texts)


def captured(root: Path) -> tuple[dict[str, dict[str, dict]], dict[str, tuple[str, str, str, str]]]:
    """Newest raw play per game and play ID, and each game's (home, away, home code, away code)."""
    reads: dict[tuple[str, int], tuple[str, str]] = {}
    boards: list[tuple[str, str]] = []
    for log in sorted(root.glob("*.jsonl")):
        for line in log.read_text().splitlines():
            entry = json.loads(line)
            if entry["kind"] == "espn.plays" and entry.get("event_id"):
                key = (entry["event_id"], int(entry.get("page") or 1))
                if key not in reads or entry["at"] > reads[key][0]:
                    reads[key] = (entry["at"], entry["sha256"])
            elif entry["kind"].startswith("espn.scoreboard"):
                boards.append((entry["at"], entry["sha256"]))
    plays: dict[str, dict[str, dict]] = defaultdict(dict)
    for (event, _page), (_at, sha) in reads.items():
        for item in load(root, sha).get("items", []):  # type: ignore[union-attr]
            known = plays[event].get(str(item.get("id")))
            if known is None or (item.get("modified") or "") >= (known.get("modified") or ""):
                plays[event][str(item.get("id"))] = item
    teams: dict[str, tuple[str, str, str, str]] = {}
    for _at, sha in sorted(boards):
        for event in load(root, sha).get("events", []):  # type: ignore[union-attr]
            sides = {c["homeAway"]: c["team"] for c in event["competitions"][0]["competitors"]}
            teams[event["id"]] = (
                sides["home"]["id"],
                sides["away"]["id"],
                sides["home"]["abbreviation"],
                sides["away"]["abbreviation"],
            )
    return plays, teams


def main(root: Path) -> None:
    plays, teams = captured(root)
    facts: list[PlayFacts] = []
    failed = Counter()
    for event, items in sorted(plays.items()):
        if event not in teams:
            failed["no scoreboard"] += len(items)
            continue
        normalized = []
        for raw in items.values():
            try:
                normalized.append(normalize_play(raw, event, SEASON))
            except ValueError as error:
                failed[str(error)] += 1
        context = GameTeams.build(*teams[event], seen=text_codes(p.text for p in normalized))
        facts += [interpret(p, context) for p in normalized]
    print(f"Games: {len(plays)}. Plays: {len(facts)}. Not normalized: {dict(failed) or 0}.\n")

    print("| Shape | Plays | Template, nothing missing | Missing a fact | No template (reason) |")
    print("| --- | --- | --- | --- | --- |")
    by_shape: dict[str, list[PlayFacts]] = defaultdict(list)
    for fact in facts:
        by_shape[fact.shape].append(fact)
    totals = Counter()
    for shape, group in sorted(by_shape.items(), key=lambda kv: -len(kv[1])):
        ready = [f for f in group if f.template and not f.missing]
        short = Counter(m for f in group if f.template for m in f.missing)
        reasons = Counter(f.reason for f in group if not f.template)
        totals["plays"] += len(group)
        totals["ready"] += len(ready)
        print(f"| {shape} | {len(group)} | {len(ready)} | {dict(short) or ''} | {dict(reasons) or ''} |")
    football = [f for f in facts if f.shape not in ("timeout", "other")]
    ready = [f for f in football if f.template and not f.missing]
    print(f"\nFootball plays: {len(football)}; ready to animate: {len(ready)} ({len(ready) / len(football):.1%}).\n")

    # The interpreter's spots against ESPN's own: the spot the text states, and start plus yards.
    simple = [
        f
        for f in football
        if f.shape in ("pass", "run", "scramble", "kneel", "sack")
        and not f.penalties
        and not f.turnover
        and f.reason is None
    ]
    stated = [f for f in simple if f.action_end is not None and f.end is not None]
    agree = sum(f.action_end == f.end for f in stated)
    added = [f for f in simple if None not in (f.start, f.yards, f.end)]
    sums = sum(f.start + f.yards == f.end for f in added)  # type: ignore[operator]
    print("| Check | Plays | Agree |")
    print("| --- | --- | --- |")
    print(f"| End spot vs the spot the text states | {len(stated)} | {agree} ({agree / max(len(stated), 1):.1%}) |")
    print(f"| Start + yards = end | {len(added)} | {sums} ({sums / max(len(added), 1):.1%}) |")
    yte = Counter(f.spot_source for f in football)
    print(f"\nSpot source: {dict(yte)}")

    completions = [f for f in football if f.passing and f.passing.result == "complete"]
    caught = sum(f.passing.catch_spot is not None for f in completions)  # type: ignore[union-attr]
    picks = [f for f in football if f.passing and f.passing.result == "intercepted"]
    picked = sum(f.passing.catch_spot is not None for f in picks)  # type: ignore[union-attr]
    aimed = [f for f in football if f.passing and f.passing.result == "incomplete"]
    depth = sum(f.passing.depth is not None for f in aimed)  # type: ignore[union-attr]
    runs = [f for f in football if f.run and f.run.style == "run"]
    lanes = sum(f.run.side is not None for f in runs)  # type: ignore[union-attr]
    print("\n| Fact | Plays | Stated |")
    print("| --- | --- | --- |")
    print(f"| Catch spot on completions (yards after catch) | {len(completions)} | {caught} |")
    print(f"| Spot of interceptions | {len(picks)} | {picked} |")
    print(f"| Depth and side of incompletions | {len(aimed)} | {depth} |")
    print(f"| Direction of runs | {len(runs)} | {lanes} |")
    for shape in ("punt", "kickoff", "field_goal"):
        group = [f for f in football if f.shape == shape and f.kick]
        results = Counter(f.kick.result for f in group)  # type: ignore[union-attr]
        landed = sum(f.kick.landing is not None or f.kick.distance is not None for f in group)  # type: ignore[union-attr]
        print(f"| {shape} distance or landing; results {dict(results)} | {len(group)} | {landed} |")
    extra = Counter((f.point_after.kind, f.point_after.good) for f in football if f.point_after is not None)
    print(f"\nExtra points and two-point tries attached to plays: {dict(extra)}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/live-captures"))
