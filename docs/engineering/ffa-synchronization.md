# Local FFA synchronization

Implemented M1c, 2026-10-30. The worker reads the public FFA league **1729878439**, configured season **2026**, and publishes complete canonical revisions to PostgreSQL. The API reads those stored facts. There is no member UI, member login, recommendation service or production deployment.

## Start locally

After frozen dependency installation and `make db-up`:

```sh
make local-env
make local-db-migrate
make local-sync
make local-sync-status
make local-api
```

`local-env` creates an ignored, mode-600 `.env.local` once and preserves an existing file. It contains local database/storage configuration and a random local operator token; it never prints the values. Each local command explicitly opts into that file. Other commands/tests do not implicitly load it. Never put the token in a frontend bundle or commit/copy the file into an artifact. The checked-in local PostgreSQL credentials are development-only.

`local-sync` performs one explicit refresh. An existing queued cooldown/retry remains scheduled; it prints `waiting_for_existing_job` rather than bypassing its due time. `local-sync-watch` runs a foreground worker: default five-minute refreshes, a 30-second schedule check, and a minimum allowed cadence of 60 seconds. Stop with Ctrl+C or SIGTERM. Due times and jobs survive restart; the process must be running to poll. This phase leaves no background service installed or polling after its smoke check. The fixed cadence is the normal-week mode; draft/live/kickoff-specific schedules are future slices.

Commands refuse production, non-loopback database hosts, and database names outside `_local`/`_test`. Synthetic fixtures still require `_fixture`/`_test` and do not create a full canonical league document. Migration `0002_ffa_sync` extends `0001_foundation` without editing it. Back up local PostgreSQL and `data/source-archives` together before schema/data experiments; never drop shared tables to reset a test.

## Read the stored league

`make local-api` binds to `127.0.0.1:8000` and disables proxy-header trust. With no operator token configured, only health routes are registered. With the local token, requests must also originate from an actual loopback peer; forwarded client headers do not establish access. Supply `Authorization: Bearer <local token>` from a trusted local operator client. Do not paste the token into chat, logs or browser application code.

| GET route | Result |
| --- | --- |
| `/health/live`, `/health/ready` | Process/schema readiness; no league facts |
| `/internal/league/current` | Canonical league, original capture/state/rule hashes, revision changes and current sync health |
| `/internal/league/history?limit=50` | Newest first, bounded to 1–100 revisions, previous ID and change summary |
| `/internal/league/snapshots/{uuid}` | An immutable stored revision in the configured season, with current source health |
| `/internal/league/sync` | Last attempt/confirmation, due time, pause/failure code and staleness |

All operator responses, including access/validation errors, use `Cache-Control: no-store`. Missing snapshots return 404; unavailable/unconfigured storage returns safe 503. Routes perform no provider HTTP calls and accept no mutations. `/api/v1/league` remains absent; production startup still fails until M2 invite-only OIDC/session/binding controls are implemented. Local operator inspection is not member authentication.

## Publication and lineage

Native ESPN IDs resolve to once-assigned internal UUIDs through exact aliases with evidence and validity times. FFA teams and fantasy matchups are scoped to the league/season. Athletes, NFL teams and D/ST units are distinct kinds; team affiliation intervals describe observed times, not invented transfer dates. Manager display names and owner relationships are retained; unused contacts/notification/first/last-name fields are discarded. These provider memberships do not bind an Arbit account.

A full document contains teams/managers, official standings, current rosters, all observed available players, eligibility/locks/injury state, matchups with explicit scoring/matchup periods and draft picks. Rule versions preserve normalized slot/lock/waiver/draft facts, both exact scoring rule sets and provider policy provenance. Unknown eligibility slot names are explicitly labeled. An unknown player kind, owner reference, NFL-team mapping or draft profile prevents publication. Missing draft profiles currently require an adapter/source follow-up; they are never inferred from a name or bare ID. NFL-team display metadata awaits a verified directory in M1d.

Player `official_current_points` requires an exact actual/source-0 weekly/split-1 block for this season and scoring period; projections and the ambiguous pool `appliedStatTotal` never substitute. Missing actuals remain null. Values are Decimal strings with the verified cent rounding. ESPN official totals remain distinct from reconstructed/model estimates.

