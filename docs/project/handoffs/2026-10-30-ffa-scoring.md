# Handoff — 2026-10-30 — Actual FFA scoring verification

## Completed owner scope

Owner explicitly requested finishing every successful API route/audit, then mapping actual FFA rules and verifying ESPN totals before recommendations. The [endpoint handoff](2026-10-30-endpoint-coverage.md) closes routing: 68/68 recognized successful audit variants across 19 families; all 81 cases accounted, including five limited/metadata responses and 13 exclusions. Message boards remain excluded.

M1c now maps all 46 configured definitions into the existing shared Decimal scorer, with athlete/D/ST role-specific rules and exact defense bands. It independently recomputes actual raw statistics and verifies per-category contributions, player totals and archived starting-lineup totals. Added `uv run arbit-worker espn-score-audit [--periods ...]`; no database, credentials, new dependency, public API route, migration, provider write or deployment.

Authoritative [mapping/semantics/support document](../../research/ffa-scoring-verification-2026-10-30.md), [safe final source report](../../research/ffa-scoring-audit-2026-10-30.json), [implementation plan](../../superpowers/plans/2026-10-30-ffa-scoring.md).

## Actual results and reproducibility

Final reviewed-code live run, UTC **2026-10-31 03:59:12–03:59:28**, code commit **0797ceb**: completed scoring periods 1–7; **918 roster entries = 797 verified played player-games + 121 explicitly classified provider zeros; 56/56 lineup totals; zero mismatches/errors; 46/46 definitions mapped**. Thirty-five categories had nonzero actual contributions; eleven unobserved nonzero categories are disclosed, with synthetic hand/boundary checks. Current period 8 is excluded from completed-period verification. Recommendations remain false.

Nine source fetches were captured privately under ignored `data/research/scoring/2026-10-30/run-20261031T035912Z/`. These are parsed Decimal-string archives with authentic source-body receipts, not counterfeit raw byte snapshots. Exact request URLs, support hashes, totals and nonzero coverage reproduce on replay. The safe report contains the private archive manifest hash; no member data is committed. Original numeric-only observed QB/K/DST fixtures retain hashes and anonymize identity.

The normal CLI was also smoke-tested for period 1: 124 verified games, five provider zeros, eight matched lineups. Existing endpoint inspection/verification and guarded synthetic publication commands remain available.

## Evidence and review

Final full command:

```sh
npm exec --yes --package=node@24.22.2 --package=pnpm@12.16.1 -- make runtime-check
```

Exit 0: **275 tests passed**, Ruff lint/format, strict mypy, AJV examples and foundation checks. Real PostgreSQL integration is included. `git diff --check` and final documentation validation passed. CI was not remotely run; no push/merge occurred. Local PostgreSQL remains healthy and test schemas are removed by fixtures.

Fresh independent review found two Important gaps: unexpected contributions on zero-rate categories could cancel; extreme finite decimals could escape safe error handling. All three failing reproductions became passing regressions after fixes. An intended unbounded-range caller adaptation was tested in the working tree but omitted from the preceding staging list; it is included in final fix commit 0797ceb. No Critical findings remain in the final tree, no deferred Important findings. Review explicitly set aside downstream identity/publication/auth/model work and unobserved provider rounding/rare-event behavior; those limitations remain recorded.

## Key decisions

- The reference repository's football stat-ID table and description of appliedStats are wrong. Factual mappings are pinned to maintained primary wrapper source and verified against actual raw/contribution pairs; no upstream implementation copied.
- D/ST override 16 is independent of lineup placement. Defense bands use raw 120/127 and verify corresponding flags; the under-100 band accepts negative net yardage via an explicit unbounded core lower bound.
- Exact source/split/season/period/GP selection prevents projections, season aggregates and duplicate blocks becoming actual scores. Sparse known additive counters are zero-suppressed only inside complete actual GP=1 blocks. Missing maps/range totals remain unknown. Official no-game zero references are separately labeled and never counted as verified statistics.
- Comparisons use explicit cent half-up policy; current rates/observed counts yield exact cents. Float serialization noise is not a widened score tolerance or an ESPN tie-rounding guarantee.
- Unsupported definitions/controls, missing source capabilities, unknown slots, duplicate starters, multiweek/current periods, source drift and mismatches fail verification safely. Advice is never enabled by this command.

## Next executable work

Persist versioned rule sets and explicit canonical aliases/defense identities with new migrations, extend canonical snapshot contracts to full FFA facts, then wire lease-fenced acquisition→normalization→publication with source health, shared budgets, durable retries and correction replay. Preserve the verified scorer's single implementation; future nflverse normalization must reproduce the exact category semantics before projections use it. Then continue dataset coverage, member authentication and the application/Model phases.

Current local branch `codex/m1c-ffa-scoring` is based on `c1cdbb0`. Canonical FFA publication, member binding/auth, Model and UI remain unimplemented. Do not equate this completed scoring slice with full M1 or recommendation readiness.
