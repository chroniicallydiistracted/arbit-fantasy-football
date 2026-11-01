# Arbit Data Architecture Specification

Updated 2026-10-31 · Accepted architecture; implementation status is explicit below. Source capability evidence: [research register](../research/source-register.md).

## Source authority and boundaries

| Source | Authority | Planned inputs | Limitations and decisions |
| --- | --- | --- | --- |
| ESPN Fantasy | FFA league truth | Settings/scoring, slots/eligibility, teams/managers, rosters/ownership, matchups/standings, draft, free agents/waivers, transactions where available | Unofficial, mutable interface; private access may need server-side cookies. Completeness/pagination and permission must be demonstrated with FFA, never inferred from one successful request |
| nflverse | Primary NFL statistical foundation | PBP, player/team weekly stats, schedules/results, rosters/IDs, snap counts, depth, NGS, advanced charting where covered | Dataset-specific schema, publication times, coverage and terms; not a guaranteed real-time feed. In-season features must not use data published after the prediction cutoff |
| Sleeper | Relevant NFL live games and play-by-play only | Only individually verified eligible game/PBP routes | Owner excludes all fantasy data, directories/crosswalk hints, trends, projections, rankings and fantasy stats/scoring. No eligible route is currently enabled |
| ESPN NFL | Live NFL context | Scoreboard, event summary, drives/plays, boxscore, participants and scoring events where supplied | Unofficial; fields/types/coverage vary by event. One completed-game summary was observed, not a live reliability guarantee |
| Gridiron | Intended fields/uniforms | Team/season/game-specific images and variant metadata | [URL patterns verified](../research/gridiron-url-patterns-2026-10-31.md); permission held privately, personal use only (OWN-015). No API; week 8 art is stored privately, not yet integrated |

A source conflict never silently overwrites authoritative FFA facts. Retain both observations with source/time and expose a discrepancy. ESPN fantasy totals remain official even when Arbit's reconstructed live scoring differs. nflverse historical corrections create new dataset versions rather than changing past model inputs in place.

## Canonical identity

Use internal UUIDs, with `(provider, entity_kind, scope, external_id)` aliases and effective dates. Preserve provider IDs as strings. `entity_kind` distinguishes athlete, NFL team, fantasy team, and defense/special-teams unit; a D/ST is not a human player. GSIS/ESPN/Sleeper IDs are aliases, not a universal primary key. An NFL player can change team within a season; team affiliation is dated.

Reconciliation order: verified provider crosswalk → exact trusted alias → curated deterministic evidence (name, position, birth date, team history) → unresolved queue. Fuzzy/name-only matches may propose candidates but never auto-merge, especially suffixes, duplicated names, rookies, traded players and D/ST units. Store mapping method, evidence, reviewer, confidence, and validity. Unresolved identities can appear as raw provider records but are excluded from affected advice with a visible limitation. Alias corrections invalidate derived projections/joins and preserve the original mapping version for reproduction.

Fantasy team membership is season-specific and can include multiple managers. NFL game IDs and fantasy matchup IDs have their own aliases. Provider NFL week, scoring period, and matchup period are separately named; playoff rounds and multiweek matchups must not be collapsed into one `week` field.

## Storage layers and publication

1. **Raw:** immutable compressed provider body or Parquet download in local/S 3-compatible storage; metadata in PostgreSQL. Remove member fields not needed by Arbit and redact secrets before storage. Restricted raw league data is never a public URL.
2. **Normalized:** canonical identities, validated league snapshots, normalized games/stats/play revisions, and source health. Schema adapters are versioned.
3. **Analytical:** versioned Parquet partitions by dataset/season/season_type/week where applicable, point-in-time feature sets, model artifacts, evaluation reports. Never force timestamped depth charts into a fictional weekly source key.
4. **Serving:** indexed current league snapshot, player summaries, model results, recommendations, matchup projections, archive records; bounded payloads for web views.

Object manifest: dataset ID, provider URL, fetch time, provider publication time if known, ETag/Last-Modified when available, SHA-256, byte size, season range, schema/adapter version, terms/attribution, coverage and quality report. A release manifest pins all inputs for a model run. Checksum changes create a revision even when the URL does not change. Only a fully validated revision becomes the current pointer.