First publication and changed scoring/lineup contexts require a completed-period audit. Its config, role-rule and lineup-context hashes must match the acquired league; only a successful nonempty player/lineup reconciliation is persisted. Unchanged definitions reuse immutable verification evidence. Preseason/new-season publication with no completed-period proof is deliberately blocked by this current gate; rollover needs an explicit validation design before adoption. Recommendations remain false even after verification. Eleven rare-category empirical gaps remain disclosed in the [scoring proof](../research/ffa-scoring-verification-2026-10-30.md).

All canonical aliases/rules/documents, current pointer, affiliations, outbox event, success state and lease completion commit together. A failed publication rolls back those writes. Captures may remain quarantined for review. A repeated full business state updates its confirmation time without producing another revision/outbox event. Changed state creates an immutable revision; changed completed matchup totals or completed draft picks are labeled corrections. Reverting to an earlier business state creates another revision. No member push/SSE consumer or model invalidation system is shipped yet.

## Capture storage and replay

Private `data/source-archives/<SHA256>.json.gz` files contain typed parsed/redacted acquisition facts, original HTTP body receipts and, on first/new-rule verification, the safe audit report. These are not original HTTP byte archives or a full completed-week scoring-input archive. The address is the checksum of uncompressed serialized content; HTTP body hashes remain separate. Files publish atomically, use restricted permissions, and existing objects are verified rather than overwritten. Reads verify checksum/schema and bounded decompression (32 MiB); symlink/path escapes and oversize captures are rejected. Store the directory on a private local filesystem; no static route serves it.

A new file is durable before its manifest is registered in PostgreSQL. A crash can leave an unreferenced private file; this phase does not automatically delete such artifacts. A registered captured/quarantined input can be reviewed/replayed after a compatible adapter fix. Already published/unchanged captures always resolve to their original snapshot without promoting it or refreshing source age:

```sh
uv run --env-file .env.local arbit-worker sync-replay <known-manifest-hash>
```

Replay makes no provider requests. It re-runs canonical publication when needed and reuses stored scoring evidence; it does not independently re-fetch or recompute a completed-week scoring audit. The previous scoring slice separately archives/replays completed-week raw-stat inputs. Restore the database and private archives together; arbitrary external paths/unregistered captures are not accepted by this CLI.

## Failures, retries and freshness

One active sync job per season is enforced in PostgreSQL. Workers claim only `espn.sync` jobs, heartbeat every ten seconds against a 120-second lease, and fence capture registration, publication, success and failure writes. A replaced/expired worker cannot publish or overwrite another worker's health. A final lease check rolls back a transaction that outlives its lease. Five exhausted/crashed attempts enter a 15-minute recovery delay before automatic scheduling can start another job.

All automatic acquisition and scoring-audit requests share a PostgreSQL gate in the same application database/schema: concurrency one, at least two seconds between starts, persisted Retry-After cooldown and a circuit after three transient failures. No SQL transaction spans HTTP; a session advisory lock is explicitly released before connection reuse. Each existing HTTP request remains bounded by its response/deadline rules. Research `espn-inspect`, `espn-endpoints` and `espn-score-audit` are separate explicit manual tools with their existing per-instance budget: do not run those alongside automatic polling as if they shared the database gate.

Transient network/5xx/429/drift/incomplete data retries use persisted five-second exponential delay with jitter, cap the ordinary delay at 15 minutes, and honor longer Retry-After. Authentication or unsupported-rule/reconciliation/mapping failures pause automatic scheduling. Check safe `error_code`, visibility/schema/rule evidence, then explicitly run `local-sync` after correcting the condition. It resumes a paused source but cannot jump an active retry. Unexpected database failure leaves work recoverable by its durable lease.

The last complete snapshot remains readable. Source is stale after 15 minutes since acquisition start/confirmation, or if timestamps are in the future; a failed refresh is degraded even before that limit. Replay and publication time cannot make an old observation fresh. Current source reads span a window; stable bracketing detects observed context changes, but cannot prove atomic source state or rule out silent omissions/change-and-revert behavior.

[Live evidence](../research/ffa-sync-live-2026-10-30.json), [handoff](../project/handoffs/2026-10-30-durable-ffa-sync.md), [plan](../superpowers/plans/2026-10-30-durable-ffa-sync.md).
