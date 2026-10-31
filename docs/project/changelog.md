# Development Changelog

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
