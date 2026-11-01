# Supplemental and live source operations — M1e

**Current owner policy:** Sleeper is eligible only for verified relevant NFL live-game/PBP data. No eligible route is currently enabled. Former fantasy directories, hints, state/trends and fantasy-stat acquisition/mapping are retired; `sleeper-sync` and `sleeper-probe` return `SLEEPER_LIVE_ONLY` before reading cache or contacting a provider. Remaining Sleeper descriptions below are historical M1e implementation notes, not active product capability. Default source status/verification excludes retired Sleeper observations.

M1e adds durable public observations and safe local inspection. ESPN remains FFA authority, NFLverse remains the statistical foundation, and Sleeper is supplemental. No source command calculates fantasy recommendations, changes a league, creates aliases or serves public/member data. The [source audit](../research/m1e-source-audit-2026-10-31.md) distinguishes actual capabilities from empirical gaps.

## Local commands

After frozen installs, `make db-up` and `make local-db-migrate`, use the existing private local profile:

```sh
uv run --env-file .env.local arbit-worker live-inspect --season 2026 --week 8 --events 401873023 401873026
uv run --env-file .env.local arbit-worker sources-status
uv run --env-file .env.local arbit-worker sources-verify
uv run --env-file .env.local arbit-worker live-replay --observation <play-page-observation-hash>
uv run arbit-worker assets-check
```

`live-replay` accepts all page observation hashes for one complete game, plus optional `--previous <hash...>` for a previous complete set. Both replay and verification read stored objects and PostgreSQL only, with zero provider requests. A request to replay incomplete/mixed-event page sets fails. Do not confuse a manifest hash with a body hash.

`live-inspect` requires the configured season and an explicit NFL week. Supplied event IDs must belong to that scoped scoreboard, be unique, and number at most eight. Without IDs it samples up to two completed games and one scheduled game. Before kickoff or for a postponed/cancelled game, play acquisition is explicitly not requested; this does not claim a successful empty play-feed response. Per-game failures remain safe partial results and make the command nonzero. Scoring periods and NFL weeks are different concepts.

`sleeper-sync` captures the full directory, current NFL state, and 24-hour add/drop trends (25 each). It prints counts/hashes/age evidence and read-only join totals, never source player names, member records or raw bodies. `sleeper-probe` is an explicit research command for two undocumented stats representations; HTTP 200 does not promote them into a supported live feed or FFA scoring source. Season disagreement in documented state is visible and makes overall sync unsuccessful without changing configuration.

All database commands reject production, non-loopback hosts and names outside `_local`/`_test`. `assets-check` needs no database, provider calls or media. M1e itself added no member endpoints. M2 now provides configured member auth/routes; the optional loopback operator boundary remains, and production requires complete secure OIDC.

## Acquisition, cache and freshness

`ARBIT_PUBLIC_SOURCES_PATH` defaults to ignored `data/public-sources`; content-addressed objects are in `objects/<sha256>` with private directory/file permissions. Original HTTP bytes, normalized JSON and observation manifests remain immutable. Additive schema `0005_public_sources` stores observations and current/refresh reservations; prior migrations are unchanged. Back up PostgreSQL and objects together.

| Resource | Minimum refresh interval | Implemented cached-read status |
| --- | --- | --- |
| Sleeper full directory | 24 hours | Stale once observation age reaches 24 hours or the last refresh failed |
| Sleeper state | One hour | Stale once age reaches one hour or refresh fails |
| Sleeper trends | 15 minutes | Stale once age reaches 15 minutes or refresh fails |
| Candidate weekly stats | 24 hours | Candidate only; stale at one interval or failed refresh |
| ESPN scoreboard/summary/play page | 30 seconds | Stale at one interval or failed refresh; no live-latency guarantee |

These are implemented local policies. The architecture's longer 48-hour/two-missed-interval serving thresholds remain proposals for later measured serving-policy tuning. The batch importer currently treats a missed refresh conservatively. `sources-status` exposes original observation timestamps, next-allowed times and safe last errors; reading it never renews freshness. No automatic supplemental/live scheduler is installed.