## Relational model

All timestamps are UTC `timestamptz`; the client formats the member's timezone. Use UUID primary keys except source-native identifiers stored as aliases. This is the target relational model; applied `0001_foundation` and `0002_ffa_sync` currently implement its snapshot/outbox/jobs, native identity/affiliation, immutable rules/captures/document and sync-health subset. [Implemented schema and behavior](../engineering/ffa-synchronization.md). Other rows remain planned.

| Table or group | Key constraints and relationships | Purpose |
| --- | --- | --- |
| `league`, `league_season` | One configured league, unique provider ID; season unique within league | Fixed FFA context; no tenant routing or multi-league onboarding |
| `rule_set`, `roster_slot_rule` | FK season; immutable content hash, effective time; unknown source rule IDs retained | All scoring/slot/waiver/lock/draft settings, support status |
| `manager`, `fantasy_team`, `team_membership` | Team unique `(season, espn_team_id)`; dated manager/team join | Co-managers, renamed teams, season history |
| `user_account`, `identity`, `session`, `invitation` | Identity unique `(issuer, subject)`; hashed session/invite tokens; expiries | Arbit access independent from ESPN cookies |
| `account_team_binding` | FK account and season membership; explicit administrator approval | Team personalization and delegated access |
| `athlete`, `nfl_team`, `defense_unit`, `entity_alias`, `team_affiliation` | Alias unique by provider/kind/external ID/effective range; no overlapping active mappings | Identity resolution without mixing D/ST and humans |
| `league_snapshot` | FK season/rules; source fetch, complete flag, content hash, publication revision | Atomic consistent view; only complete snapshots publish |
| `roster_entry`, `player_availability` | FK snapshot/team/player; one owning team per entity per snapshot; eligibility slots separate | Starters/bench/IR, free-agent/waiver/owned state and deadlines |
| `fantasy_matchup`, `standing` | FK snapshot/team; explicit scoring and matchup periods | Current FFA official matchup and standings state |
| `draft`, `draft_pick` | Draft FK season; pick unique `(draft, overall_pick)`; revision and source mode | Order, snake/other structure, trades of picks if configured, corrections |
| `nfl_game`, `game_alias`, `game_participant` | Unique source identity; schedule revision; FK dated teams/players | Schedule, status, final/provisional distinctions |
| `play_revision`, `live_stat_revision` | Unique `(provider, event_id, source_play_id, revision_hash)`; tombstones | Corrected, canceled and late plays/stats; no destructive update |
| `dataset_manifest`, `source_fetch`, `source_health`, `mapping_review` | Immutable fetch identity and processing state | Provenance, drift/failure tracking, reconciliation queue |
| `feature_set`, `model_run`, `evaluation_report` | Immutable input manifest/rules/code versions; FK artifacts | Reproducible point-in-time model runs |
| `player_evaluation`, `recommendation` | FK model/run/snapshot; horizon/objective; invalidation and expiry | Shared serving intelligence, reason/evidence records |
| `job`, `outbox_event` | Unique idempotency key; due time/lease/fencing token; ordered local sequence | Durable compute and at-least-once notification |
| `watchlist`, `saved_scenario`, `user_preference` | FK account; scenario references snapshot and rules | Member-created working context |
| `season_result`, `league_record`, `championship` | FK season/teams; unique version and confirmation audit | Final history and Geller Cup; corrected by append-only revision |
| `asset_manifest` | Source URL/hash, kind, season/game/team, variant, permissions/attribution, verified status | Known field/uniform selections and fallbacks |
| `audit_event` | Actor/time/action/entity and redacted diff | Administrative bindings, corrections, imports and releases |

Index serving queries by season/snapshot/team; identities by aliases; plays by event and normalized sequence; jobs by status/next-run time; recommendations by team/horizon/run. Large statistical facts remain Parquet; materialize only needed aggregates. Use Decimal for scoring and JSON numbers only where precision is demonstrably safe; the API transmits fantasy point values as decimal strings.

