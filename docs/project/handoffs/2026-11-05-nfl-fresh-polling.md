# Handoff — 2026-11-05 — Fresh NFL polling

The owner requested fresh keys on every primary NFL poll and a two-second active cadence (OWN-045). In Thursday's capture, 112 timed plays had a 33.8-second median from whistle to ordinary direct v2 arrival. The owner then ran 60 paired postgame requests. Every unique `_cache_probe` value produced `Age: 0` and `MISS, MISS, MISS`, and all 60 normal requests reported a hit. The private study with both experiments is under `data/nfl-api/cache-study-2026-11-05/`. [Implementation plan](../../superpowers/plans/2026-11-05-nfl-fresh-polling.md).

## Worker behavior

- The primary lane sends one week summary request and one full v2 detail request per active, linked game in each round. Each request gets a distinct `_cache_probe` UUID, including summary polls outside the active window. A cache-key value is also recorded in its private receipt.
- Active rounds are due two seconds after the previous round starts. The lane watches the five minutes before kickoff and finishes when it has a usable final record. If a summary arrives first with a final phase, details continue until they catch up. Outside the active window, summary rounds follow the 30-second pregame and five-minute idle cadences.
- Overlapping game reads run concurrently with up to eight workers. The lane waits for a round to finish before starting another, so a slow provider response can extend the interval. HTTP 429 pauses the lane according to its backoff and `Retry-After`.
- Unchanged detail bodies refresh the observation timestamp. New plays and corrections go through the existing transaction and outbox. ESPN's emergency fallback remains eligible after 90 seconds without a usable NFL detail. The route probe continues to use normal cache keys for comparison.

## Verification and activation

- `uv run --frozen pytest -q tests/integration/test_nfl_lane.py` covered independent two-second reads, cache-key uniqueness, overlapping games, summary failure, correction publication, rate-limit backoff, and the final-record transition.
- `uv sync --frozen`, `make db-up` and `npm exec --offline --yes --package=pnpm@12.16.1 -- make runtime-check` succeeded. The final runtime suite passed **1,184 tests** with foundation, lint, typing and contract checks.
- The worker used an isolated PostgreSQL schema and a simulated four-minutes-before-kickoff clock for the real Cincinnati–Atlanta pregame response. Three summary and three v2 detail reads had distinct keys, HTTP 200, age zero and three misses. Measured send gaps were 1.498 and 2.000 seconds for both routes. The initial anonymous sign-in delayed the first send in the isolated run. Receipts are under the private study's `worker-smoke/` directory.
- The local worker restarted at **22:37:13 Arizona time** after the game was final. It discovered all 15 Week 9 games and its first summary returned HTTP 200 with age zero and three misses. The local API reported ready. The browser recorder retained its process and continued its own capture.

## Sunday

R-042 remains open. Use the private receipts to compare fresh v2 against the cached v2 probe by new play ID, then measure actual round cadence, error rate and request volume during overlapping games. The native drive chart is a separate research result with a shorter observed cache cycle and still needs a live comparison. [Thursday capture handoff](2026-11-05-live-feed-observation.md).
