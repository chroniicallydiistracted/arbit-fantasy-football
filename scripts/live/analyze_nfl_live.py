"""Compare first sightings, play revisions and browser traffic from a captured live game."""

import argparse
import gzip
import json
import re
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from statistics import median
from typing import Any


def instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def days(root: Path, start: datetime, end: datetime) -> Iterator[Path]:
    day = start.date()
    while day <= end.date():
        path = root / f"{day}.jsonl"
        if path.is_file():
            yield path
        day += timedelta(days=1)


def rows(
    paths: Iterable[Path], start: datetime, end: datetime
) -> Iterator[tuple[datetime, dict[str, Any]]]:
    for path in paths:
        with path.open(encoding="utf-8") as source:
            for number, line in enumerate(source, 1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    print(f"Skipped unreadable JSON in {path.name} line {number}", file=sys.stderr)
                    continue
                if not isinstance(row, dict):
                    continue
                when = instant(row.get("received_at") or row.get("at"))
                if when is not None and start <= when <= end:
                    yield when, row


def espn_sightings(
    records: Iterable[tuple[datetime, dict[str, Any]]],
    root: Path,
    event_id: str,
    plays: dict[str, dict[str, datetime]],
) -> dict[str, int]:
    wanted = {event_id + play_id: play_id for play_id in plays}
    counts: Counter[str] = Counter()

    @lru_cache(maxsize=32)
    def matching_ids(digest: str) -> set[str]:
        try:
            with gzip.open(root / "objects" / f"{digest}.json.gz", "rt", encoding="utf-8") as f:
                body = json.load(f)
            return {str(row.get("id")) for row in body.get("items", [])} & wanted.keys()
        except (OSError, EOFError, ValueError):
            counts["unreadable_objects"] += 1
            return set()

    for when, row in records:
        if row.get("kind") != "espn.plays" or row.get("event_id") != event_id:
            continue
        counts["requests"] += 1
        digest = row.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            counts["without_body"] += 1
            continue
        for provider_id in matching_ids(digest):
            sightings = plays[wanted[provider_id]]
            sightings["espn"] = min(when, sightings.get("espn", when))
    return dict(counts)


def browser_traffic(records: Iterable[tuple[datetime, dict[str, Any]]]) -> dict[str, Any]:
    requests: dict[tuple[str, int], tuple[Any, ...]] = {}
    routes: dict[tuple[Any, ...], list[datetime]] = defaultdict(list)
    statuses: dict[tuple[Any, ...], Counter[int]] = defaultdict(Counter)
    events: Counter[str] = Counter()
    transports = []
    navigation = []
    for when, row in records:
        event = row["event"]
        events[event] += 1
        key = (row["run"], row.get("id"))
        if event == "request" and row.get("resource") in {"xhr", "fetch", "eventsource"}:
            endpoint = tuple(row.get(k) for k in ("host", "path", "method", "resource"))
            requests[key] = endpoint
            routes[endpoint].append(when)
        elif event == "response" and key in requests:
            statuses[requests[key]][row["status"]] += 1
        elif event in {"websocket_open", "webtransport_open", "event_stream"}:
            transports.append(
                {k: row.get(k) for k in ("at", "event", "run", "id", "host", "path", "status")}
            )
        elif event in {
            "game_page",
            "game_page_failed",
            "refresh_to_find_play_by_play",
            "play_by_play_selected",
        }:
            navigation.append(
                {k: row[k] for k in ("at", "event", "run", "status", "control") if k in row}
            )
    fetch_routes = []
    for endpoint, times in sorted(routes.items(), key=lambda item: -len(item[1])):
        times.sort()
        gaps = [(b - a).total_seconds() for a, b in pairwise(times)]
        fetch_routes.append(
            {
                "host": endpoint[0],
                "path": endpoint[1],
                "method": endpoint[2],
                "resource": endpoint[3],
                "requests": len(times),
                "statuses": dict(statuses[endpoint]),
                "first_at": times[0],
                "last_at": times[-1],
                "median_gap_seconds": median(gaps) if gaps else None,
            }
        )
    return {
        "events": dict(events),
        "transports_opened": transports,
        "navigation": navigation,
        "fetch_routes": fetch_routes,
    }


def analyze(
    records: Iterable[tuple[datetime, dict[str, Any]]],
    game: str,
    event_id: str,
    start: datetime,
    end: datetime,
    espn_root: Path,
) -> dict[str, Any]:
    first: dict[str, dict[str, datetime]] = defaultdict(dict)
    whistles: dict[str, tuple[datetime, str]] = {}
    published: dict[str, datetime] = {}
    offsets: list[tuple[datetime, Any]] = []
    corrections: list[dict[str, Any]] = []
    previous: dict[str, tuple[datetime, dict[str, Any]]] = {}
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for when, row in sorted(records, key=lambda item: item[0]):
        route = row["route"]
        details = row.get("games", {}).get(game)
        if route == "summaries":
            if details is not None:
                offsets.append((when, details.get("offset")))
        elif row.get("game") != game and details is None and game not in row.get("game_ids", ()):
            continue
        counts[route][str(row.get("status") or row.get("error") or "observed")] += 1
        if route == "published":
            committed = instant(row.get("published_at")) or when
            for kind in ("introduced", "revised", "cancelled"):
                for provider_id in row.get(kind, []):
                    published.setdefault(provider_id.removeprefix(event_id), committed)
        if route == "stream":
            mime = row.get("headers", {}).get("content-type")
            if mime:
                counts[route][mime.split(";", 1)[0]] += 1
        detail = details if details is not None else row
        if "fingerprints" not in detail:
            continue
        for play_id in detail["fingerprints"]:
            first[play_id].setdefault(route, when)
        observed_whistles = detail.get("whistles")
        if observed_whistles is None and (timed := detail.get("newest_timed")):
            observed_whistles = {str(timed["play_id"]): timed["whistle_at"]}
        for play_id, raw_time in (observed_whistles or {}).items():
            if (whistle := instant(raw_time)) is not None:
                # Prefer the full primary game detail when routes disagree.
                if play_id not in whistles or (route == "v2" and whistles[play_id][1] != "v2"):
                    whistles[play_id] = whistle, route
        if route in previous:
            prior_at, prior = previous[route]
            for play_id, fingerprint in detail["fingerprints"].items():
                old = prior["fingerprints"].get(play_id)
                if old is not None and old != fingerprint:
                    corrections.append(
                        {
                            "route": route,
                            "play_id": play_id,
                            "previous_at": prior_at,
                            "observed_at": when,
                            "record_offset_before": prior.get("offset"),
                            "record_offset_after": detail.get("offset"),
                            "marked_deleted": play_id in detail.get("deleted", []),
                        }
                    )
        previous[route] = when, detail

    summary_times = [when for when, _ in offsets]
    for change in corrections:
        for when_key, label in (("previous_at", "before"), ("observed_at", "after")):
            index = bisect_right(summary_times, change[when_key]) - 1
            change[f"summary_offset_{label}"] = offsets[index][1] if index >= 0 else None
            change[f"summary_observed_{label}"] = offsets[index][0] if index >= 0 else None
        before, after = change["summary_offset_before"], change["summary_offset_after"]
        change["summary_offset_changed"] = (
            before != after if before is not None and after is not None else None
        )

    espn_counts = espn_sightings(days_rows(espn_root, start, end), espn_root, event_id, first)
    plays = {}
    delays: dict[str, list[float]] = defaultdict(list)
    for play_id, sightings in first.items():
        if play_id in published:
            sightings["app_commit"] = published[play_id]
        whistle, whistle_route = whistles.get(play_id, (None, None))
        per_route = {}
        for route, when in sightings.items():
            # A first observation before the reported whistle is a data-quality finding.
            seconds = round((when - whistle).total_seconds(), 3) if whistle is not None else None
            per_route[route] = {"at": when, "seconds_after_whistle": seconds}
            if seconds is not None and seconds >= 0 and start <= whistle <= end:
                delays[route].append(seconds)
        plays[play_id] = {"whistle_at": whistle, "whistle_route": whistle_route, "first": per_route}
    return {
        "nfl_request_counts": {route: dict(statuses) for route, statuses in counts.items()},
        "espn_capture_counts": espn_counts,
        "summary_samples": len(offsets),
        "timed_plays_in_window": sum(start <= when <= end for when, _ in whistles.values()),
        "timed_arrivals": {
            route: {
                "plays": len(values),
                "median_seconds": round(median(values), 3),
                "p90_seconds": sorted(values)[(9 * len(values) - 1) // 10],
            }
            for route, values in sorted(delays.items())
        },
        "plays": plays,
        "payload_revisions": corrections,
    }


def days_rows(
    root: Path, start: datetime, end: datetime
) -> Iterator[tuple[datetime, dict[str, Any]]]:
    return rows(days(root, start, end), start, end)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, help="NFL game UUID")
    parser.add_argument("--espn-event", required=True, help="Linked ESPN event ID")
    parser.add_argument("--from", dest="start", required=True, help="ISO timestamp with timezone")
    parser.add_argument("--until", required=True, help="ISO timestamp with timezone")
    parser.add_argument("--nfl-log", type=Path, default=Path("data/nfl-api/live-log"))
    parser.add_argument("--espn-capture", type=Path, default=Path("data/live-captures"))
    parser.add_argument("--browser-log", type=Path)
    args = parser.parse_args()
    start, end = instant(args.start), instant(args.until)
    if start is None or end is None or start >= end:
        parser.error("--from and --until must be ordered, timezone-aware ISO timestamps")
    result = analyze(
        days_rows(args.nfl_log, start, end),
        args.game,
        args.espn_event,
        start,
        end,
        args.espn_capture,
    )
    result.update(game=args.game, espn_event=args.espn_event, window_start=start, window_end=end)
    if args.browser_log is not None:
        result["browser"] = browser_traffic(rows([args.browser_log], start, end))
    print(json.dumps(result, indent=2, default=datetime.isoformat))


if __name__ == "__main__":
    main()
