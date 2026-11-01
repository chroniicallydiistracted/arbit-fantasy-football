# Development Changelog

## 2026-10-31 — Live capture and animation scope

- Added private raw copies of every response the live lane reads, adding no requests, with a 5 GiB limit and failures that never reach the feed (OWN-020, R-030). The worker was restarted with it at 2026-11-01 06:23 UTC; 553 backend tests and all static checks pass.
- Measured the owner's sprite sheet and tested it on one real play in scratch: 6 poses recolored, attractive stills, stepped motion. The owner chose the sprite look (OWN-022). Six test frames show upright and falling poses can come close, while a flat ground pose isn't good enough yet. No application code changed.
- Owner scoped animation to what is relevant to each play (OWN-021). Spec documents now describe labeled 3D re-creations of the players ESPN names and the ball, replacing the dashed schematic and the 600–1800 ms sequence limit (ENG-023).

## 2026-10-31 — M2 source and agent policy correction

- Recorded live-NFL-game/PBP-only Sleeper scope and GPT-6.1 Sol-only subagent policy. Removed fantasy normalization/mapping and disabled former acquisition commands before cache/network reads; current status/verification excludes retired captures. Historical evidence remains intact.
- Began M2 under the accepted invite/OIDC/member-binding and React/PWA architecture; no provider project, client or external service provisioned.

## 2026-10-31 — M1e supplemental and live sources

- Added immutable public observations and additive 0005 refresh reservations, safe fixed HTTP bounds, daily cross-process Sleeper cache and last-good/fenced publication. Verified directory 12,229/state/add/drop and two explicit candidate stats representations; direct identity hints join 40/121 owned athletes without alias/ownership mutation.
- Verified scoped ESPN scoreboard/summary/core-play sources and canonical participant references across four completed games/842 plays including overtime/tie; pinned 20 factual provider types. Added pure revision-aware offline replay with explicit no-play/missing/unknown behavior and no fantasy arithmetic or route tracking.
- Fixed all four Important independent-review findings with observed failing regressions: per-play page observation time, season-type scope, individual play reference scope and safe malformed-reference recovery. Full check 409 tests plus Ruff/mypy/AJV/foundation passed.
- Implemented exact-context/variant/dated-permission metadata gate and empty Gridiron manifest; fresh uniform/field terms and 2026 navigation verified, no media/contact/grants. Current active/corrected Live cases, source hint gaps and longer serving-threshold tuning remain explicit.
- Final offline proof 25 observations/66 unique objects and repeated actual 197-play capture replay with zero changes/provider calls. FFA snapshot/roster/entity/alias counts unchanged, no active refreshes. No UI, automatic supplemental scheduler, model, recommendation enablement, push or deployment. [Audit](../research/m1e-source-audit-2026-10-31.md), [guide](../engineering/supplemental-live-sources.md), [handoff](handoffs/2026-10-31-supplemental-live.md). M2 is next.

## 2026-10-31 — Comprehensive NFLverse foundation

- Imported the full published catalog: 1,140 logical files across 28 families, 1,087 tables/11,973,952 stored rows and 53 archive-only originals/metadata/reference files. Preserved all columns, historical/legacy/subtype/summary variants, raw data ZIPs and explicit benchmark/diagnostic distinctions. Alternate format mirrors remain cataloged; model ZIPs are excluded as non-observations.
- Added immutable source/Parquet objects, schema/coverage/terms manifests, additive 0003/0004 migrations, durable staged acquisition/publication and source/catalog ordering. All 786 hashless identities passed a second complete catalog check; offline verification covered 1,140 manifests/1,157 unique data objects without network calls.
- Verified exact GSIS/ESPN joins for 121/121 owned athletes and protected canonical-player HTTP reads. Two athletes without weekly rows remain missing. Backed up and closed five later conflicting supplemental aliases with original rows/reports/UUIDs/FFA facts preserved.
- Fixed all five Important independent-review findings with observed failing regressions; full check passes 357 tests plus Ruff/mypy/AJV/foundation. One uppercase-suffix compatibility minor affects zero selected files and remains deferred.
- Added resource-limited nested RDS fallback and explicit nested-history JSON preservation; no R runtime, model execution, member access, recommendations or deployment enabled. M1e supplemental/live-source proof is next. [Audit](../research/nflverse-data-audit-2026-10-31.md), [guide](../engineering/nflverse-ingestion.md), [handoff](handoffs/2026-10-31-nflverse.md).

## 2026-10-30 — Durable canonical FFA synchronization