## ESPN ingestion and synchronization

M1b implements `EspnReader.fetch_league_snapshot(season, scoring_period=None)` for the fixed FFA league: public combined settings/team/roster/matchup-score/draft/status reads, complete available-player pagination, and a bracketing context check. It returns an `EspnAcquisition` of provider facts and source receipts, never a canonical `LeagueSnapshotCandidate`. See the [implementation plan](../superpowers/plans/2026-10-30-public-espn-reader.md) and [operator command](../engineering/local-development.md). The source is public and cookie-free; message boards are outside scope. All 68 useful/diagnostic successful audit variants across 19 route families are now wired through `EspnClient.fetch(Endpoint, EndpointOptions)`: individual historical-period reads, transactions, cards, corrected news/pro-schedule/standings routes, NFL core/site/web reads and PNG assets. [Coverage and proof](../research/espn-endpoint-coverage-2026-10-30.md). Source retrieval is separate from canonical normalization/product presentation; absent sections remain limited or metadata-only.

The implemented transport uses fixed-origin HTTPS GETs, no redirects/environment proxies, a 15-second elapsed I/O deadline across TCP attempts after DNS, TLS, writes, headers, body and chunk framing (system DNS itself is not interruptible), an 8 MiB body cap, finite exact Decimal JSON parsing, safe errors and Retry-After hints. Each transport serializes requests with at least two seconds between starts. It does not retry automatically. This is a manual, single-process acquisition path: a shared cross-process limiter, provider-aware durable retries, conditional requests, source health and scheduler remain required before concurrent polling.

Availability advances offsets by the actual number returned until an empty page, with at most 20 page requests. Duplicate IDs, incorrect statuses, owned overlap, scope mismatches and detected changes to settings/period/roster/locks/draft fail the acquisition. Historical rosters are rejected because the current player pool cannot establish past availability. Source observations span a capture window; changes that occur and revert between observations, or provider omissions without metadata, cannot be ruled out. This is not an atomic provider snapshot or an advice-readiness claim.

The implemented M1c canonical synchronization flow is: acquire a season-specific lease → fetch all required views/pages → store redacted immutable response manifests → validate required sections and exact configuration → reconcile identities → stage a candidate snapshot → verify ownership and roster invariants → publish in one transaction → enqueue invalidations and outbox event. Paginate/filter the entire available-player universe; top-50 results cannot stand for all FFA free agents. If data changes across pages, retry a bounded reconciliation pass and mark uncertain results instead of publishing an inconsistent roster.

Detect acquisitions, releases, trades, lineup changes, waivers, matchups, settings and draft changes by diffing published snapshots; transaction logs are supplementary, not the only source. Do not infer a successful waiver transaction from a trending-player feed. Unknown scoring or slot IDs fail the rules-support gate and block affected calculations while other league facts remain visible.

No season inference from the machine date: configured season is 2026 until an explicit rollover workflow snapshots finals, updates configuration and bootstraps the new season. Observed settings, both normalized exact scoring roles, full policy provenance and eligibility/locks now persist in immutable rule/document versions. Actual 46-rule scoring reconciliation gates first/new scoring-lineup contexts. Cross-provider identity, optimization/model evaluation and member access remain prerequisites for advice. [Durable-sync contract](../engineering/ffa-synchronization.md).

## Polling and freshness proposal

Implemented normal-week mode: five-minute durable sync, stale after 15 minutes; one shared request at a time and two seconds between starts (≤30/minute). Retry due times have jitter/Retry-After; three transient request failures open a 60-second circuit, five job attempts enter a 15-minute recovery delay, permanent access/rule failures pause. Other adaptive modes in this table remain proposals. Standalone research commands retain their explicit per-instance budget.

These are Arbit schedules and user-facing staleness thresholds, subject to measured provider behavior and rate limits, **not provider guarantees**. One global provider limiter shares traffic across jobs and users. Initial ESPN host budget ≤60 requests/minute combined, concurrency ≤2; tune downward on 429s and record all request volume.

