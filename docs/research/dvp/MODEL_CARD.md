# Model card: M3-3 defense against the position (DvP)

Specification §11.8, §12. TASK-20261124-003. **Research artifact. It is not in production and changes no weight;** any use in Arbit's Sit/Start model needs the owner's approval (OWN-074).

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

## Intended use

- **The D/ST matchup.** An opponent's tendency to concede D/ST points (sacks, low scoring, few yards) is real, stable within a season, and carries over between seasons. A D/ST start decision should weigh it, shrunk with k ≈ 8 and a last-season prior.
- **Explaining "why"** (OWN-068). For D/ST, the opponent term is a measured contribution. For other positions, the honest explanation is that the opponent's record against the position doesn't predict next week's points beyond the offense's own form.

## Not intended

- **Raw "points allowed to position" rankings.** Used at face value, they make QB-to-K forecasts 4–13% worse and are no better for D/ST.
- **QB, RB, WR, TE and K matchup adjustments at the group level.** They are not supported; a player-level effect would need its own test (Phase C).
- **Reading w(n) as a share of a Sit/Start model.** It is credibility inside the DvP estimate.
- **Anything beyond 2016–2026 FFA rules** without re-checking the scoring hash.

## Limits

- **2025 is conditionally held out.** v0 and the Phase A reliability lab described 2016–2025, 2025 included, though no 2025 forecast or parameter entered selection. Independent confirmation is the prospective 2026 window ([PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)).
- **Final revisions only.** The actuals are final revisions. Stat corrections that arrived after a cutoff can't be replayed before 2026; they were negligible where measured (A12).
- **Team-position totals, not players.** How a D/ST term translates into start/sit choices is Phase C.
- **Chance at the 1% scale.** One noise placebo improved 2025 TE RMSE by 0.65%. Changes under 1% can arise by chance, so the threshold is a real guard.
- **Performance:** with polars' default thread pool the walk-forward is slow on small frames, so runs set `POLARS_MAX_THREADS=2`. Receipts record it.

## Safety and fallback

- **Fallback to B00:** with no opponent history or prior, the D/ST term is zero and the forecast is B00. The same holds when k can't be estimated (an infinite k gives no weight).
- **Fails closed:** a planted projection column (`UNKNOWN_COLUMN`) or a holdout without a matching frozen manifest stops the run.

## Eligibility for promotion

**Not eligible yet.** It needs both of these:
1. The prospective 2026 window (weeks 12–18, frozen before any of those games) confirms the D/ST term on games played after the freeze.
2. The owner approves a production weight (OWN-074).

Until then, `feature_specs` keeps v0's constants. No advisor uses this.

## Provenance

| Item | Where |
| --- | --- |
| Code | `arbit_model.dvp` (walkforward, lab, asof, observations, reliability, provenance), `scripts/model/dvp.py` |
| Holdout run | Code `165d140`, every frozen hash verified |
| Receipts | [backtest-development.json](backtest-development.json), [backtest-validation.json](backtest-validation.json), [backtest-holdout.json](backtest-holdout.json) |
| Frozen method and decision rule | `config/dvp/frozen.json` |
| Reports | [BACKTEST_REPORT.md](BACKTEST_REPORT.md), [RELIABILITY_REPORT.md](RELIABILITY_REPORT.md), [METHODOLOGY.md](METHODOLOGY.md) |