- Stored exact scoped ESPN UUID aliases/observed affiliations, immutable full policies and scored rule versions, complete league documents and correction history through new `0002_ffa_sync` migration. First/new scoring-lineup contexts require completed ESPN reconciliation; recommendations remain disabled.
- Added private bounded immutable capture archives, offline replay, no-change confirmations, atomic leased publication/completion, durable schedules/retries/pause/freshness and a shared PostgreSQL request gate/circuit.
- Final independent review fixes contain extreme Decimal inputs and corrupt gzip, and recheck leased replay completion; 316 runtime tests plus static/contract/artifact checks pass.
- Added optional secret-and-loopback local reads with no-store, guarded real sync commands and private local profile setup; default API stays health-only and production/member access awaits M2.
- Live ESPN → PostgreSQL → HTTP proof: 8 teams/8 managers, 132 owned/923 available, 128 picks/56 matchups; 797 played games/121 provider zeros/56 lineups reconcile with zero issues. Four refreshes, including automatic-worker and final corrected-code checks, retain one snapshot/outbox; old replay does not promote or refresh. [Evidence](../research/ffa-sync-live-2026-10-30.json), [guide](../engineering/ffa-synchronization.md), [handoff](handoffs/2026-10-30-durable-ffa-sync.md).

## 2026-10-30 — Actual FFA scoring mapping and verification

- Mapped all 46 fetched scoring definitions into the shared exact engine, including D/ST role overrides, allowed-point/yard bands and disjoint field-goal ranges; corrected reference-document ID/contribution errors with pinned provenance.
- Added strict actual-game scope, explicit sparse-counter/no-game-zero handling, per-rule/player/lineup reconciliation and `espn-score-audit`.
- Final reviewed live proof: 797 played player-games +121 provider-zero entries, 56/56 lineup totals across periods 1–7, zero discrepancies. Nine private parsed-input archives replay identical results; eleven rare nonzero categories remain empirically unobserved and disclosed.
- Fixed independent review's cancelling zero-rate contribution and extreme-decimal failure paths; included the tested unbounded-range adaptation. Full runtime check passes 275 tests plus quality/contract checks. Recommendations remain disabled; no dependencies/migrations/provider writes/push/deployment.

## 2026-10-30 — Complete audited ESPN endpoint routing

- Closed the gap between the broad audit and the initial core reader: all 68 recognized successful variants across 19 allowlisted families are callable through the guarded provider client.
- Added corrected player/news/pro-schedule/standings routes, historical period reads, transactions, boxscores/live/rankings/cards, NFL core/site/web metadata and PNG assets. HTTP-success shells remain explicitly limited/metadata-only.
- Added `arbit-worker espn-endpoints [--live]`, full request reconstruction/preflight and safe partial evidence on failure. All 81 audit cases accounted; 13 intentionally excluded.
- Fixed three Important independent-review findings with RED→GREEN tests: nested capability loss, contradictory optional scope, and inconsistent audit outcomes. Final full runtime check: 209 passing tests and all quality/contract checks; post-review live run: 68/68 pass, zero failures.
- Owner explicitly requested proceeding to exact scoring mapping/reconciliation before recommendations. Reference stat-ID and appliedStats descriptions conflict with actual football data; normalization will use pinned provenance and observed source math.

## 2026-10-30 — M1b public ESPN reader

- Owner authorized development using verified public access and excluded message boards; corrected the obsolete 401 blocker and cloned the pinned reference under ignored `.references`.
- Added GET-only public HTTPS transport with response/timeout/pacing bounds, safe typed errors and Retry-After; observed league/player contracts retain exact settings and unknown data.
- Added ownership/context guards and full availability pagination through an empty terminal page; provider short-page caps do not silently truncate inventory. Historical roster/current-availability combinations are rejected.
- Added `uv run arbit-worker espn-inspect`, reporting safe counts/source evidence without a database or credentials. Fresh live proof: eight teams, 132 owned, 923 available, 46 scoring items, 128 picks, 56 matchups; seven requests.
- Full runtime check passes 110 tests plus Ruff/mypy/AJV/foundation checks. Contracts also validate the earlier real combined response and four available pages. Artifact validation excludes ignored local captures/reference checkouts while retaining project checks.
- Canonical identities, actual scoring reconciliation, durable production sync, member auth and UI remain future work. No dependency, provider setting, remote branch or deployment changed.

## 2026-10-30 — Public ESPN capability audit

- Owner enabled public league viewing for testing; no final access policy selected.
- Reviewed every tracked file at pseudo-r reference commit 097c42f; tested all 21 documented views/nine client request families through 81 cookie-free GET probes.
- Verified core data access, actual FFA settings, 923 available players, exact 132-player roster ownership match, 128 picks, 389 unique transactions and an NFL PBP sample.
- Recorded field/domain/filter discrepancies, explicit communication denial, legacy HTML responses and full sanitized request/checksum evidence. Raw bodies remain ignored local research data; no runtime code, dependencies, cookies, provider writes or production sync changed.

