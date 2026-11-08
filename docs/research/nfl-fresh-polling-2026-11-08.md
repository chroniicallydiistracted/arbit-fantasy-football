# Fresh-key NFL polling on a live Sunday — 2026-11-08

R-042 asked for a paired first-play comparison and a request budget during overlapping games, after the fresh-key, two-second polling change (OWN-045). This is that measurement. All figures come from the worker's private request log (`data/nfl-api/live-log/`). Reproduce:

```sh
uv run python scripts/live/check_fresh_polling.py --day 2026-11-08 --since 16:41
uv run python scripts/live/check_fresh_polling.py --day 2026-11-06   # Thursday, before the change
```

**Window.** 16:41 UTC (the worker resumed after the PC woke) to about 20:40 UTC. It covers the end of Cincinnati–Atlanta and the seven 11:00 MST games up to their fourth quarters. The late games hadn't kicked off. Plays whistled before the lane's first read of their game were left out, which drops the Cincinnati–Atlanta catch-up.

## Result: fresh keys reach plays about twice as fast

| Measure | Fresh-key v2 (primary lane) | Cached v2 (probe, same games) | Thursday, primary lane before the change |
| --- | --- | --- | --- |
| Response age | Age 0 on all 35,075 reads; edge MISS on all | median 18 s, p90 32 s; 92% edge HIT | median 22 s; 91% HIT |
| Whistle → first sighting | **median 17.9 s**, p10 11.6, p90 35.6 (868 plays) | median 39.4 s, p90 56.5 (263 plays) | median 33.9 s, p90 54.3 (126 plays) |

- **Same play, both routes:** fresh saw all 263 commonly probed plays first, by a median of 17.6 s (p10 4.6, p90 32.5).
- **Stale reads:** of the 1,792 cached reads sent after the fresh lane already had a play, 85% still lacked it.
- **Poll timing isn't the difference:** the probe polled each game every 2.6 s (median), close to the fresh lane's 2.0 s.
- **Into the app:** a play was committed and published within 0.2 s of its first fresh sighting (median 0.0 s).
- **What remains:** the ~18 s left is the NFL's own entry time before a play appears at the origin. Polling can't shorten it.

## Worker health and request budget

- **Cadence:** reads of each live game were 2.0 s apart (median; p10 1.9, p90 2.1). Of 30,424 gaps, 20 exceeded 3 s and 7 exceeded 5 s.
- **Responses:** median 0.4 s, p90 0.6 s, max 1.6 s.
- **Errors:** one network blip, 18:43–18:44 UTC, with `NFL_API_UNREACHABLE` on 14 primary reads and one on each other route. The longest gap was 73 s, short of the 90 s ESPN fallback. No 429s; every other read returned 200.
- **Sign-in:** the token refreshed about every 55 minutes, 9 sign-ins each time (one per worker thread), all 200.
- **Volume (primary lane only):**
  - Median minute: 240 requests and 3.1 MB on the wire (gzip). Busiest: 249 requests and 9.6 MB at 20:21 UTC.
  - The research probe added about 23,600 requests over the window: v2-direct, v1, slug, player stats, weekly and stream.

## Browser leg: announced to on screen

Measured 14:01–14:13 MST with seven signed-in tabs, one per game: the last minutes of six 11:00 games and the start of the 14:05 game. The dev account ran on the local port, one browser profile per tab. 87 plays were announced on open tabs, and 83 were matched end to end.

| Step | Median | p90 | Max |
| --- | --- | --- | --- |
| Announced → event at the page | 0.52 s | 0.95 s | 1.07 s |
| Event → plays re-fetched with the new play | 0.49 s | 0.85 s | 1.96 s |
| **Announced → play on screen** | **1.0 s** | 1.6 s | 2.9 s |

- **Event wait:** most of it is the API checking the outbox once a second.
- **Re-fetch:** the page batches events for 250 ms, then re-fetches. With seven tabs re-fetching, the plays request took 0.74 s (median).
- **Rendering:** text appeared as soon as the data arrived (median under 20 ms). Three plays' text wasn't found within 90 s.
- **On screen** means the play's text is on the page. The field animation then plays at the play's real duration.
- **Through Cloudflare:** each request adds about one more round trip to Cloudflare's Los Angeles edge, about 43 ms from this house. Access blocks automation, so that path wasn't timed end to end.
- **Whole chain:** about 19 s median from whistle to screen, of which about 18 s is before the play reaches the NFL's feed.
- **Test artifact:** the first attempt shared one browser profile across seven tabs. On the local port's HTTP/1.1, the seven open event streams used up Chrome's six connections per site, and the tabs' re-fetches stalled. The public address's HTTP/2 shares one connection, so members aren't affected. Several local tabs in one browser would be.

Reproduce with `scripts/live/time_browser_leg.cjs`, then `scripts/live/browser_leg_report.py`; usage is in the script headers.

## Limits

- **Coverage:** one Sunday afternoon window, ending in the 11:00 games' fourth quarters. The late games, the night game and Monday aren't included.
- **Probe sample:** it covers a capped subset of games, so the paired sample (263) is smaller than the fresh one (868).
