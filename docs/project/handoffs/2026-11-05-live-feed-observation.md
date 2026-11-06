# Handoff — 2026-11-05 — Week 9 live-feed observation

## Running before kickoff

Jacksonville at Baltimore kicks off at **18:15 Arizona time** on November 5 (01:15 UTC on November 6). NFL game ID `ab380826-4feb-11f1-abca-2c54536568a9`, ESPN event `401873037`. The [earlier handoff](2026-11-05-live-by-kickoff.md) covers migration `0008`, the live field and art. The [observation plan](../../superpowers/plans/2026-11-05-live-feed-observation.md) covers the collector follow-up.

- The existing local `arbit-worker.service` first loaded the observation changes at 17:08 Arizona time. It loaded the last verified fix at **17:25:15 Arizona time**, so the by-slug probe can learn the game's slug from its first detail read. All five lanes started, the NFL lane discovered 15 Week 9 games, and the local API returned `{"status":"ready"}`. The API process and its served web build stayed in use.
- `arbit-nfl-browser-week9.service` is a separate transient local service for the [public Game Center](https://www.nfl.com/games/jaguars-at-ravens-2026-reg-9). The final recorder started at **17:16:04 Arizona time** and stops at **23:00 Arizona time** (06:00 UTC). It loaded the game page with HTTP 200, rejected optional cookies, and recorded over 600 pregame requests in its latest run.
- Work is local and uncommitted on `claude/platform-reset`. The collector uses the existing database schema and outbox.

## What the capture covers

| Input | Collection |
| --- | --- |
| Primary NFL feed | Summaries every 2 seconds of wait in active mode, 30 seconds pregame, 5 minutes idle. The summary hash includes the offset. Changed summaries trigger v2 detail reads and up to 30 seconds of fast cache retries. Final detail still behind after the chase retries at the 20-second correction cadence. Unlisted active games get a 5-second detail cadence. NFL plays are eligible as primary for 90 seconds after the last usable detail. |
| NFL route probe | Independently scheduled reads for at most two games. Direct v2 every 2 seconds, v1, by-slug and player statistics every 4 seconds, shared weekly details every 10 seconds, event-stream handshake every minute. Intervals are minimum waits and can stretch with response time. Starts 5 minutes before kickoff and can sample a minute after final. A 429 pauses this lane for at least a minute. `ARBIT_NFL_PROBE=0` disables it on worker startup. |
| ESPN | Existing `data/live-captures/` keeps page-level arrival times and deduplicated response objects. When the NFL feed is primary, ESPN's independent shadow reads capture comparison data. The same ESPN lane publishes fallback plays when the NFL game is stale. |
| Browser | `data/nfl-api/browser/jaguars-at-ravens-2026-reg-9.jsonl` contains route, method, type, timing, status, cache and size metadata from the isolated browser, plus page-level DevTools WebSocket, SSE and WebTransport events. Request headers, cookies, bodies and frame contents are omitted. The recorder selects play-by-play or All Drives when offered and logs any navigation used to find it. |
| NFL request receipts | `data/nfl-api/live-log/<UTC date>.jsonl` records individual attempts, gzip sizes, cache headers, summary offsets, per-play fingerprints and whistle times. A publication row records which play IDs committed and when. The logger writes owner-only files and reports write failures to the worker journal. |

## Checks

| Command or observation | Result |
| --- | --- |
| `uv sync --frozen` and `make db-up` | Passed. The dedicated PostgreSQL container was healthy. |
| `npm exec --offline --yes --package=pnpm@12.16.1 -- make runtime-check` | Passed with 1,181 tests, Ruff, mypy, foundation and contract checks. The new fixtures cover the final retry and persisted phase, independent ESPN shadow cadence and fallback, and the postgame report. |
| Client contract and design checks, Biome, TypeScript, Vitest, `vite build --outDir /tmp/arbit-web-kickoff.MctQbL`, `pnpm test:pwa` | Passed. 22 web tests and one PWA test passed. Biome reported three existing reduced-motion `!important` warnings. |
| `pnpm --filter @arbit/web test:browser` against the fictional API on port 8011 and the isolated build | 11 passed, including the open-client update without a reload and the Live game deep link. |
| Public NFL API pregame smoke | Week discovery, schedule and summaries returned HTTP 200 with gzip. Schedule receipt recorded 4,491 compressed bytes and 32,307 decoded bytes. |
| One request per probe route against JAX at BAL before kickoff | All six returned HTTP 200. The event-stream request returned JSON in pregame. The weekly route included the target game. |
| Schedule and v2 detail comparison for JAX at BAL | The schedule has no slug. The detail returns `jaguars-at-ravens-2026-reg-9`, which the worker now records even when the response has no football plays. The isolated regression verifies that later schedule discovery preserves it. |
| Public Game Center control smoke | A separate CHI at SEA recorder run loaded HTTP 200, rejected optional cookies and selected **All Drives**. The JAX at BAL recorder loaded the pregame page, where that control was absent. |
| Pregame report against tonight's logs | It joined four summary receipts and 32 browser fetch routes. There were zero timed plays in the window. Both current JSONL files had mode 0600. |

## After the game

Run this command from the repository root to build the private comparison report.

```sh
umask 077
python3 scripts/live/analyze_nfl_live.py \
  --game ab380826-4feb-11f1-abca-2c54536568a9 \
  --espn-event 401873037 \
  --from 2026-11-06T01:10:00Z \
  --until 2026-11-06T06:00:00Z \
  --browser-log data/nfl-api/browser/jaguars-at-ravens-2026-reg-9.jsonl \
  > data/nfl-api/jaguars-at-ravens-2026-reg-9-report.json
```

The report lists first sightings and whistle delays per play, plus each route's sample count, median and p90. ESPN joins by the established event ID + NFL play ID match. For each changed play fingerprint it shows the last summary offset observed at each side of the change. Offsets can advance for unrelated updates, and play fingerprints also cover provider metadata. Use the browser request cadence with recorded navigation times and transport events to distinguish recurring reads from page loads.

**R-042 remains open** for actual in-game route freshness, live-only fields, offset coverage, browser transport behavior and whistle-to-app latency. The request budget for a full Sunday slate depends on this evidence. Host sleep or loss of network interrupts observation (R-029). Capture files and the report stay under ignored `data/`.
