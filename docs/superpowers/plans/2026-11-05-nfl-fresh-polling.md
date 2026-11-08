# Fresh NFL polling

Implemented and loaded locally on November 5 at 22:37 Arizona time. [Verification and remaining live evidence](../../project/handoffs/2026-11-05-nfl-fresh-polling.md).

Requirements LV-001, LV-003, LV-005, DATA-006, DATA-008 and ENG-005. The owner requested a new cache key on each poll and a two-second cadence after the [Week 9 experiment](2026-11-05-live-feed-observation.md). The owner independently measured 60 cold v2 requests using a unique `_cache_probe` value per request.

- In `nfl_feed.py`, keep the existing v2 game-detail response and add a fresh `_cache_probe` to each primary summary or detail read. Poll each active or imminently starting game on each two-second round, independent of summary offsets. Use the existing pregame and idle cadences outside the live window.
- Anchor the next round to the previous start and bound concurrent game reads. Preserve the 90-second ESPN fallback and explicit rate-limit backoff. Keep polling for a usable final detail when its summary finishes first. The alternate-route probe remains a cached control for the live comparison.
- In `test_nfl_lane.py`, exercise distinct cache keys, start-to-start timing, identical summaries, corrections, a lagging final, and fallback on the isolated PostgreSQL database. Run the full runtime check and verify the local worker outside the game window.
- The database schema, app contract and local deployment model stay the same. In-game latency and the full-slate request budget are Sunday evidence under R-042.
