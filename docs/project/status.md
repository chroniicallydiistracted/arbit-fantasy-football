# Project Status

Updated **2026-10-30**. Phase: **M1 data/runtime foundation**.

## Confirmed context

FFA ESPN league **1729878439**, season **2026**. Owner approved the architecture/stack and additional dependencies, especially UX/UI. Deployment remains portable and local-first. High-quality, deliberate product design and engineering are required. Owner authorized development using the verified public FFA access and excluded message boards from product scope. Exact owner Gridiron asset links are still unavailable.

## Current implementation

M1a is implemented: pinned native Python/JS workspaces, exact scoring and temporal identity, PostgreSQL migration/snapshot/outbox persistence, fenced durable jobs, guarded synthetic worker path and health-only API. See [local development](../engineering/local-development.md) for reproducible commands. Runtime verification currently has **316 passing tests**, including real PostgreSQL integration, plus Ruff/strict mypy/AJV/artifact checks. All completed slices have independent review and regression-backed fixes; no Important findings remain deferred.

M1b implements the public transport, observed league/player contracts, bounded complete pagination, ownership/context checks and `arbit-worker espn-inspect`. The complete audited retrieval surface is wired through 19 registered endpoint families; `arbit-worker espn-endpoints --live` passed all 68 recognized successful variants after review (63 available, three limited, two metadata-only). [Coverage](../research/espn-endpoint-coverage-2026-10-30.md). A fresh live read returned eight teams, 132 owned, 923 available, 46 scoring items, 128 picks and 56 matchups through seven cookie-free GETs. [Reader receipt](../research/espn-reader-live-2026-10-30.json). The pinned reference checkout is available under ignored `.references`.

M1c scoring slice: all 46 actual definitions mapped; completed weeks 1–7 verified 797 played player-games plus 121 separate provider-zero entries and 56/56 lineup totals, with zero discrepancies. Private archived-input replay reproduces the result. Eleven categories lack nonzero live examples; synthetic math/boundary evidence is distinguished. [Scoring proof](../research/ffa-scoring-verification-2026-10-30.md). Recommendations remain disabled.

M1c durable sync now publishes complete FFA facts with persistent native identities, dated affiliations, immutable verified rules, correction history and private capture manifests. Shared PostgreSQL pacing/cooldown, leased heartbeats, durable retry/pause/freshness and offline replay are implemented. Protected loopback-only operator reads serve the stored league; default API remains health-only. Live proof: eight teams/eight managers, 132 owned, 923 available, 128 picks, 56 matchups, one snapshot/outbox after four successful refreshes (including a bounded automatic-worker run). [Operator guide](../engineering/ffa-synchronization.md), [safe evidence](../research/ffa-sync-live-2026-10-30.json).

No frontend UI, member authentication/binding, cross-provider mappings, statistical model or deployment exists yet. M1d nflverse coverage/manifests/crosswalks is next. Recommendations remain disabled. The earlier private-setting 401 is historical; current settings requests return 200 without cookies, and message-board availability is outside product scope. See the [full audit](../research/espn-public-api-audit-2026-10-30.md).

## Milestones

| Milestone | State |
| --- | --- |
| M0 foundation | Delivered; architecture/stack accepted by owner |
| M1a runtime/core/snapshot | Implemented, reviewed and locally verified |
| M1b FFA access/capability inventory | All audited usable routes wired and live-verified; canonical local sync implemented in M1c; member production access awaits M2 |
| M1c scoring/normalization | Scoring and canonical FFA aliases/publication/durable local sync implemented and live-verified |
| M1d–e statistical/supplemental sources | Planned |
| M2 application/auth/Front Office/PWA | Not started |
| M3 Model/Scout | Not started |
| M4 Lineup/waivers | Not started |
| M5 trade/Draft | Not started |
| M6 Live | Not started |
| M7 Archive/refinement | Not started |

## Repository and verification

Owner published baseline commit `cab6bd8` on main. Current work: local branch `codex/m1c-durable-sync`; no new push, merge or deployment. Aggregate validation: `make runtime-check` after frozen installs and `make db-up`. On this host use the pinned npm-exec workaround in the development guide if Corepack is misconfigured. Local PostgreSQL service remains available; HTTP smoke process has been stopped.

Latest [durable sync handoff](handoffs/2026-10-30-durable-ffa-sync.md) records canonical publication and live API proof; [scoring handoff](handoffs/2026-10-30-ffa-scoring.md) records exact scoring verification; [endpoint handoff](handoffs/2026-10-30-endpoint-coverage.md) records full routing; [reader handoff](handoffs/2026-10-30-public-reader.md) records core acquisition; [public API handoff](handoffs/2026-10-30-espn-public.md) records the earlier 81-probe audit. [M1a handoff](handoffs/2026-10-30-m1a.md) records runtime tests, code scope, environment adaptations and review results. [Initial foundation handoff](handoffs/2026-10-30-foundation.md) is historical. [Roadmap](roadmap.md), [decisions](decision-register.md), [known issues](known-issues.md), [research](../research/source-register.md) and [changelog](changelog.md) preserve continuity.
