# Handoff — 2026-10-30 — Durable canonical FFA synchronization

## Delivered scope

Owner authorized the next M1c phase after actual scoring verification. This slice connects the existing public reader and shared exact scorer to persistent canonical facts, private captures, durable synchronization and protected local operator reads. [Plan](../../superpowers/plans/2026-10-30-durable-ffa-sync.md), [operator/behavior contract](../../engineering/ffa-synchronization.md), [safe live receipt](../../research/ffa-sync-live-2026-10-30.json).

- New immutable migration `0002_ffa_sync`; prior `0001_foundation` unchanged. Exact native aliases use once-assigned UUIDs, typed kinds, league/season scopes for fantasy teams/matchups, and observed affiliation intervals. No name matching or guessed D/ST/team IDs.
- Full immutable FFA documents preserve manager/team memberships, standings, rosters/available pool, locks/eligibility/injury state, matchups and draft. Unused personal/contact fields are discarded. Native manager membership does not bind an Arbit account.
- Immutable full rule versions contain normalized slots/policies, exact athlete/DST scoring sets and provider provenance. New scoring/lineup contexts require completed-period verification with matching config/role/context hashes. Verified unchanged contexts reuse evidence. Missing actual points remain null; projections/ambiguous pool totals never become actuals.
- Private bounded content-addressed parsed/redacted archives retain acquisition facts, original body receipts and new-rule audit reports. Artifact hashes differ from source-body hashes. They do not archive full completed-week raw scoring inputs; the prior scoring slice does that separately. Canonical replay is offline and cannot refresh or promote an already processed capture.
- Atomic publication resolves aliases/rules/documents, current pointer, affiliations, outbox and job completion. Last good state survives failure. Unchanged observations only confirm freshness; changed and corrected business states append revisions.
- Durable due times, one active source job per season, type-filtered claims, heartbeat/fencing, bounded retries with jitter/Retry-After, exhaustion delay, permanent pause, and shared PostgreSQL request pacing/circuit. Standalone manual research commands retain per-instance pacing; do not mix them with automatic polling.
- Optional loopback-plus-secret operator GET routes serve stored facts/history/status with no-store. Default API remains health-only, `/api/v1/league` absent, production startup blocked. `make local-env` creates an ignored private profile once; no secrets printed. Invite-only OIDC/member UI remain M2.

## Actual live proof

Code `53477de`, UTC 2026-10-31 approximately 05:57–05:58 (local 2026-10-30): `make local-env local-db-migrate`; `uv run --env-file .env.local arbit-worker sync --once` succeeded. FFA contained **8 teams, 8 managers, 132 owned, 923 available, 128 draft picks, 56 matchups**, current scoring period 8. PostgreSQL has 1,159 canonical entities/aliases, one rule version, one scoring-verification record and one full snapshot/outbox event. All 46 definitions supported; **797 played player-games + 121 provider-zero entries; 56/56 lineups; 0 mismatches/errors** across completed weeks 1–7. Eleven nonzero empirical gaps remain disclosed.

Second explicit live refresh returned `changed:false` and the same snapshot, with a second capture/updated confirmation. The bounded automatic-worker smoke and final corrected-code refresh likewise returned unchanged; four successful captures retain one snapshot/outbox. `sync-replay` of the first capture returned `offline:true,replayed:true,changed:false` and the same original snapshot without moving freshness. Private archives remain under ignored `data/source-archives`; no names, tokens, cookies or provider bodies are committed.

Bounded real HTTP smoke: ready/current/history/sync each 200/no-store with local operator authorization; missing authorization 401/no-store. The API process was then stopped. Worker does not keep polling; `make local-sync-watch` is an explicit foreground command. PostgreSQL remains healthy with actual local state, and `.env.local` remains private/ignored. No provider writes, hosting, push, merge or remote deployment.

## Verification and review

Pre-review full `npm exec --yes --package=node@24.22.2 --package=pnpm@12.16.1 -- make runtime-check`: exit0, **312 tests**, Ruff/format, strict mypy across 41 sources, AJV and foundation checks; real isolated PostgreSQL integration included. Focused RED→GREEN tests cover capture corruption/size/privacy, stable typed/scoped identity, mapping/rules rollback, concurrent/no-change publication, corrected history, old replay, final lease expiry, heartbeat/replacement, persisted retries/pause/exhaustion/circuit, unrelated job isolation and API token/peer/no-store failures.

One fresh whole-branch review found no Critical issues and three actionable edge cases. Provider decimal overflow could terminate the automatic worker; malformed DEFLATE could escape the replay error boundary; an already-published leased replay used an earlier clock sample. The latter two were regraded Important against the promised recovery/fencing contracts. All three received observed failing regression tests followed by fixes and a fresh full check: **316/316 tests, Ruff/format, strict mypy across 41 sources, AJV and foundation validation, exit 0**. No Important findings or minors are deferred. No second reviewer was dispatched; the fixes are backed by those regressions and the green complete suite.

The additive migration also passed a real upgrade test with existing v1 snapshots, queued jobs and outbox preserved. A bounded `sync --watch` completed an unchanged due refresh and stopped cleanly on SIGTERM. Final corrected code is `8db1af8`; the final safe receipt records its unchanged live refresh and protected HTTP 200/unauthorized 401 check at UTC 06:07:36, separately from the initial source/verification captures. All four source captures resolve to the original full snapshot; replay after the final refresh again preserved confirmation time.

Review rulings, in the order made:

1. Member OIDC/bindings/models/UI/deployment stay in later approved milestones; this is the local data phase. Cost if wrong: later product delivery remains required.
2. Cross-provider reconciliation/backfill follows this source-native slice in M1d. Cost if wrong: statistical/historical joins are not ready yet.
3. OS-account takeover is outside the trusted local-operator boundary; ordinary corruption/path input still fails safely. Cost if wrong: an account compromise can modify local files/database.
4. Final documentation receives author/artifact validation without a second reviewer. Cost if wrong: prose has weaker independent review than code.
5. Live proof relies on the root agent's actual HTTP/database checks and hashed receipts; the reviewer intentionally avoided private data/network calls. Cost if wrong: live results are not independently duplicated.

## Operational limits and next stage

This is a verified local data slice, not completion of all M1 or a released product. Automatic normal-week polling is implemented; draft/live/kickoff-adaptive schedules, production worker deployment, member sessions/bindings, SSE consumers and model invalidation are later slices. Unknown owner/player/team/draft profiles or new unverified rules fail closed. Missing draft profiles need bounded source enrichment; no inference. Current new-season gate needs completed-week proof, so preseason/rollover requires an explicit validation design. NFL-team display metadata and statistical cross-provider mappings are not yet verified. Source bracketing cannot prove atomic state or eliminate silent provider omissions.

Next executable milestone: **M1d nflverse statistical foundation** — audit official datasets, real 2026/historical schemas/coverage/publication metadata/licenses, create versioned manifests and immutable sample reload, and join verified GSIS/ESPN identities with observation cutoffs. Preserve the single FFA scorer and do not enable projections/recommendations before normalized statistics and temporal/model validation. Then finish M1e supplemental/live source research and M2 member authentication/application shell. Gridiron links remain optional pending owner availability; they do not block M1d.

Branch `codex/m1c-durable-sync`, based on `95d8f14`; local commits only. [Status](../status.md), [issues](../known-issues.md), [requirements](../../product/requirements.json) and [changelog](../changelog.md) reflect scope and remaining gates.
