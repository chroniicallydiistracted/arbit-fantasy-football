# M3-3 Phase C: D/ST start/sit decisions

Specification §5 Phase C, §7 and §9 Phase 5. TASK-20261124-004. **Research only:** nothing here changes a weight, a table or the app.

**Question:** the frozen D/ST matchup term (B06) cuts next-game error by 3–6%. Does it also make better start/sit choices than the offense-only B00?

**Answer: yes.** B06 starts the higher-scoring D/ST more often in every period. The gain is 4.4 to 8.5 points of pairwise accuracy, against a minimum of 1.8 declared before the run. **Phase C label: PROMISING.**

As with the group-level result, independent confirmation is the 2026 weeks 12–18 window, which was frozen before those games ([PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)).

## Scope

- **D/ST only.** Phase C starts only for a group with a credible group-level signal (§5).
  - D/ST is the only one: it is PROMISING.
  - QB is INCONCLUSIVE, and RB, WR, TE and K are NOT_USEFUL.
  - Not running Phase C for them is the specification's gate, not a finding about individual players.
- **A D/ST is one unit per team.** Its group-level forecast is its player-level forecast, with a share of 1, so allocation is not a question (C01, C02).
  - The forecast row for offense O carries the points of the D/ST that faced O.
  - `decisions.units` checks both halves of that against the canonical observations, and fails closed otherwise:
    - the row is oriented to the offense;
    - the scoring D/ST is the game's other team.
- **C00, the baseline,** is B00, Arbit's offense-only forecast from prior FFA actuals.
  - Arbit has no other player projection: the app shows "Projections off".
  - No provider projection enters anywhere.

## Declared before any result

The rule in [`config/dvp/sitstart.json`](../../../config/dvp/sitstart.json) was committed (`317361f`, pushed 2026-11-24 06:48 UTC) before Phase C was computed (`bac02af`).

| Item | Declaration |
| --- | --- |
| Pairs | Every unordered pair of D/STs that both play in the same week. Each model starts the higher forecast |
| Ties | A pair whose units scored the same is excluded from accuracy. A forecast tie earns 0.5 |
| Primary metric | B06's pairwise accuracy minus B00's, in percentage points |
| Practical minimum | **1.8 points:** the accuracy change implied by Phase B's 1% RMSE minimum at B00's development correlation (0.1448), under a bivariate normal. Only B00 development data entered it |
| Rule | **PROMISING** if the change is ≥ 1.8 points and changed choices gain net points in development, 2024 and 2025. **NOT_USEFUL** if it misses 1.8 in all three. **INCONCLUSIVE** otherwise. **BLOCKED** on an integrity failure |
| Uncertainty | Week-block bootstrap: 2,000 replicates, seed 1729 |
| Inputs | Each stage's frozen forecasts, checked against the hash in its receipt. Nothing is fit or tuned |

## Results

**Receipt:** [`sitstart.json`](sitstart.json). **Plot:** [`plots/sitstart.svg`](plots/sitstart.svg).

| | Development 2017–2023 | Validation 2024 | Holdout 2025 (conditional) |
| --- | --- | --- | --- |
| D/ST team-games / weeks / pairs | 3,678 / 122 / 53,867 | 544 / 18 / 7,992 | 544 / 18 / 7,984 |
| Pairwise accuracy, B00 → B06 | 55.7% → 60.1% | 53.8% → 62.3% | 55.3% → 62.0% |
| **Change (95% interval)** | **+4.4 (3.3 to 5.6)** | **+8.5 (4.1 to 12.5)** | **+6.6 (2.6 to 10.5)** |
| Choices B06 changes | 33% of pairs | 37% | 38% |
| B06 right when it changes the choice | 56.9% | 61.5% | 58.7% |
| Points per changed choice | +1.56 | +2.68 | +1.83 |
| Worst single changed choice | −40 | −24 | −34 |
| Within-week rank correlation, B00 → B06 | 0.16 → 0.28 | 0.09 → 0.33 | 0.15 → 0.32 |
| League top 8 per week (points of the 8 highest-forecast D/STs), B00 → B06 | 59.0 → 66.7 | 48.7 → 67.8 | 56.1 → 66.6 |
| Close pairs (B00 forecasts within 1 point) | +6.1 | +8.2 | +10.0 |
| Waiver-pool proxy (both ranked 9–24 by B00) | +7.1 | +10.1 | +9.5 |

**In plain terms:**
1. **B00 barely ranks D/STs.** It is right in 54–56% of pairs, little better than a coin. Its offense-only view knows the D/ST's opponent only through that opponent's own record.
2. **B06 adds the opponent's tendency to concede D/ST points.** It is right in 60–62% of pairs.
3. **When B06 disagrees with B00, B06 is right 57–61% of the time.** It gains 1.6–2.7 actual points per changed choice.
4. **The gain holds where decisions are hard and where they are realistic.** That covers close calls and the D/STs an 8-team league usually leaves on waivers.
5. **Across a league's eight starting D/STs a week,** B06's top eight outscore B00's by about 8–19 points, or 1–2.4 points per start.

**Regret is real.** A changed choice can lose up to 40 points in one pair, and 28 of 122 development weeks had a net loss across all pairs. The term improves the odds; it doesn't guarantee a week.

## What is not available

- **League-constrained evaluation (part of C05)** was split by the owner's Phase B audit (OWN-076: 2026 is FFA's inaugural season), [LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md):
  - **C05L-HIST (2016–2025): NOT_APPLICABLE.** FFA didn't exist, so the pairwise and top-8 measures here are the legitimate method for those seasons.
  - **C05L-2026-EXP: done, exploratory.**
    - Weeks 1–11 used rosters and claimable free agents rebuilt at each cutoff.
    - Start decisions (28): −6 points; streaming (88): +46 points.
    - Both intervals span zero widely: too few decisions to measure.
  - **C05L-2026-PRO: pending,** with weeks 12–18 captured prospectively.
- **The waiver-pool subgroup is an assumption:** that an 8-team league rosters the top 8 by B00. It is reported, not used in the rule.
- **C03 (route, slot or target-share roles):** BLOCKED. It has no meaning for a D/ST.

## Independence

- **The 2025 forecasts are the same frozen ones already scored for group-level RMSE.** No Phase C quantity was computed before the rule was declared, and nothing was tuned.
- **2025 is CONDITIONALLY_HELD_OUT here too.** Independent confirmation comes from the prospective window:
  - [`config/dvp/frozen-phase-c.json`](../../../config/dvp/frozen-phase-c.json) froze `decisions.py`, this configuration and the parameters at 2026-11-24 06:57 UTC;
  - that is before the first 2026 week-12 kickoff (2026-11-26 01:00 UTC).

## Consequence

D/ST now clears both gates the specification sets before integration (§12):
1. The group-level forecast improves (PROMISING).
2. The player-level start/sit choices improve (PROMISING).

**It is still not eligible for promotion.** It needs:
- the prospective 2026 confirmation, at both levels;
- the owner's approval of a production weight (OWN-074).

## Reproduce

```bash
POLARS_MAX_THREADS=2 uv run python scripts/model/dvp.py sitstart --config config/dvp/sitstart.json \
  --run <main>/artifacts/dvp/phase1-audit-20261124T024442Z --receipts docs/research/dvp
```

It runs in under a second and reads only the audit run's observations and frozen forecasts.
