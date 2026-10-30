# Arbit Data Architecture Specification

Version 0.1 · 2026-10-30 · Proposed. Source capability evidence: [research register](../research/source-register.md).

## Source authority and boundaries

| Source | Authority | Planned inputs | Limitations and decisions |
| --- | --- | --- | --- |
| ESPN Fantasy | FFA league truth | Settings/scoring, slots/eligibility, teams/managers, rosters/ownership, matchups/standings, draft, free agents/waivers, transactions where available | Unofficial, mutable interface; private access may need server-side cookies. Completeness/pagination and permission must be demonstrated with FFA, never inferred from one successful request |
| nflverse | Primary NFL statistical foundation | PBP, player/team weekly stats, schedules/results, rosters/IDs, snap counts, depth, NGS, advanced charting where covered | Dataset-specific schema, publication times, coverage and terms; not a guaranteed real-time feed. In-season features must not use data published after the prediction cutoff |
| Sleeper | Supplemental metadata, NFL state, trends and ID hints | Documented player directory/state/trending; scoring/play/game endpoints only after explicit proof | No Sleeper fantasy league integration. Official public docs do not establish a supported live PBP/scoring feed; endpoint gaps remain research work |
| ESPN NFL | Live NFL context | Scoreboard, event summary, drives/plays, boxscore, participants and scoring events where supplied | Unofficial; fields/types/coverage vary by event. One completed-game summary was observed, not a live reliability guarantee |
| Gridiron | Intended fields/uniforms | Team/season/game-specific images and variant metadata | Likely sites identified; owner URL patterns not supplied. No API assumed; assets and use permissions unconfirmed |

A source conflict never silently overwrites authoritative FFA facts. Retain both observations with source/time and expose a discrepancy. ESPN fantasy totals remain official even when Arbit's reconstructed live scoring differs. nflverse historical corrections create new dataset versions rather than changing past model inputs in place.

## Canonical identity

Use internal UUIDs, with `(provider, entity_kind, external_id)` aliases and effective dates. Preserve provider IDs as strings. `entity_kind` distinguishes athlete, NFL team, fantasy team, and defense/special-teams unit; a D/ST is not a human player. GSIS/ESPN/Sleeper IDs are aliases, not a universal primary key. An NFL player can change team within a season; team affiliation is dated.

Reconciliation order: verified provider crosswalk → exact trusted alias → curated deterministic evidence (name, position, birth date, team history) → unresolved queue. Fuzzy/name-only matches may propose candidates but never auto-merge, especially suffixes, duplicated names, rookies, traded players and D/ST units. Store mapping method, evidence, reviewer, confidence, and validity. Unresolved identities can appear as raw provider records but are excluded from affected advice with a visible limitation. Alias corrections invalidate derived projections/joins and preserve the original mapping version for reproduction.

Fantasy team membership is season-specific and can include multiple managers. NFL game IDs and fantasy matchup IDs have their own aliases. Provider NFL week, scoring period, and matchup period are separately named; playoff rounds and multiweek matchups must not be collapsed into one `week` field.

## Storage layers and publication

1. **Raw:** immutable compressed provider body or Parquet download in local/S3-compatible storage; metadata in PostgreSQL. Remove member fields not needed by Arbit and redact secrets before storage. Restricted raw league data is never a public URL.
2. **Normalized:** canonical identities, validated league snapshots, normalized games/stats/play revisions, and source health. Schema adapters are versioned.
3. **Analytical:** versioned Parquet partitions by dataset/season/season_type/week where applicable, point-in-time feature sets, model artifacts, evaluation reports. Never force timestamped depth charts into a fictional weekly source key.
4. **Serving:** indexed current league snapshot, player summaries, model results, recommendations, matchup projections, archive records; bounded payloads for web views.

Object manifest: dataset ID, provider URL, fetch time, provider publication time if known, ETag/Last-Modified when available, SHA-256, byte size, season range, schema/adapter version, terms/attribution, coverage and quality report. A release manifest pins all inputs for a model run. Checksum changes create a revision even when the URL does not change. Only a fully validated revision becomes the current pointer.

## Relational model

All timestamps are UTC `timestamptz`; the client formats the member's timezone. Use UUID primary keys except source-native identifiers stored as aliases. The following are planned tables, not applied migrations.

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

The adapter exposes `fetch_league_snapshot(league_id, season, scoring_period)`, `fetch_available_players(cursor)`, `fetch_draft_state()`, and capability checks. Requests have timeouts, bounded response sizes, per-host budgets, conditional fetches where supported, redacted logs, and explicit 401/403/429/5xx handling. No external write methods are implemented.

For each poll: acquire a season-specific lease → fetch all required views/pages → store redacted immutable response manifests → validate required sections and exact configuration → reconcile identities → stage a candidate snapshot → verify ownership and roster invariants → publish in one transaction → enqueue invalidations and outbox event. Paginate/filter the entire available-player universe; top-50 results cannot stand for all FFA free agents. If data changes across pages, retry a bounded reconciliation pass and mark uncertain results instead of publishing an inconsistent roster.

Detect acquisitions, releases, trades, lineup changes, waivers, matchups, settings and draft changes by diffing published snapshots; transaction logs are supplementary, not the only source. Do not infer a successful waiver transaction from a trending-player feed. Unknown scoring or slot IDs fail the rules-support gate and block affected calculations while other league facts remain visible.

No season inference from the machine date: configured season is 2026 until an explicit rollover workflow snapshots finals, updates configuration and bootstraps the new season. Imported league names, roster sizes, PPR multipliers and waiver systems remain unknown until fetched.

