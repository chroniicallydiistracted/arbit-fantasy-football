# API and Integration Contracts

Version 0.1 · 2026-10-30 · Business-route design contracts. M1a implements `/health/live` and `/health/ready`; member business routes remain unimplemented until their authenticated slices. M1c adds optional loopback-and-secret operator-only `/internal/league/current`, `/history`, `/snapshots/{uuid}` and `/sync` GETs; [implemented contract and errors](../engineering/ffa-synchronization.md). M1d adds stored `/internal/league/nflverse/coverage` and `/internal/league/nflverse/players/{uuid}/stats?season=2026&week=1` GETs under the same boundary; [implemented source-read contract](../engineering/nflverse-ingestion.md). No token means no data routes; production remains blocked.

## Common rules

Same-origin `/api/v1` JSON API, authenticated opaque session cookie. User IDs/team bindings come from the server session, never a trusted client `teamId`. Administrators may inspect other teams through an explicit authorized route. Validate path, query and body with Pydantic; generate OpenAPI and the TypeScript client at runtime bootstrap. Handwritten client copies of wire types are prohibited. Large statistical downloads are authorized, paginated/streamed, and do not expose raw private provider files.

Times are ISO 8601 UTC; canonical IDs UUID strings; provider IDs opaque strings. Distinguish `season`, `seasonType`, `nflWeek`, `scoringPeriodId` and `matchupPeriodId`. Fantasy points/monetary bid values are decimal strings. Null means unknown/inapplicable as defined, not zero. List queries use bounded cursor pagination (`limit` default 50, maximum 200), stable sorting and `nextCursor`; filter semantics are documented per endpoint. Payloads include observation and generation times; a successful fetch is not proof the provider data itself is current.

Successful read envelope: `data`, `meta` (request ID, schema version, snapshot ID, as-of time, data status/limitations), and pagination where relevant. Recommendation records use [recommendation schema](../../packages/contracts/schemas/recommendation.schema.json); a [synthetic example](../../tests/fixtures/recommendation.example.json) illustrates it without actual FFA members or predictions. Configuration uses [league schema](../../packages/contracts/schemas/league-config.schema.json).

## Planned routes

| Method/path under `/api/v1` | Input / output | Authorization and consistency |
| --- | --- | --- |
| `GET /me` | Account, season/team binding, permissions and display preferences | Own session; no secret source credentials |
| `GET /league` | Metadata, validated rules, slots, support gaps, source freshness | Invited member; configured FFA only |
| `GET /league/teams` | Season teams/managers, needs and standings | FFA members; minimal necessary member info |
| `GET /front-office` | Own team, matchup, roster, standings and shared decisions | Own binding; one pinned snapshot |
| `GET /players` | Search/position/availability/archetype filters; paged summaries | FFA member; availability includes snapshot and timestamp |
| `GET /players/{id}` | Rich profile, history, utilization/depth, schedule, news, evaluations | Canonical ID; season/horizon/window explicit |
| `POST /comparisons` | Two–four canonical IDs + period/horizon; aligned metrics | Member; bounded scope; snapshot pinned |
| `GET /lineup` | Current roster, locks, shared evaluation, recommended legal lineup | Own team; objective query validated |
| `POST /lineup/scenarios` | Candidate assignment/objective + `expectedSnapshotId` | Own team; reject stale/illegal state; job if expensive |
| `GET /market/waivers` | Ranked, roster-specific add/drop options and availability | Own binding; freshness gate |
| `POST /market/trades/evaluate` | Own/partner player packages and horizon | Both teams in FFA; legal rosters/ownership checked |
| `GET /market/trades/opportunities` | Ranked feasible package evaluations for own team | Shared player values; no external submission |
| `GET /draft` | Full board, state source, own roster/next pick and recommendations | One FFA draft; active state freshness gate |
| `POST /draft/simulations` | Strategy, slot/options, seed and snapshot | Bounded job, own saved scenario |
| `POST /draft/manual-state` | Explicit fallback picks/corrections and revision | Authorized member/scenario owner; separate from authoritative state |
| `GET /live/games` | Scoreboard, FFA relevance, freshness | Members; official/provisional separate |
| `GET /live/games/{id}/plays` | Revision-aware timeline, cursor, participants, schematic fields | Full or own-roster filter; no inferred tracking coordinates |
| `GET /live/events` | SSE replay cursor with authorized event types | Session-bound; stream access revalidated on revoke/expiry |
| `GET /archive/seasons/{season}` | Verified results, records, Geller Cup history | FFA member; original rule version |
| `GET /methodology` | Model/source versions, evaluation summaries and limitations | Member-safe explanations, no private training rows |
| `GET /jobs/{id}` | State/progress/result URL/error | Job owner or administrator; no cross-user scenario leak |
| `PUT /me/preferences` | Display/watchlist preferences with revision | Own account; CSRF and origin checks |
| `POST /admin/sync` | Source/job type, idempotency key | Administrator; bounded refresh; no provider secrets in result |

