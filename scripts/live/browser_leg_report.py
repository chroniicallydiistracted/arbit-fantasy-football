"""Join `time_browser_leg.cjs` timings with the worker's publications: announced -> event -> fetched -> shown.

uv run python scripts/live/browser_leg_report.py out.jsonl data/nfl-api/live-log/<UTC day>.jsonl
"""

import json
import sys
from datetime import datetime
from statistics import median, quantiles

browser_log, live_log = sys.argv[1], sys.argv[2]
rows = [json.loads(line) for line in open(browser_log, encoding="utf-8")]
start = next(r["at"] for r in rows if r["kind"] == "started")
stop = next(r["at"] for r in rows if r["kind"] == "stopped")
tabs = {r["tab"] for r in rows if "tab" in r}


def ms(value: str) -> float:
    return datetime.fromisoformat(value).timestamp() * 1000


published: dict[str, tuple[str, float]] = {}
with open(live_log, encoding="utf-8") as source:
    for line in source:
        if '"published"' not in line:
            continue
        row = json.loads(line)
        if row.get("route") != "published" or row["event_id"] not in tabs:
            continue
        at = ms(row["published_at"])
        if start <= at <= stop - 15_000:
            for play in row.get("introduced") or []:
                published.setdefault(play, (row["event_id"], at))

sse = [r for r in rows if r["kind"] == "sse" and r["name"] in ("game.plays", "game.corrected")]
fetches = [r for r in rows if r["kind"] == "fetch" and r["path"].endswith("/plays")]
screens = {r["id"]: r["at"] for r in rows if r["kind"] == "screen"}
timeouts = {r["id"] for r in rows if r["kind"] == "screen-timeout"}

legs: dict[str, list[float]] = {
    k: [] for k in ("event", "fetch", "screen", "total_fetch", "total_screen")
}
missing = 0
for play, (event, at) in published.items():
    events = sorted(
        r["at"]
        for r in sse
        if r["tab"] == event
        and json.loads(r["data"] or "{}").get("event") == event
        and r["at"] >= at - 500
    )
    got = sorted(r["done"] for r in fetches if r["tab"] == event and play in (r.get("new") or []))
    if not events or not got:
        missing += 1
        continue
    legs["event"].append(events[0] - at)
    legs["fetch"].append(got[0] - events[0])
    legs["total_fetch"].append(got[0] - at)
    if play in screens:
        legs["screen"].append(screens[play] - got[0])
        legs["total_screen"].append(screens[play] - at)


def spread(values: list[float]) -> str:
    if not values:
        return "none"
    cuts = quantiles(values, n=10) if len(values) > 1 else [values[0]] * 9
    return (
        f"n={len(values)} median={median(values):.0f} p90={cuts[-1]:.0f} max={max(values):.0f} ms"
    )


print(
    f"Window {datetime.fromtimestamp(start / 1000):%H:%M:%S}-{datetime.fromtimestamp(stop / 1000):%H:%M:%S} local; tabs {len(tabs)}"
)
print(
    f"Plays announced on open tabs: {len(published)}; matched end to end: {len(published) - missing}"
)
print("Announced -> event at the page:      ", spread(legs["event"]))
print("Event -> plays re-fetched with it:   ", spread(legs["fetch"]))
print("Announced -> play data on the page:  ", spread(legs["total_fetch"]))
print("Data -> play text on screen:         ", spread(legs["screen"]))
print("Announced -> play text on screen:    ", spread(legs["total_screen"]))
print(f"Text never shown within 90 s: {len(timeouts & set(published))}")
anim = [
    r["done"] - r["sent"] for r in rows if r["kind"] == "fetch" and r["path"].endswith("/animation")
]
plays_fetch = [r["done"] - r["sent"] for r in fetches]
print("Plays request time:    ", spread(plays_fetch))
print("Animation request time:", spread(anim))
print("Errors reading bodies:", sum(1 for r in fetches if "error" in r))
