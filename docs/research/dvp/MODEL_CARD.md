# Model card: M3-3 defense against the position (DvP)

Specification §11.8, §12. TASK-20261124-003; Phase C and the conclusions table TASK-20261124-004. **Research artifact. It is not in production and changes no weight;** any use in Arbit's Sit/Start model needs the owner's approval (OWN-074).

## What it is

A forecast of next week's FFA points for each team and position group. It comes in two parts:
- **B00, the offense-only comparator.** Each side's own record: its last season regressed toward the league, updated with this season's completed games.
- **The DvP term,** where the evidence supports one. The opposing unit's residuals against those baselines in its completed games this season, shrunk by n / (n + k), with a prior from last season (variant B06).

**Inputs:** only Arbit's own FFA actuals of completed regular-season games, scored under the league's rules (targets index `6ffb62fb…`), and the nflverse schedule. No provider projection enters anywhere (lineage allowlist; `forbidden_vendor_projection_dependencies = 0`).

**Timing:**
- A game counts from 12:00 UTC the day after it.
- Forecasts are made before the first game of each NFL week.
- Each season's parameters come from earlier seasons only.

## Results

Change in next-game RMSE against B00. Development is rolling folds 2017–2023; 2024 is validation; 2025 is the conditional holdout. The method was frozen in [`config/dvp/frozen.json`](../../../config/dvp/frozen.json) before 2025 ran.

| Group | Best DvP variant | Development | 2024 | 2025 (95%, week blocks) | Label (predeclared rule) | Use |
| --- | --- | --- | --- | --- | --- | --- |
| **D/ST** | B06 (k ≈ 8, last-season prior) | −3.0% | −6.4% | **−4.1%** (−0.39 to −0.11 points) | **PROMISING** | Candidate for the D/ST matchup term, after prospective confirmation and the owner's approval |
| QB | B06 | −0.9% | +0.3% | −1.1% (−0.15 to −0.02 points) | INCONCLUSIVE | None (zero DvP influence) |
| RB | B06 | −0.8% | −0.8% | −0.5% | NOT_USEFUL | None |
| WR | B06 | −0.7% | +1.2% | −0.6% | NOT_USEFUL | None |
| TE | B07 | −0.2% | −0.0% | −0.4% | NOT_USEFUL | None |
| K | B06 | −0.1% | −0.0% | −0.3% | NOT_USEFUL | None |

**The rule:** PROMISING needs the frozen candidate to cut RMSE by at least 1% in all three periods; NOT_USEFUL means the best DvP variant misses 1% in all three; anything between is INCONCLUSIVE.

**Overall: PROMISING, for D/ST only.**

**Base error** (B00, 2025 RMSE in points per team-game): QB 7.80, RB 9.76, WR 12.66, TE 8.37, K 4.76, D/ST 6.38. The D/ST term removes about 0.26 points of that error per game.

## Start/sit decisions (Phase C, D/ST)

Pairwise start/sit accuracy of the frozen B06 against B00, over every pair of D/STs playing the same week, with the rule declared before the run ([PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md)):

| | Development | 2024 | 2025 |
| --- | --- | --- | --- |
| Accuracy, B00 → B06 | 55.7% → 60.1% | 53.8% → 62.3% | 55.3% → 62.0% |
| Change, points (95%) | +4.4 (3.3 to 5.6) | +8.5 (4.1 to 12.5) | +6.6 (2.6 to 10.5) |
| Points per changed choice | +1.56 | +2.68 | +1.83 |

**Phase C: PROMISING.** The minimum was 1.8 points, with net points gained in every period.

## Conclusions by position

Specification §11 ("before completion"). Repeatability is Phase A; forward benefit is Phases B–C. They are separate questions.

| Group | Repeatable trait? | Forward benefit? | Effect-size estimate | Uncertainty | Stable across seasons? | Recommended use | Limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **D/ST** | **Yes, strong:** k ≈ 7.2, 12% per game; carries into next season (r 0.40) | **Yes:** RMSE and start/sit both PROMISING | RMSE −3.0% dev, −6.4% 2024, −4.1% 2025; start/sit +4.4 to +8.5 accuracy points | 2025 ΔRMSE −0.39 to −0.11 points; accuracy intervals exclude 0 in every period | Yes: helped in 9 of 9 seasons (−0.15 to −0.41 points) | Candidate D/ST matchup term (B06, k ≈ 8, last-season prior) after prospective confirmation and owner approval | 2025 conditionally held out; one short prospective window; regret per choice up to 40 points |
| QB | Modest: k ≈ 24 (16–42); drifts within a season | No (INCONCLUSIVE) | −0.9% dev, +0.3% 2024, −1.1% 2025 | 2025 −0.15 to −0.02 points | Mostly: 8 of 9 seasons, but 2024 worse | None (zero DvP influence) | Within-season drift; no player-level test (gate not met) |
| RB | Modest: k ≈ 20 (16–27); rushing yards repeat fastest | No (NOT_USEFUL) | −0.8%, −0.8%, −0.5% | 2025 −0.16 to +0.06 points | 8 of 9 seasons, all under 1% | None | Under the 1% practical minimum everywhere |
| WR | Weak: k ≈ 27 (18–58); v0's 44 was an unlucky split | No (NOT_USEFUL) | −0.7%, +1.2%, −0.6% | 2025 −0.19 to +0.03 points | Mostly (8 of 9), but 2024 worse by 0.16 points | None | Touchdowns allowed are noise (k ≈ 180); raw WR mostly season-wide scoring |
| TE | Weak: k ≈ 37 (23–97) | No (NOT_USEFUL) | −0.2%, −0.0%, −0.4% | 2025 −0.06 to −0.002 points | 8 of 9 seasons, all tiny (−0.04 to +0.02 points) | None | Under 0.4% everywhere |
| K | Weakest: k ≈ 50 (33–101) | No (NOT_USEFUL) | −0.1%, −0.0%, −0.3% | 2025 −0.03 to +0.003 points | 7 of 9 seasons, all near 0 (−0.02 to +0.01 points) | None | Field goals don't repeat (k ≈ 164) |

