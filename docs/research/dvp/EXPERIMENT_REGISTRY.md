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
| M3-3-A01 | EXECUTED | v0's method on validated observations, with intervals | [V0_REPRODUCTION.md](V0_REPRODUCTION.md) |
| M3-3-A11 | PASSED | v0 and the extension read only FFA actuals under the league's rules, with no projection | [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md), [DATA_QUALITY.md](DATA_QUALITY.md) |
| M3-3-A00 | PLANNED | Raw DvP landscape and raw vs adjusted ranks | |
| M3-3-A02 | PLANNED | Split-method sensitivity (alternating games, halves, 6+6, seeded random splits) | |
| M3-3-A03 | PLANNED | Opponent-adjustment sensitivity | |
| M3-3-A04 | PLANNED | Stability by position, game count and era | |
| M3-3-A05 | PLANNED | Variance components with unequal game counts vs v0's k | |
| M3-3-A06 | PLANNED | Temporal stability and decay | |
| M3-3-A07 | PLANNED | Between-season carryover | |
| M3-3-A08 | PLANNED | Placebo and null distributions | |
| M3-3-A09 | PLANNED | Volume vs efficiency vs touchdowns | |
| M3-3-A10 | PLANNED | Era robustness | |
| M3-3-A12 | PLANNED | Completion and correction sensitivity | |
| M3-3-B00–B12 | PLANNED | Walk-forward: offense-only comparator B00, DvP variants B01–B08, controls and integrity B09–B12 | Preweek cutoff; development 2016–2023, validation 2024 |
| M3-3-C00–C05 | PLANNED (conditional) | Player-level Sit/Start impact | Runs only if Phase B finds a credible group-level signal |

**Blocked:** full D/ST coverage (156 team-games) waits on a canonical scorer repair, an owner decision (R-072). D/ST experiments run on the 5,122 valid team-games and report the gap.