Auth routes live under `/auth` (OIDC start/callback, session logout/invite redemption) and health under `/health/live` and `/health/ready`. Readiness checks DB/migration compatibility and configuration, not an upstream provider request on every health poll. No ESPN transaction endpoint is planned.

## Errors and asynchronous work

Use `application/problem+json`: `type`, `title`, `status`, `detail`, `instance`, `code`, `requestId`, and safe optional `fieldErrors` / `retryAfterSeconds`. Never include cookies, SQL, stack traces or raw provider bodies. Codes include `AUTH_REQUIRED`, `TEAM_BINDING_REQUIRED`, `FORBIDDEN`, `STALE_SNAPSHOT`, `RULES_UNSUPPORTED`, `PROVIDER_UNAVAILABLE`, `IDENTITY_UNRESOLVED`, `INVALID_LINEUP`, `RATE_LIMITED`, `JOB_FAILED`.

401 requires sign-in; 403 is authenticated but unauthorized; 404 conceals unauthorized object existence where appropriate; 409 handles stale scenario revisions; 422 handles invalid input; 429 includes Retry-After; 503 returns unavailable capability without losing unrelated cached facts. Missing/noncurrent analysis may return 200 with an explicit unavailable analysis section if the surrounding league view is valid; a request to compute blocked advice returns the specific error.

A bounded scenario accepts `Idempotency-Key` scoped to account and request hash, returns 202, `Location: /api/v1/jobs/{id}` and queued status, or the prior same-key result. A reused key with a different request returns 409. Job status is queued/running/succeeded/failed/canceled, with safe error and timestamps. Results bind snapshot/model/rules and become historical when invalidated.

## SSE contract

`id`: monotonically increasing persisted outbox sequence. `event`: `league.updated`, `draft.updated`, `game.play`, `game.corrected`, `analysis.ready`, `source.status`, `snapshot.required`. `data`: JSON containing schema version, entity, revision, occurred/observed time and authorized summary. Never put private secrets in URL query parameters or payload. Heartbeat comments every 20 seconds; clients use Last-Event-ID. Missing/expired cursor produces `snapshot.required`; refresh snapshot before applying incremental events. Duplicates are ignored by ID; corrections supersede earlier play revisions. On revoked session, close stream and clear private state.

## Internal interfaces

Core: `score(stat_line, rule_set) -> ScoreBreakdown`, `validate_roster(roster, slot_rules, lock_state) -> ConstraintReport`, and `resolve_identity(provider_ref, as_of) -> ResolvedIdentity | UnresolvedIdentity`. ScoreBreakdown includes per-rule Decimal contributions and unsupported-rule diagnostics; no adapter performs fantasy arithmetic.

Data: adapters return validated source records plus `SourceFetch` provenance, not shared mutable singletons. Worker: `enqueue(job_type, input_ref, idempotency_key, not_before) -> JobRef`; claim lease, heartbeat, fenced complete and retry/dead-letter are persistent. Model: `evaluate_players(context, feature_set, model_ref) -> EvaluationSet`; advisors receive that set and league constraints. The concrete typed signatures and table migrations are pinned in the first implementation plan and later vertical-slice plans; the API OpenAPI becomes the executable authority once generated.

## M1e operator-only source tools

M1e adds guarded local worker commands for supplemental capture, NFL source inspection, offline verification/replay and Gridiron prerequisite checks; it adds no member/business HTTP routes. [Command and source contracts](../engineering/supplemental-live-sources.md). Candidate/Sleeper points are never authoritative FFA totals; a canonical play's page observation time is separate from game-summary freshness. M2 still owns authentication and generated member contracts, M6 owns persistent Live events/SSE and rendering.
