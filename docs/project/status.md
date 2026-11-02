# Project Status

Updated **2026-11-01**. Phase: **M2 implemented; design reset and real-time platform built on `claude/platform-reset`, running on the local app and accepted by the owner**. Primary developer: Claude. **Live (M6) is next by owner direction, ahead of M3** (OWN-019); see [prerequisites](../research/live-animation-prerequisites-2026-10-31.md).

## Confirmed context

FFA ESPN league **1729878439**, season **2026**. Owner approved the architecture/stack and additional dependencies, especially UX/UI. Deployment remains portable and local-first. High-quality, deliberate product design and engineering are required. Owner authorized development using the verified public FFA access and excluded message boards from product scope. Exact owner Gridiron asset links are still unavailable.

## Current implementation

M1a is implemented: pinned native Python/JS workspaces, exact scoring and temporal identity, PostgreSQL migration/snapshot/outbox persistence, fenced durable jobs, guarded synthetic worker path and health-only API. See [local development](../engineering/local-development.md) for reproducible commands. Runtime verification had **409 passing tests** at that point, including real PostgreSQL integration, plus Ruff/strict mypy/AJV/artifact checks. All completed slices have independent review and regression-backed fixes; no Important findings remain deferred.

M1b implements the public transport, observed league/player contracts, bounded complete pagination, ownership/context checks and `arbit-worker espn-inspect`. The complete audited retrieval surface is wired through 19 registered endpoint families; `arbit-worker espn-endpoints --live` passed all 68 recognized successful variants after review (63 available, three limited, two metadata-only). [Coverage](../research/espn-endpoint-coverage-2026-10-30.md). A fresh live read returned eight teams, 132 owned, 923 available, 46 scoring items, 128 picks and 56 matchups through seven cookie-free GETs. [Reader receipt](../research/espn-reader-live-2026-10-30.json). The pinned reference checkout is available under ignored `.references`.

M1c scoring slice: all 46 actual definitions mapped; completed weeks 1–7 verified 797 played player-games plus 121 separate provider-zero entries and 56/56 lineup totals, with zero discrepancies. Private archived-input replay reproduces the result. Eleven categories lack nonzero live examples; synthetic math/boundary evidence is distinguished. [Scoring proof](../research/ffa-scoring-verification-2026-10-30.md). Recommendations remain disabled.

M1c durable sync now publishes complete FFA facts with persistent native identities, dated affiliations, immutable verified rules, correction history and private capture manifests. Shared PostgreSQL pacing/cooldown, leased heartbeats, durable retry/pause/freshness and offline replay are implemented. Protected loopback-only operator reads serve the stored league; default API remains health-only. Live proof: eight teams/eight managers, 132 owned, 923 available, 128 picks, 56 matchups, one snapshot/outbox after four successful refreshes (including a bounded automatic-worker run). [Operator guide](../engineering/ffa-synchronization.md), [safe evidence](../research/ffa-sync-live-2026-10-30.json).

M1d is implemented and fully imported: 1,140 selected logical files across 28 families, 1,087 tables/11,973,952 stored rows and 53 archive-only originals/metadata/reference files. Versioned original/normalized objects and additive 0003/0004 migrations pin checksums, source/observation/proof times, schemas, coverage and attribution. Durable staged acquisition/publication, exact GSIS/ESPN crosswalks and protected canonical-player reads are verified. All 786 checksum-free assets passed a second catalog check; offline verification covered all 1,140 manifests/1,157 unique data objects. All 121 rostered athletes map to GSIS, with two lacking weekly rows. Five later conflicting supplemental aliases were closed with backed-up immutable history; zero active provider/entity multiplicities remain. [Full audit](../research/nflverse-data-audit-2026-10-31.md), [guide](../engineering/nflverse-ingestion.md), [safe receipt](../research/nflverse-live-2026-10-31.json).

M1e is implemented and locally verified: durable public observations/daily cache, documented Sleeper directory/state/trends and two explicit candidate stat representations; read-only exact joins with conflicts excluded; scoped ESPN scoreboard/summary/core plays and per-play-time correction-safe replay; empty Gridiron manifest and exact-context/permission gate. Actual proof: 12,229 directory records, 40/121 owned-athlete direct hints (NFLverse remains 121/121); four completed games/842 plays including overtime/tie, all 293 game-scoped supplied athlete IDs resolved; final/pregame CLI and offline 25-observation/66-object verification. No images or messages. [Audit](../research/m1e-source-audit-2026-10-31.md), [guide](../engineering/supplemental-live-sources.md).