A row-locked reservation commits before source I/O. The directory limit applies across processes and persists even if the request fails or its outcome is uncertain. There is no force flag bypassing the daily limit. A five-minute reservation token fences late publication. A failed acquisition preserves the last good pointer with an error/stale flag; a first failed acquisition has no fabricated replacement. Publication saves immutable objects before a token-fenced database transaction; crashes can leave unreferenced private objects, and no destructive automatic cleanup runs.

Sleeper requests share an independent PostgreSQL gate (one request at a time, at least one second between starts). NFL calls share the existing combined ESPN gate (two seconds between starts) with FFA workers. HTTP errors retain safe status/Retry-After; the gate persists cooldowns/circuit state. Commands do not automatically retry failed resources or install background pollers. Do not run the older standalone per-instance research transports concurrently with automatic/provider-gated work.

Requests are allowlisted public GETs, with no environment proxy, credential, cookie, redirect or payload-reference following. Bodies cap at 32 MiB; strict finite/unique-key JSON caps depth 64 and nodes 2 million. The elapsed I/O budget is 30 seconds after address resolution; synchronous system DNS cannot be interrupted. Core plays cap at 20 pages/6,000 plays per game, with consistent event/count/page metadata, complete unique IDs and conflicting-overlap rejection. Bounds fail explicitly and preserve the last good source state.

## Identity, scope and replay

Sleeper rows preserve their original fields and missing values; D/ST/unknown records remain separate. Existing trusted GSIS/ESPN aliases provide read-only matches at a dated cutoff. Reused IDs, existing-entity disagreements and unresolved records never create or replace aliases. Trend activity does not establish FFA availability. The current directory hints join 40/121 owned athletes; NFLverse still resolves all 121. Additional bridging requires separately validated source evidence before affected model use.

ESPN scoreboard/summary scope must match requested year/season type/week where supplied. A play's own public NFL reference must match event, competition and play ID. Athlete/team references are parsed only from expected public scoped paths and never fetched, including private-host references. Source type IDs/text, scores, clock, periods, participants, multiple effects and point-after metadata remain distinct from fantasy scoring. A down of-1 is a measured unknown sentinel, retained as raw evidence and normalized to null. Missing scores/coordinates remain null.

Every play carries its play-page observation time through live reads and offline replay. A newer summary or another page cannot make older cached play content newer. Duplicate facts can confirm their own observation time without emitting a play change; older per-play evidence cannot undo a later correction. Explicit no-play observations cancel the effective play; omission from a later partial source is not a tombstone. Replay performs no fantasy arithmetic or persistent M6 serving/outbox publication.

Field points retain source yards-to-endzone and separate team frames. Turnover/multiphase/unknown positions cannot become an invented continuous route or stadium direction. Text/unknown fallback is deliberate. Actual active-game latency, live corrections and some game/play classes remain empirical M6 gates.

## Gridiron prerequisites

`config/gridiron-assets.json` is intentionally empty. Curated records require exact event/season/type/week/team/venue/neutral context, verified variant/pattern evidence and observation time, source/image metadata/checksum/dimensions/attribution, and a dated permission grant for the corresponding field/uniform uses. Unknown context, ambiguous matches, missing or expired permission selects labeled fallback.

A positive result is **`eligible_metadata`**, always `local_asset_ready=false`. It does not download, hotlink, decode, cache or serve an image. M6 must separately verify permitted bytes/media and serving behavior. Both [uniform](https://gridiron-uniforms.com/GUD/about.shtml) and [field](https://www.gridiron-uniforms.com/fields/controller/controller.php?action=main) pages require reuse permission. Patterns are now [verified from the site's pages](../research/gridiron-url-patterns-2026-10-31.md), and permission is held privately (OWN-015). A field not listed for a game is still only a candidate. No contact was sent. [Detailed prerequisites](../research/gridiron-prerequisites-2026-10-31.md).