| Dataset/mode | Initial cadence | Mark stale / degraded after |
| --- | --- | --- |
| FFA settings and team metadata | At startup and every six hours; also before draft/scenario if changed | 12 hours; no new rule-dependent advice on unvalidated rules |
| Rosters/availability, normal week | Every five minutes | 15 minutes; availability actions require an on-demand shared refresh if older than 60 seconds |
| Near kickoff, waiver deadline or active fantasy matchup | Every 60 seconds when scheduled/active | Three minutes; label cached snapshot |
| Active draft | Every five seconds if endpoint/call budget proven; otherwise clearly labeled manual tracking | 15 seconds; suspend current-pick advice until resync |
| ESPN NFL scoreboard / active game summaries | Scoreboard every 30 seconds; selected active-game summaries every 15–30 seconds within host budget | 60 seconds since last successful fetch; show delay without claiming field-to-screen latency |
| Final NFL game reconciliation | At final, +1 hour, next morning and next correction cycle | Provisional until reconciliation; ESPN fantasy confirmation separate |
| nflverse datasets | Check manifest/checksum on relevant provider publication schedule; daily general reconciliation | Dataset-specific expected release plus one missed release window; show observation time as well as fetch time |
| Sleeper live NFL games/PBP | Disabled pending route verification | No fantasy directory, trend, state or scoring use |
| Gridiron approved asset manifests | Weekly and on explicit curation | Unknown variant remains unknown; never substitute a generic uniform as verified |

Offseason disables game/draft polling; scheduler uses configured season state and observed games rather than a hardcoded calendar. Poll due times have jitter. Backoff starts at five seconds, exponential up to 15 minutes with jitter; honor longer `Retry-After`. Cap normal attempts at five, then failed/dead-letter state for inspection. Repeated auth denial immediately marks credential action needed and stops tight retries. A circuit breaker limits outage storms. Current published state remains available with its age.

## Implemented NFLverse statistical foundation — M1d

The [full audit](../research/nflverse-data-audit-2026-10-31.md) records complete published catalog acquisition: 1,140 logical files/28 families, immutable originals and normalized Parquet, additive 0003/0004 schema, profiles/terms/source timestamps and exact canonical GSIS/ESPN joins. All 121 owned athletes resolve to GSIS; two have no observed weekly rows. NFL-team metadata is retained without guessed franchise/DST joins. Wider source ambiguities remain in review.

Per-file acquisition/publication uses durable leased jobs and last-good pointers. Hashless sources stage until a second source catalog confirms identity/size/revision; immutable proofs separately date confirmation. As-of reads require acquisition and confirmation by cutoff, while source/catalog ordering prevents delayed older work from replacing current data. A corrected historical download is not a historical publication vintage. No automatic source scheduler or model-feature promotion is installed. See [operator contract](../engineering/nflverse-ingestion.md).

## NFL statistical processing

Start with a measured dataset coverage inventory for past seasons and 2026; record missingness, revisions, types and licensing per dataset. Candidate features: efficiency (EPA, success, yards per opportunity), volume (snaps, attempts, targets, air yards, red-zone share), role stability, team pace/pass rate, defensive matchup, schedule and recent trends with sample weighting. Route/participation features enter in-season models only if their actual publication timestamp proves availability at that cutoff. Injury, news, weather and depth information need source-specific evidence, not an assumption that all exist in one dataset.

For each feature: define unit, denominator, window, minimum sample, missingness indicator, transformation version and earliest observable time. Joins use canonical IDs and temporal validity; aggregate at the right grain before joining to avoid duplicating receiving/rushing totals on PBP rows. Defensive opponent adjustments shrink small samples. Train/validate with chronological cutoffs; fitting transforms across all seasons before splitting is prohibited.

## Shared scoring and recommendation lineage

Normalize ESPN stat-category IDs into versioned scoring rules: linear rates, threshold/range bonuses, distance-dependent kicking, turnovers, fractional/negative points, defensive/team scoring, and slot eligibility as actually configured. Preserve unsupported rules verbatim, with a diagnostic code; do not assume PPR, K/DST, bench, IR, FLEX, or superflex settings. Use exact Decimal arithmetic and tested final rounding. Bonus expectations come from simulated stat lines/distributions, not `bonus(mean(stat))`.