M2 member auth/binding, Front Office facts and PWA now exist locally. Google is selected, with real client/member/team acceptance still open. Active/corrected Live evidence and exact asset grants remain M6 gates. Recommendations remain disabled. The earlier private-setting 401 is historical; current settings requests return 200 without cookies, and message-board availability is outside product scope. See the [full audit](../research/espn-public-api-audit-2026-10-30.md).

## Milestones

| Milestone | State |
| --- | --- |
| M0 foundation | Delivered; architecture/stack accepted by owner |
| M1a runtime/core/snapshot | Implemented, reviewed and locally verified |
| M1b FFA access/capability inventory | All audited usable routes wired and live-verified; canonical local sync implemented in M1c; member production access awaits M2 |
| M1c scoring/normalization | Scoring and canonical FFA aliases/publication/durable local sync implemented and live-verified |
| M1d statistical foundation | Complete published catalog imported, reviewed, replay/identity/local-read verified |
| M1e supplemental/live sources and assets | Implemented/reviewed; observed source matrix, offline replay and asset prerequisites verified; empirical Live/asset gaps explicit |
| M2 application/auth/Front Office/PWA | Implemented/local validation; Google selected; real client/member acceptance pending |
| M3 Model/Scout | Not started |
| M4 Lineup/waivers | Not started |
| M5 trade/Draft | Not started |
| M6 Live | In progress: scoreboards running on the local app; Gridiron delivery, play animation and fantasy attribution remain |
| M7 Archive/refinement | Not started |

## Repository and verification

Owner published baseline commit `cab6bd8` on main. Owner published `codex/m2-member-application` at `61368fd`. Current work: local branch `claude/platform-reset`, not pushed; no merge or deployment. Aggregate validation: `make runtime-check` after frozen installs and `make db-up`. On this host use the pinned npm-exec workaround in the development guide if Corepack is misconfigured. Local PostgreSQL service remains available; HTTP smoke process has been stopped.

Latest [M2 handoff](handoffs/2026-10-31-member-application.md) records member implementation, local proof and Google release gate. Earlier [M1e handoff](handoffs/2026-10-31-supplemental-live.md) records supplemental/live proof, review fixes and remaining gates; [NFLverse handoff](handoffs/2026-10-31-nflverse.md) records full M1d source/identity/HTTP proof and review rulings; [durable sync handoff](handoffs/2026-10-30-durable-ffa-sync.md) records canonical publication and live API proof; [scoring handoff](handoffs/2026-10-30-ffa-scoring.md) records exact scoring verification; [endpoint handoff](handoffs/2026-10-30-endpoint-coverage.md) records full routing; [reader handoff](handoffs/2026-10-30-public-reader.md) records core acquisition; [public API handoff](handoffs/2026-10-30-espn-public.md) records the earlier 81-probe audit. [M1a handoff](handoffs/2026-10-30-m1a.md) records runtime tests, code scope, environment adaptations and review results. [Initial foundation handoff](handoffs/2026-10-30-foundation.md) is historical. [Roadmap](roadmap.md), [decisions](decision-register.md), [known issues](known-issues.md), [research](../research/source-register.md) and [changelog](changelog.md) preserve continuity.

## M2 active work and source correction

The owner restricts Sleeper to relevant NFL live games/PBP only. Earlier directory/state/trend/fantasy-stat and hint-mapping paths are retired and no longer application inputs; old audit receipts remain historical. No eligible Sleeper live route is enabled. ESPN game/PBP remains active. [M2 plan](../superpowers/plans/2026-10-31-member-application.md) covers invited member access, stored Front Office facts and the deliberate application/PWA shell. Google is now the selected provider. No real OAuth client or external service has been provisioned.

## M2 implemented scope

Invited OIDC accounts, opaque sessions, administrator-approved manager bindings and access controls, typed/generated member API, Front Office saved facts, player drawer/search, watchlist/preferences and static-only PWA are implemented. Two clearly fictional browser members prove scope; the actual stored FFA snapshot validates without a fixture identity. Google is selected; owner-controlled client configuration and real invited sign-in/team proof remain open. [M2 handoff](handoffs/2026-10-31-member-application.md), [operations](../engineering/member-application.md). No recommendations, active Live workspace or deployment.

