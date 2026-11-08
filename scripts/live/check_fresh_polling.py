"""Measure the fresh-key NFL polling (OWN-045, R-042) from the worker's request log.

Compares the primary lane's fresh-key v2 reads (`nfl`/`v2`) with the probe's ordinary cached reads
of the same route (`nfl_probe`/`v2-direct`): cache headers, per-game cadence, errors, request
volume, and when each new play first appeared after its whistle. Plays already whistled before the
lane's first read of their game (a catch-up after sleep) are left out of the latency figures.

    uv run python scripts/live/check_fresh_polling.py --day 2026-11-08 [--since 16:41]
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median, quantiles
from typing import Any

FRESH, CACHED = ("nfl", "v2"), ("nfl_probe", "v2-direct")


def when(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def spread(values: list[float]) -> str:
    if not values:
        return "none"
    cuts = quantiles(values, n=10) if len(values) > 1 else [values[0]] * 9
    return (
        f"n={len(values)} median={median(values):.1f} p10={cuts[0]:.1f} "
        f"p90={cuts[-1]:.1f} max={max(values):.1f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", required=True, help="UTC day of the log file")
    parser.add_argument("--since", default="00:00", help="UTC time to start from, HH:MM")
    parser.add_argument("--log", type=Path, default=Path("data/nfl-api/live-log"))
    args = parser.parse_args()
    start = when(f"{args.day}T{args.since}:00Z")

    routes: Counter[tuple[str, str]] = Counter()
    statuses: Counter[tuple[str, str, Any]] = Counter()
    errors: Counter[tuple[str, str, Any]] = Counter()
    ages: dict[tuple[str, str], list[float]] = defaultdict(list)
    edge: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    sends: dict[str, list[datetime]] = defaultdict(list)
    round_seconds: list[float] = []
    per_minute: Counter[str] = Counter()
    bytes_per_minute: Counter[str] = Counter()
    first_read: dict[str, datetime] = {}
    seen: dict[tuple[str, str], dict[str, datetime]] = {FRESH: {}, CACHED: {}}
    whistle: dict[str, datetime] = {}
    cached_reads: dict[str, list[tuple[datetime, frozenset[str]]]] = defaultdict(list)
    published: dict[str, datetime] = {}

    with (args.log / f"{args.day}.jsonl").open(encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            at = when(row.get("received_at") or row["at"])
            if at < start:
                continue
            key = (row["lane"], row["route"])
            if key == ("nfl", "published"):
                event = row["event_id"]
                for play in row.get("introduced") or []:  # ESPN play IDs: event ID + NFL play ID
                    if play.startswith(event):
                        published.setdefault(
                            f"{event}:{play[len(event) :]}", when(row["published_at"])
                        )
                continue
            routes[key] += 1
            if "error" in row:
                errors[(*key, row["error"])] += 1
            if row["lane"] == "nfl" and "sent_at" in row:
                minute = row["sent_at"][:16]
                per_minute[minute] += 1
                bytes_per_minute[minute] += row.get("wire_bytes") or 0
            if key not in (FRESH, CACHED):
                continue
            statuses[(*key, row.get("status"))] += 1
            if row.get("status") != 200 or "fingerprints" not in row:
                continue
            headers = row.get("headers") or {}
            if "age" in headers:
                ages[key].append(float(headers["age"]))
            edge[key][(headers.get("x-cache") or "?").split(",")[-1].strip()] += 1
            event = row["event_id"]
            if key == FRESH:
                sent = when(row["sent_at"])
                first_read.setdefault(event, sent)
                if row.get("reason") == "active" and row.get("phase") == "INGAME":
                    sends[event].append(sent)
                    round_seconds.append(row["seconds"])
            plays = frozenset(row["fingerprints"])
            for play in plays:
                seen[key].setdefault(f"{event}:{play}", at)
            for play, at_whistle in (row.get("whistles") or {}).items():
                whistle.setdefault(f"{event}:{play}", when(at_whistle))
            if key == CACHED:
                cached_reads[event].append((when(row["sent_at"]), plays))

    print(f"Window: {start:%Y-%m-%d %H:%M} UTC to the end of the log\n")
    print("Requests by lane and route:")
    for (lane, route), count in sorted(routes.items()):
        print(f"  {lane}/{route}: {count}")
    print("Status codes (v2 reads):", dict(statuses))
    print("Errors:", dict(errors) or "none")
    for key, label in ((FRESH, "fresh-key v2"), (CACHED, "cached v2 probe")):
        print(f"\n{label}: Age seconds {spread(ages[key])}; edge cache {dict(edge[key])}")

    gaps = [
        (later - earlier).total_seconds()
        for times in sends.values()
        for earlier, later in zip(times, times[1:], strict=False)
        if (later - earlier).total_seconds() < 120
    ]
    print(f"\nFresh v2 gap between reads of the same live game (s): {spread(gaps)}")
    print(
        f"  gaps over 3 s: {sum(gap > 3 for gap in gaps)}; over 5 s: {sum(gap > 5 for gap in gaps)}"
    )
    print(f"Fresh v2 response time (s): {spread(round_seconds)}")
    probe_gaps = [
        (b[0] - a[0]).total_seconds()
        for reads in cached_reads.values()
        for a, b in zip(reads, reads[1:], strict=False)
        if (b[0] - a[0]).total_seconds() < 120
    ]
    print(f"Cached probe gap between reads of the same game (s): {spread(probe_gaps)}")
    busiest = sorted(per_minute, key=per_minute.__getitem__)[-1] if per_minute else None
    if busiest:
        print(
            f"\nPrimary lane volume: busiest minute {busiest} UTC with {per_minute[busiest]} "
            f"requests and {bytes_per_minute[busiest] / 1e6:.1f} MB on the wire; "
            f"median minute {median(per_minute.values()):.0f} requests, "
            f"{median(bytes_per_minute.values()) / 1e6:.1f} MB"
        )

    live = {
        play
        for play, at in whistle.items()
        if play in seen[FRESH] and at >= first_read.get(play.split(":")[0], at)
    }
    fresh_lag = [(seen[FRESH][play] - whistle[play]).total_seconds() for play in live]
    print(
        f"\nWhistle to first fresh sighting (s), plays whistled while polling: {spread(fresh_lag)}"
    )
    commit = [
        (published[play] - seen[FRESH][play]).total_seconds() for play in live if play in published
    ]
    print(f"First fresh sighting to published in the app (s): {spread(commit)}")

    probed = {play for play in live if play in seen[CACHED]}
    cached_lag = [(seen[CACHED][play] - whistle[play]).total_seconds() for play in probed]
    print(f"Whistle to first cached-probe sighting (s), probed games: {spread(cached_lag)}")
    paired = [(seen[CACHED][play] - seen[FRESH][play]).total_seconds() for play in probed]
    print(f"Paired: cached sighting minus fresh sighting, same play (s): {spread(paired)}")
    print(
        f"  fresh first: {sum(p > 0 for p in paired)}, cached first: {sum(p < 0 for p in paired)}"
    )
    stale = served = 0
    for play in probed:
        event, play_id = play.split(":")
        for sent, plays in cached_reads[event]:
            if sent >= seen[FRESH][play]:
                served += 1
                stale += play_id not in plays
                if play_id in plays:
                    break
    print(
        f"Cached probe reads sent after fresh already had the play: {served}; "
        f"still missing it: {stale} ({stale / served:.0%})"
        if served
        else "No cached probe reads to compare"
    )


if __name__ == "__main__":
    main()