M1c implements the actual FFA scorer adapter: fetched rates, 26 effective athlete rules and 46 D/ST rules with override 16 independent of lineup placement. Point/yard bands use raw 120/127 with source-indicator consistency checks; the under 100-yard range has an unbounded lower endpoint. Only exact actual/source 0, weekly/split 1, configured season/period and GP=1 blocks are recomputed. Known sparse additive counters have an explicit policy; absent maps/range totals remain unknown. Empty no-game official zeros are not verified stat cases. `espn-score-audit` checks per-rule contributions, scoped player references and historical active-lineup totals, brackets settings and keeps advice disabled. [Support/proof](../research/ffa-scoring-verification-2026-10-30.md) records empirical coverage, precise cent policy and replay provenance. Exact FFA rule versions are persisted by M1c. Cross-source semantic equivalence and feature/model validation remain future M3 work; upstream fantasy-point columns are not FFA totals.

A historical score uses the relevant season/rule version. Reconcile hand-verified game fixtures against ESPN totals including corrections, D/ST points allowed definitions and edge plays. PBP reconstructed totals are provisional because later boxscore corrections and categories can differ. Advice must carry snapshot ID, rule hash, feature-set version, model run, as-of cutoff, generated time, horizon, coverage and limitations. Changes invalidate by dependency: a lineup move affects that team's lineup scenario; a rules change affects all scoring-dependent artifacts.

## Live events and graphical projection

Normalize source event/play IDs, sequence, game clock/period, possession, down/distance, start/end field position where observed, participants, scoring category and revision. Keep provider text and raw type alongside canonical type. Support pass, rush, sneak, sack, interception, field goal, PAT, two-point conversion, punt/kick/return, penalty/no-play, fumble and unknown. Plays can have multiple effects; a fumble return after an interception cannot be flattened into one positive gain.

Reconcile authoritative cumulative live stats by revision where present rather than indefinitely adding deltas from play text. Idempotent replays produce the same current scoreboard and fantasy attribution; corrections replace the effective revision and emit a correction event. A tombstoned/no-play event reverses prior derived effects. Deduplicate polling overlap and handle reordered events. If a provider lacks stable IDs, retain deterministic fingerprint plus ambiguity flags and do not claim reliable per-play scoring until validated.

A play re-creation can use line of scrimmage, observed endpoint and named participants, but PBP does not establish actual player routes, tracking coordinates or tackle location. The UI labels the motion as a re-creation and falls back to text when field position is missing. Orientation is canonical offense-to-defense and flips for display using possession/direction, including turnovers and overtime. Preserve separate game clock and wall time. Field/uniform manifestations include source, exact variant confidence and fallback; show weekly uniforms only when verified.

## Governance, retention and operations

Back up private league/user/identity/alias/archive data daily encrypted, with proposed 30-day rolling retention and monthly season snapshots; test restore quarterly. Raw private league snapshots: 30 days initially, retain sanitized season-final snapshots and rule versions for Archive; revisit after storage/terms review. Live normalized event revisions persist for season replay; outbox replay retention starts at 24 hours. Public datasets/artifacts follow their source terms and manifest retention needs. Account removal revokes sessions, removes unnecessary personal settings and anonymizes administrative audit attribution where appropriate, without erasing verified league results.