Final M2 verification: 453 backend tests, 14 client tests and 7 Chromium scenarios pass; generated contracts/type/build/PWA checks pass. One Sol review’s two Important and one Minor findings were fixed with regressions. Actual populated-source migration preserves all counts/digest; no real member account was created. See the final M2 handoff for remaining operational acceptance.

## Google configuration follow-up — 2026-10-31

The owner created the Google OAuth client and supplied credentials in a locally ignored file. That file was safely moved from `config/google-auth.env` to root `.env.auth.local`, restricted to mode 600, and confirmed untracked/ignored. Configuration validation and real-OIDC-mode local readiness passed without printing credentials or contacting Google. The remaining M2 gate is the first administrator invitation, actual Google sign-in, approved manager binding and second-member verification.

## Owner sign-in acceptance and manager labels — 2026-10-31

The owner confirmed successful real Google sign-in, first administrator invitation, team approval/session rotation and return to Front Office. This is owner-reported real acceptance, separate from prior fictional tests; second-member and native/assistive-technology checks remain open. ESPN's team/settings view supplies first names for all eight FFA managers; six display names are generic. Canonical optional first names and team context now label the administrator manager dropdown, retaining original handles for fallback/disambiguation and stable IDs for binding. A normal live sync stored all eight names with manager IDs and approved bindings unchanged.

## Design reset and real-time platform — 2026-10-31

The owner reported AI-identifiable design drift and stale data, and redirected the work (OWN-013–017). **Built and verified on `claude/platform-reset`; applied to the running local app on 2026-11-01 04:26 UTC.** [Handoff](handoffs/2026-10-31-platform-reset.md).

- **Design:** new officiating-and-broadcast character ([ADR-005](../architecture/decisions/005-officiating-character.md), [design system](../design/design-system.md)), all slogans removed, and `pnpm check:design` enforcing the rules; it flagged 436 violations on the old interface. The owner accepted it (OWN-018).
- **Sync:** `arbit-worker run` keeps the FFA league, NFL scoreboard, active-game plays and summaries, NFL teams and schedule, and NFLverse statistics current on a cadence that follows the real NFL slate.
- **Clients:** session-bound SSE updates open pages without a reload. Per-device sessions mean signing in on a phone no longer ends the laptop session.
- **Members now see:** real Live scoreboards with possession, down and distance, field position, score by quarter, win probability, team stats, leaders, drives and plays with a my-players filter; also NFL team/bye/opponent on roster rows, per-source data status, season results strip and playoff line.
- **Evidence:** 587 backend tests, 20 client tests, 10 browser scenarios and all static checks pass. The [first real slate](../research/live-slate-receipt-2026-11-01.md) was measured: 0 read failures, a median play delay of 36 seconds, and real game changes reaching an open page without a reload.
- **Running now:** `arbit-api` and `arbit-worker` as systemd user services on schema `0007_realtime`, upgraded with scoreboards 2026-11-01 21:25 (UTC−7). The fix for signing in from another local address (R-036) is built and waits on the next upgrade. They do not come back by themselves after a Windows restart (R-029).
- **Next:** Gridiron URL patterns are verified and week 8 art is stored privately. Scoreboards and animation have [19 listed prerequisites](../research/live-animation-prerequisites-2026-10-31.md); the owner chose [pixel sprites](../research/live-animation-prerequisites-2026-10-31.md#sprite-direction--owner-decision-2026-11-01) (OWN-022), approved the test frames (OWN-023) and owns the art (OWN-024). 40 frames are in `assets/sprites`, not yet in the app. [Scoreboards](../superpowers/plans/2026-11-01-live-scoreboards.md) are running. Next are Gridiron sync and private delivery, then recoloring and the in-app play renderer.
- **Live capture:** the worker has kept private raw copies of every live read since 2026-11-01 06:23 UTC, ahead of the first real slate (OWN-020, R-030). Animation shows only the players ESPN names on a play and the ball (OWN-021). The host PC slept through the 2026-11-01 early games, so only the late games were observed live (R-029).
