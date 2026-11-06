# Arbit agent entry point

Arbit is the FFA Fantasy Football Companion for ESPN league **1729878439**, season **2026**. M1a–e runtime/source/scoring/NFLverse/game-play foundations are implemented within recorded coverage. M2 member auth/API/Front Office/PWA and administrator controls are implemented; the owner verified the first real Google sign-in. A design reset and real-time sync platform (owner direction, 2026-10-31) run on the local app, and the owner accepted the design. Live (M6) is next, ahead of M3, by owner direction (OWN-019). Semantic features/models, advisors, full Live and deployment remain future work. Hosting platform is undecided and deferred until application development finishes; the production origin will be `https://ffa.westfam.media`. Until then deployment remains local-first.

## Read before changing work

1. [README](README.md), [current status](docs/project/status.md), and [latest handoff](docs/project/handoffs/2026-11-05-live-feed-observation.md).
2. [Requirement registry](docs/product/requirements.md), affected [feature experience](docs/product/feature-experiences.md), and applicable architecture/design documents.
3. [Decision register](docs/project/decision-register.md), [ADRs](docs/architecture/decisions/README.md), [research](docs/research/source-register.md), and [development standard](docs/engineering/agentic-development-standard.md).
4. The active implementation plan and existing affected code, once code exists. Chat history is not authoritative project memory.

## Non-negotiable project invariants

- Single FFA league, annual redraft; do not add tenancy or a second league provider. Never guess PPR, roster slots, draft structure, waiver rules or first-season history.
- ESPN is league authority; nflverse is the primary statistical foundation. For live NFL game data (plays, scores, clock, game state) the NFL API (`api.nfl.com`) is the primary source by owner direction (OWN-041), and ESPN's live game feed is the emergency fallback; ESPN's lane runs until the NFL lane is wired ([plan](docs/superpowers/plans/2026-11-05-nfl-api-primary.md)). Sleeper is eligible only for verified relevant NFL live-game/PBP data. Do not use Sleeper fantasy leagues, directories/crosswalk hints, roster/ownership, trends, rankings, projections or fantasy-stat/scoring inputs; no such eligible live route is currently enabled. Gridiron assets require verified variants; the owner obtained permission privately for personal use only, so they may be served only inside the invite-only application, never publicly or commercially.
- Shared identity, scoring, eligibility and versioned player evaluations serve all modules. No advisor or client duplicates provider parsing or fantasy arithmetic.
- Unknown data is not zero. The documented sparse-counter exception applies only to complete actual GP=1 stat maps; provider-zero no-game references remain separate. Unknown rules/identity or stale ownership must limit or block affected advice explicitly. Official ESPN totals, live estimates and model projections are visibly distinct.
- Preserve point-in-time lineage and corrections. No future information in a model backtest, fabricated route tracking, or unsupported numerical acceptance probability.
- Current public ESPN reads require no cookies; message boards are outside product scope. All ESPN interactions are read-only in the initial scope. Credentials remain server-side and outside source, fixtures, logs and browser bundles.
- Architecture/stack were approved on 2026-10-30. Additional development dependencies are authorized, especially UX/UI. Preserve deliberate, high-quality product design and engineering; generic dashboard filler is not acceptable. Do not report fixtures or documentation as a shipped feature.
- Design must be original. No slogans or taglines in the product, no AI-default aesthetics, no raw style values outside tokens. `pnpm check:design` enforces the mechanical part; see [design system](docs/design/design-system.md) and [ADR-005](docs/architecture/decisions/005-officiating-character.md).
- Every source that changes needs a supervised sync worker with a declared cadence and stale limit, and open clients must refresh without a reload. See [real-time plan](docs/superpowers/plans/2026-10-31-realtime-sync.md).

## Model cost policy

Agents may run their own audits and reviews, including through subagents. No subagent or review may use a model with higher usage cost than the primary session's active model (OWN-013; the earlier GPT-6.1 Sol-only rule existed to control review cost and is superseded). This overrides skill model-selection defaults.

## Work and validation

Follow Review → Plan → Implement → Validate → Document → Handoff. A plan names affected requirement IDs, files, interfaces and evidence. Use meaningful focused tests for behavioral changes; documentation/token changes use the foundation validator. Do not add redundant tests that merely repeat implementation. Use approved scope and judgment for routine reversible changes; gates require evidence, not repeated user permission. Ask before changing product scope or provisioning/publishing services without prior authorization.

Current executable check:

```sh
python3 scripts/validate_foundation.py
```

Runtime check: `make runtime-check` after frozen installs and `make db-up`; see [local development](docs/engineering/local-development.md). Run `make web-check` for the implemented client, contracts, design rules and PWA, and the isolated browser flow in the member guide. Don't run a build or browser suite against the owner's running app; see the member guide for an isolated port. Never fabricate a successful build or use private provider calls as mandatory CI tests.

Before handoff update status, changelog, decision/issue records as relevant, and a dated handoff with actual commands/results and remaining work. Make uncertainties actionable by naming the milestone they block. Keep the source brief unchanged; record interpretations in specifications/ADRs. Never overwrite another agent's work or claim it as verified without reading the diff and evidence.