Raw live captures in `data/live-captures` stop at 5 GiB and are never deleted automatically; retention is set after the first real slate ([operations](../engineering/supplemental-live-sources.md#raw-live-capture), R-030).

Metrics: source latency and last success, expected-publication lag, coverage/mapping failures, drift count, job age/retries, poll volume, dead letters, scoring discrepancies, SSE delivery delay and model freshness. Drift quarantines only affected datasets and blocks affected models; no silent casting or replacement by zero. Administrative recovery supports bounded replay/backfill with dry-run row counts, immutable manifests, idempotency keys and audit records.

## Release checks for the data foundation

Prove FFA access and full settings/roster coverage; document every supported and unsupported rule. Check alias uniqueness and unresolved-player reporting. Run an identical snapshot twice without duplicates, reject partial pages, recover from 401/429/schema drift, and preserve the previous current snapshot. Verify point-in-time cutoffs, live correction replay and model provenance. Exact Gridiron links/permissions remain prerequisites for that asset integration. Private credentials are only needed if league visibility changes; current public source access is verified.

## Implemented supplemental/live source foundation — M1e

The [operator contract](../engineering/supplemental-live-sources.md) defines additive 0005 public observations/reservations, immutable original/normalized/hash manifests and exact read-only supplemental joins. Sleeper directory/state/trends are cached 24h/1h/15m; candidate stats remain research and no ownership authority is inferred. Direct hints cover 40/121 owned athletes; NFLverse remains 121/121.

M1e uses stricter stale-at-one-refresh-interval or failed-refresh behavior than the longer serving thresholds proposed above. Those table thresholds are future serving-policy proposals, not current batch-import guarantees. `sources-status` preserves observed/next-allowed times; no automatic supplemental/live scheduler is installed.

ESPN year/type/week and source event/competition/play scope are validated; embedded reference URLs are never fetched. Core-play athlete references enable exact native canonical lookup where provided. Every play retains its source page's observation time through live and offline replay; summary or other-page freshness cannot promote cached old revisions. Missing plays are not tombstones. Pure replay preserves explicit cancellations without calculating fantasy effects, publishing M6 effective-play state or emitting SSE. Actual active/corrected sources, semantic attribution and rich Live remain M6.

The Gridiron prerequisite gate selects only exact context with variant/pattern evidence and dated permission; `eligible_metadata` is not image readiness. Empty manifest/no grants/no media acquisition remain explicit. See [full source audit](../research/m1e-source-audit-2026-10-31.md).

## Owner source correction — start of M2

The owner restricts Sleeper to relevant NFL live-game/PBP data only. All former Sleeper fantasy acquisition, directory/hint mapping, state/trend and fantasy-stat candidate paths are retired and blocked before cache/network reads. Historical M1e receipts describe past research only; they are not model, identity or application inputs. No eligible Sleeper live route is currently enabled. ESPN remains the verified live source, and NFLverse remains the statistical foundation.

## M2 access storage

Additive migration0006 provides issuer+subject accounts, hashed invitations/opaque sessions, bounded expiring browser-bound OIDC flows, approved season/manager bindings, revisioned preferences and safe access audit events. Consumed flow secrets are wiped. Suspended accounts and revoked sessions/bindings cannot authorize facts; reactivation requires fresh sign-in and preserves revoked state. Member responses compose one canonical FFA document with explicit observation/source status and no provider calls. The populated local migration preserved source/manifests/identity/canonical content; [M2 evidence](../project/handoffs/2026-10-31-member-application.md).

## Implemented real-time sync — 2026-10-31

`arbit-worker run` keeps every changing source current in separate league, live and statistics lanes. Cadence follows the observed NFL slate; the [plan](../superpowers/plans/2026-10-31-realtime-sync.md) holds the table and supersedes the "other adaptive modes" proposal above for those sources. Budgets are per host: Fantasy one request per 2 s, NFL one per second. Additive `0007_realtime` adds `source_health`, `nfl_team`, `nfl_schedule_game`, `nfl_game` and `nfl_play_revision`, plus `outbox_event.occurred_at` and per-device session columns.

ESPN's `proTeams` directory is the verified NFL-team source that M1c was waiting for: its IDs match the fantasy `proTeamId` alias and the site scoreboard. It joined 132/132 owned players and all 14 games of a real week (2026-11-01). Team rows live outside the immutable league document, so a directory update never creates a league revision.

An unchanged read writes only freshness. A changed play writes a new revision with its event in one transaction. A missing play is never a deletion; only an explicit source cancellation is. A play already cancelled when first seen is history rather than a correction. Final games are read again at 0, 1 and 12 hours for late corrections. Outbox events are trimmed after 24 hours, always keeping the newest so sequences are never reused.

Not yet synced because nothing consumes them: FFA transactions and waiver results (M4), player news (M3), ESPN positional ratings (M4). Each must join the registry in `arbit_data/freshness.py` when its consumer ships.