## 2026-10-30 — M1a runtime/core/snapshot implementation

- Recorded owner architecture/stack approval, dependency authorization and explicit UX/UI quality requirement.
- Added pinned Python/pnpm workspaces, frozen lockfiles, PostgreSQL image and reproducible local/check commands.
- Implemented fixed FFA config, temporal identities, exact rule-based scoring, migrations, atomic snapshots/outbox and lease-fenced durable jobs.
- Added synthetic-only worker composition and health/readiness-only API; no private data routes or production auth bypass.
- Verified 45 tests after review, including real database concurrency/retry/fencing/correction cases, isolated-schema migration/readiness and nonblocking exhausted-job cleanup. Fresh-schema standalone CLI and actual loopback HTTP smoke passed.
- Added runtime CI and updated documentation. Final branch review/verification details are in the M1a handoff. No real FFA access, frontend UI, model, push or deployment is claimed.

## 2026-10-30 — Initial planning foundation

- Preserved owner brief unchanged and recorded FFA league 1729878439 / season 2026 / portable local-first preference.
- Prepared product/feature requirements, 57-item traceability, system/data/API/model/design specifications and four proposed ADRs.
- Added cross-provider agent entry point, review/plan/implement/validate/document/handoff standards, validation guidance, operational runbook and templates.
- Defined dependency roadmap through Archive and integrated release, plus concrete first runtime/core/snapshot plan.
- Added initial contract schemas, synthetic recommendation example, semantic design tokens and responsibility-based repository scaffold with local/CI artifact checks.
- Researched primary provider/technology sources; recorded unauthenticated FFA settings 401 and one public ESPN completed-game summary 200. No private credential, provider write, paid hosting or product runtime was created.
- Verified foundation artifacts and nine rejection cases; fresh builder review found no material planning gaps. Initialized local Git on main without commit/remote; secrets/data/cache ignore checks passed. Actual evidence and remaining runtime limits are in the dated handoff.

## 2026-10-31 — M2 member application

Implemented invited OIDC accounts, opaque sessions, approved manager bindings, administrator access controls, generated contracts and the responsive Front Office/PWA. Added player search/drawer/watchlist/themes, historical/null/source handling, private-safe offline/update behavior and populated migration preservation proof. Google selected; real private client/member acceptance remains open. No external provisioning or deployment. [Handoff](handoffs/2026-10-31-member-application.md).

M2 final validation: 453 backend / 14 client tests and 7 Chromium scenarios pass after the Sol review’s account-switch, apostrophe-search and fixture-invitation fixes. No real Google/member login is claimed.

## 2026-10-31 — Private Google configuration prepared

Moved the owner-provided ignored configuration into root `.env.auth.local` and set mode 600. Verified Git exclusion, complete real-OIDC configuration, unauthenticated member boundary and local database readiness without exposing credentials or making provider calls. Actual Google/member sign-in remains unverified.

## 2026-10-31 — First-name manager assignment labels

Owner confirmed the real first-administrator Google/binding/Front Office flow. Manager choices now prefer verified ESPN first names plus team context, with handle fallback/disambiguation. Live sync populated eight first names and preserved all manager IDs/approved bindings. Original captures remain compatible; unused surnames/email/notification fields remain excluded.

## 2026-10-31 — Design reset and real-time platform

Owner decisions OWN-013–017 recorded. Replaced the generated-looking interface with an officiating-and-broadcast character, removed all slogan copy, and added `pnpm check:design`. Added `arbit-worker run`, migration `0007_realtime`, NFL team directory and schedule, live game state and play revisions, per-source freshness, a session-bound SSE stream, a Live scoreboard and plays, and per-device sessions. Fixed from real data: float noise in official totals, pregame 0–0 scores, standings in provider order, roster in provider order, data age measured from last change instead of last confirmation. Corrected stale documents. Verified on a restored copy, then applied to the running app on 2026-11-01 04:26 UTC as systemd user services. [Handoff](handoffs/2026-10-31-platform-reset.md).

## 2026-10-31 — Live prerequisites

Owner accepted the design (OWN-018) and moved Live ahead of M3 (OWN-019). Verified Gridiron URL patterns and publication timing, and stored week 8 art privately. Measured how much of a play ESPN's feed supplies. Recorded 19 prerequisites and a single-play quality gate for animation. No application code changed.
