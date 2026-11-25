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
| M3-3-HOLDOUT-2025 | EXECUTED, decision PROMISING (D/ST only) | The frozen candidates on 2025 (conditional holdout) | [MODEL_CARD.md](MODEL_CARD.md), `backtest-holdout.json` |
| M3-3-C00 | EXECUTED | An Arbit-computed, actuals-only D/ST baseline (B00; Arbit has no other player projection) | [PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md), `sitstart.json` |
| M3-3-C01 | EXECUTED | Allocating the group term to players: a D/ST is one unit per team, share 1 (checked, T26) | Same |
| M3-3-C02 | EXECUTED | Additive vs proportional vs opportunity × efficiency: identical for a share of 1 | Same |
| M3-3-C03 | BLOCKED | Role interactions (slot, outside, target share): no meaning for a D/ST | Same |
| M3-3-C04 | EXECUTED, decision PROMISING | Pairwise D/ST start/sit accuracy, B06 vs B00: +4.4 (dev), +8.5 (2024), +6.6 (2025) points; minimum 1.8 declared first | Same; `config/dvp/sitstart.json` |
| M3-3-C05 | EXECUTED, decision PROMISING | Points per changed choice +1.6 to +2.7; worst single choice −40; league top-8 +8 to +19 points a week. League-constrained evaluation split by the owner's Phase B audit; see the C05L rows | Same |
| M3-3-C05L-HIST | NOT_APPLICABLE | League-constrained evaluation on 2016–2025: FFA began in 2026 (OWN-076); the unrestricted pairwise evaluation stands for those seasons | [LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md) |
| M3-3-C05L-2026-EXP | EXECUTED, EXPLORATORY | Completed 2026 weeks 1–11, frozen B00 vs B06 on decision sets rebuilt at each cutoff: start (28 decisions) −6 points (−90 to +80); stream (88) +46 (−280 to +360). Too few decisions to measure | Same, `league-2026-exploratory.json` |
| M3-3-C05L-2026-PRO | PENDING_FUTURE_DATA | Weeks 12–18: rosters and availability captured at each forecast; descriptive evaluation after the games | Same; [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md) |

| M3-3-V2-DECOUPLED | EXECUTED, EXPLORATORY | Owner audit AUD-05: development, 2024 and 2025 through separate stages (schedule targets, contract-checked features, forecast-only outputs persisted before labels, keep-every-target join, coverage). Frozen variants reproduce v1 exactly on valid rows | [EXPLORATORY_V2.md](EXPLORATORY_V2.md), `explore-v2.json` |
| M3-3-V2-B05W | EXECUTED, EXPLORATORY | Owner audit AUD-03: rolling 3-, 5- and 8-game residual windows with REML-k shrinkage. Shorter windows are worse; none beats B03 or B06 | Same |
| M3-3-V2-B03SH | EXECUTED, EXPLORATORY | Owner audit AUD-03: B03 with v0's split-half k fit on training seasons only. Forecasts about as well as REML k | Same |
| M3-3-V3-A09VE | EXECUTED, EXPLORATORY | Owner audit AUD-02: volume allowed and efficiency allowed, REML k with season intervals. The repeatable part is volume for RB, WR and K, and efficiency for D/ST | [OPPORTUNITY_EFFICIENCY.md](OPPORTUNITY_EFFICIENCY.md), `explore-v3.json` |
| M3-3-V3-B07VE | EXECUTED, EXPLORATORY | Owner audit AUD-02: volume channel, efficiency channel and both, against B00, B03, B06 and the retained non-touchdown B07. Nothing crosses 1% outside D/ST; for D/ST, B06 stays best | Same |
| M3-3-PROSPECTIVE-2026 | PENDING_FUTURE_DATA | Weeks 12–18 archived before each kickoff (week 12 done 2026-11-24 23:12 UTC); evaluated after the games | [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md) |

**Phase C covers D/ST only.** The specification starts Phase C only after a credible group-level signal. QB (INCONCLUSIVE) and RB, WR, TE and K (NOT_USEFUL) don't have one, so they were not run. That is the gate, not a finding about players.

**No longer blocked:** the canonical targets were repaired and rebuilt (R-072, TASK-20261123-007; owner instruction OWN-075). Every experiment runs on index `6ffb62fb…`, where all 5,278 team-games have a D/ST line. v0 alone keeps reading `4afbd836…`, the index it ran on.