**Integrity flags** (machine-checked in [verify-receipt.json](verify-receipt.json), [backtest-holdout.json](backtest-holdout.json) and the T29–T40 tests):

| Flag | Value |
| --- | --- |
| `source_provenance_pass` | true: lineage allowlist, scoring hash, code scan (A11, T30–T33, T37, T40) |
| `score_finality_pass` | true: completed games only, available at 12:00 UTC the next day ([SCORE_FINALITY_AUDIT.json](SCORE_FINALITY_AUDIT.json), T34–T36, T39) |
| `forbidden_vendor_projection_dependencies` | 0 |
| 2025 holdout status | CONDITIONALLY_HELD_OUT: v0 and Phase A described 2025; no 2025 forecast or parameter entered selection |
| Reproduction | All 468 committed metrics recompute exactly from the stored forecasts. The 2025 holdout reruns from the frozen commit with forecasts equal to within 7×10⁻¹⁵ points (the last bit of polars' parallel sums) and identical results |

## Intended use

- **The D/ST matchup.** An opponent's tendency to concede D/ST points (sacks, low scoring, few yards) is real, stable within a season, and carries over between seasons. A D/ST start decision should weigh it, shrunk with k ≈ 8 and a last-season prior.
- **Explaining "why"** (OWN-068). For D/ST, the opponent term is a measured contribution. For other positions, the honest explanation is that the opponent's record against the position doesn't predict next week's points beyond the offense's own form.

## Not intended

- **Raw "points allowed to position" rankings.** Used at face value, they make QB-to-K forecasts 4–13% worse and are no better for D/ST.
- **QB, RB, WR, TE and K matchup adjustments at the group level.** They are not supported. Phase C did not run for them, because the specification starts it only after a group-level signal.
- **Reading w(n) as a share of a Sit/Start model.** It is credibility inside the DvP estimate.
- **Anything beyond 2016–2026 FFA rules** without re-checking the scoring hash.

## Limits

- **2025 is conditionally held out.** v0 and the Phase A reliability lab described 2016–2025, 2025 included, though no 2025 forecast or parameter entered selection. Independent confirmation is the prospective 2026 window ([PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)).
- **Final revisions only.** The actuals are final revisions. Stat corrections that arrived after a cutoff can't be replayed before 2026; they were negligible where measured (A12).
- **D/ST start/sit is measured on pairs, not on real lineups.** Arbit has FFA lineups only for 2026, so league-constrained lineup evaluation is BLOCKED for 2016–2025 ([PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md)).
- **Chance at the 1% scale.** One noise placebo improved 2025 TE RMSE by 0.65%. Changes under 1% can arise by chance, so the threshold is a real guard.
- **Performance:** with polars' default thread pool the walk-forward is slow on small frames, so runs set `POLARS_MAX_THREADS=2`. Receipts record it.

## Safety and fallback

- **Fallback to B00:** with no opponent history or prior, the D/ST term is zero and the forecast is B00. The same holds when k can't be estimated (an infinite k gives no weight).
- **Fails closed:** a planted projection column (`UNKNOWN_COLUMN`) or a holdout without a matching frozen manifest stops the run.

## Eligibility for promotion

**Not eligible yet.** It needs both of these:
1. The prospective 2026 window (weeks 12–18, frozen before any of those games) confirms the D/ST term on games played after the freeze. That means both levels: forecast error (`config/dvp/frozen.json`) and start/sit choices (`config/dvp/frozen-phase-c.json`).
2. The owner approves a production weight (OWN-074).

Until then, `feature_specs` keeps v0's constants. No advisor uses this.

## Provenance

| Item | Where |
| --- | --- |
| Code | `arbit_model.dvp` (walkforward, lab, asof, observations, reliability, provenance, decisions), `scripts/model/dvp.py` |
| Holdout run | Code `165d140`, every frozen hash verified |
| Receipts | [backtest-development.json](backtest-development.json), [backtest-validation.json](backtest-validation.json), [backtest-holdout.json](backtest-holdout.json), [sitstart.json](sitstart.json), [verify-receipt.json](verify-receipt.json), [METRICS.csv](METRICS.csv) |
| Frozen method and decision rule | `config/dvp/frozen.json`; Phase C: `config/dvp/sitstart.json`, `config/dvp/frozen-phase-c.json` |
| Reports | [BACKTEST_REPORT.md](BACKTEST_REPORT.md), [RELIABILITY_REPORT.md](RELIABILITY_REPORT.md), [METHODOLOGY.md](METHODOLOGY.md) |