## Polling and freshness proposal

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
| Sleeper full player directory | At most once per day; use saved mapping | 48 hours; no directory call per player lookup |
| Sleeper state/trends | Hourly/15 minutes respectively within documented limits | Two missed intervals; supplemental signals only |
| Gridiron approved asset manifests | Weekly and on explicit curation | Unknown variant remains unknown; never substitute a generic uniform as verified |

Offseason disables game/draft polling; scheduler uses configured season state and observed games rather than a hardcoded calendar. Poll due times have jitter. Backoff starts at five seconds, exponential up to 15 minutes with jitter; honor longer `Retry-After`. Cap normal attempts at five, then failed/dead-letter state for inspection. Repeated auth denial immediately marks credential action needed and stops tight retries. A circuit breaker limits outage storms. Current published state remains available with its age.

## NFL statistical processing

Start with a measured dataset coverage inventory for past seasons and 2026; record missingness, revisions, types and licensing per dataset. Candidate features: efficiency (EPA, success, yards per opportunity), volume (snaps, attempts, targets, air yards, red-zone share), role stability, team pace/pass rate, defensive matchup, schedule and recent trends with sample weighting. Route/participation features enter in-season models only if their actual publication timestamp proves availability at that cutoff. Injury, news, weather and depth information need source-specific evidence, not an assumption that all exist in one dataset.

For each feature: define unit, denominator, window, minimum sample, missingness indicator, transformation version and earliest observable time. Joins use canonical IDs and temporal validity; aggregate at the right grain before joining to avoid duplicating receiving/rushing totals on PBP rows. Defensive opponent adjustments shrink small samples. Train/validate with chronological cutoffs; fitting transforms across all seasons before splitting is prohibited.

## Shared scoring and recommendation lineage

Normalize ESPN stat-category IDs into versioned scoring rules: linear rates, threshold/range bonuses, distance-dependent kicking, turnovers, fractional/negative points, defensive/team scoring, and slot eligibility as actually configured. Preserve unsupported rules verbatim, with a diagnostic code; do not assume PPR, K/DST, bench, IR, FLEX, or superflex settings. Use exact Decimal arithmetic and tested final rounding. Bonus expectations come from simulated stat lines/distributions, not `bonus(mean(stat))`.

A historical score uses the relevant season/rule version. Reconcile hand-verified game fixtures against ESPN totals including corrections, D/ST points allowed definitions and edge plays. PBP reconstructed totals are provisional because later boxscore corrections and categories can differ. Advice must carry snapshot ID, rule hash, feature-set version, model run, as-of cutoff, generated time, horizon, coverage and limitations. Changes invalidate by dependency: a lineup move affects that team's lineup scenario; a rules change affects all scoring-dependent artifacts.

## Live events and graphical projection

Normalize source event/play IDs, sequence, game clock/period, possession, down/distance, start/end field position where observed, participants, scoring category and revision. Keep provider text and raw type alongside canonical type. Support pass, rush, sneak, sack, interception, field goal, PAT, two-point conversion, punt/kick/return, penalty/no-play, fumble and unknown. Plays can have multiple effects; a fumble return after an interception cannot be flattened into one positive gain.

Reconcile authoritative cumulative live stats by revision where present rather than indefinitely adding deltas from play text. Idempotent replays produce the same current scoreboard and fantasy attribution; corrections replace the effective revision and emit a correction event. A tombstoned/no-play event reverses prior derived effects. Deduplicate polling overlap and handle reordered events. If a provider lacks stable IDs, retain deterministic fingerprint plus ambiguity flags and do not claim reliable per-play scoring until validated.

A schematic path can use line of scrimmage and observed endpoint, but PBP does not establish actual player routes, tracking coordinates or tackle location. The UI labels inferred trajectories and falls back to text when field position is missing. Orientation is canonical offense-to-defense and flips for display using possession/direction, including turnovers and overtime. Preserve separate game clock and wall time. Field/uniform manifestations include source, exact variant confidence and fallback; show weekly uniforms only when verified.

## Governance, retention and operations

Back up private league/user/identity/alias/archive data daily encrypted, with proposed 30-day rolling retention and monthly season snapshots; test restore quarterly. Raw private league snapshots: 30 days initially, retain sanitized season-final snapshots and rule versions for Archive; revisit after storage/terms review. Live normalized event revisions persist for season replay; outbox replay retention starts at 24 hours. Public datasets/artifacts follow their source terms and manifest retention needs. Account removal revokes sessions, removes unnecessary personal settings and anonymizes administrative audit attribution where appropriate, without erasing verified league results.

Metrics: source latency and last success, expected-publication lag, coverage/mapping failures, drift count, job age/retries, poll volume, dead letters, scoring discrepancies, SSE delivery delay and model freshness. Drift quarantines only affected datasets and blocks affected models; no silent casting or replacement by zero. Administrative recovery supports bounded replay/backfill with dry-run row counts, immutable manifests, idempotency keys and audit records.

## Release checks for the data foundation

Prove FFA access and full settings/roster coverage; document every supported and unsupported rule. Check alias uniqueness and unresolved-player reporting. Run an identical snapshot twice without duplicates, reject partial pages, recover from 401/429/schema drift, and preserve the previous current snapshot. Verify point-in-time cutoffs, live correction replay and model provenance. Owner links/private credentials and exact Gridiron permissions remain explicit prerequisites, not fabricated integrations.
