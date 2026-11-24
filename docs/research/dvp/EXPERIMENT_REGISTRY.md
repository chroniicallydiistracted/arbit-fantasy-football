# M3-3 experiment registry

Machine-readable: [experiment-registry.json](experiment-registry.json). It is written by `scripts/model/dvp.py registry` from the receipts, and every record carries the specification's §10 fields. Seeds and splits are in `config/dvp/base.json`:
- **Seed:** 1729.
- **Replicates:** 2,000.
- **Development:** 2016–2023.
- **Validation:** 2024.
- **Holdout:** 2025, conditional.

Every record has `forbidden_vendor_projection_dependencies = 0`.

| ID | Status | Question | Evidence |
| --- | --- | --- | --- |
| M3-3-v0 | REPRODUCED | Do defenses repeat a position-specific tendency? (odd/even weeks, 2016–2025) | [V0_REPRODUCTION.md](V0_REPRODUCTION.md). Baseline only: the misattribution affects 5 defense-seasons |
| M3-3-A01 | EXECUTED | v0's method on validated observations, with intervals (rerun on the R-072-repaired targets: D/ST on all 320 offense-seasons) | [V0_REPRODUCTION.md](V0_REPRODUCTION.md) |
| M3-3-A11 | PASSED | v0 and the extension read only FFA actuals under the league's rules, with no projection | [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md), [DATA_QUALITY.md](DATA_QUALITY.md) |
| M3-3-A00 | EXECUTED | Raw DvP landscape and raw vs adjusted ranks | [RELIABILITY_REPORT.md](RELIABILITY_REPORT.md) |
| M3-3-A02 | EXECUTED | Split-method sensitivity (alternating, halves, 6+6, home/away, 1,000 seeded random splits, minimum games) | Same |
| M3-3-A03 | EXECUTED | Opponent-adjustment sensitivity (none, season, leave-one-out mean, median, shrunk) | Same |
| M3-3-A04 | EXECUTED | Stability by era and half size; joint position orderings | Same |
| M3-3-A05 | EXECUTED | Variance components (method of moments, REML) with each unit's game count | Same |
| M3-3-A06 | EXECUTED | Temporal stability: halves vs odd/even, lag decay, rolling windows | Same |
| M3-3-A07 | EXECUTED | Between-season carryover | Same |
| M3-3-A08 | EXECUTED | Within-week permutation nulls (Holm), cluster bootstraps | Same |
| M3-3-A09 | EXECUTED | Components: yards, receptions, touchdowns, turnovers, kicking, D/ST tiers | Same |
| M3-3-A10 | EXECUTED | Era robustness, season exclusion, trimming, influence, home/away, byes | Same |
| M3-3-A12 | EXECUTED | Refused-line handling and 2026 stat corrections | Same |
| M3-3-B00 | EXECUTED | Offense-only next-game forecast from prior FFA actuals (the comparator) | [BACKTEST_REPORT.md](BACKTEST_REPORT.md) |
| M3-3-B01–B07 | EXECUTED | DvP variants: raw, unshrunk, shrunk, tuned k, recency, last-season prior, non-touchdown | Same. D/ST B06 −3.0% (development), −6.4% (2024); positions below the 1% minimum |
| M3-3-B08 | EXECUTED | Where the gain comes from: season, week, opponent games | Same |
| M3-3-B09 | EXECUTED | Negative controls: shuffled opponents, noise, last week's opponent | Same: no meaningful uplift |
| M3-3-B10 | EXECUTED | Preweek vs per-game cutoff | Same: no forecast changes |
| M3-3-B11 | PASSED | A planted projection cannot reach a forecast | `test_dvp_walkforward.py` |
| M3-3-B12 | EXECUTED | A 48-hour slower availability rule | Same: negligible |
| M3-3-C00–C05 | PLANNED (conditional) | Player-level Sit/Start impact | Runs only if Phase B finds a credible group-level signal |

**No longer blocked:** the canonical targets were repaired and rebuilt (R-072, TASK-20261123-007; owner instruction OWN-075). Every experiment runs on index `6ffb62fb…`, where all 5,278 team-games have a D/ST line. v0 alone keeps reading `4afbd836…`, the index it ran on.
