# M3-3 DvP backtest report (Phase 3: B00–B12, development and 2024 validation)

Specification §5 Phase B, §7, §9 Phase 3, §11.7. TASK-20261124-002.

**Receipts:**
- [backtest-development.json](backtest-development.json): code `d811711`;
- [backtest-validation.json](backtest-validation.json): code `3a920c2`;
- [frozen-candidates.json](../../../config/dvp/frozen-candidates.json), frozen at 2026-11-24 03:05 UTC, before validation ran;
- forecasts in `artifacts/dvp/phase1-audit-20261124T024442Z/backtest-*/forecasts.parquet`, with their hashes in the receipts.

Settings and scope:
- **Command:** `scripts/model/dvp.py backtest`, with `POLARS_MAX_THREADS=2`.
- **Run:** seed 1729, 2,000 block-bootstrap replicates.
- **Truth:** every forecast and label is Arbit's own FFA actuals of completed regular-season games. Projection dependencies: 0.
- **2025 is untouched:** no 2025 forecast was made or inspected.

## Setup

- **Folds:**
  - **Development:** rolling origin, 2017–2023. Every parameter for season s is fit on seasons before s.
  - **Validation:** 2024, fit on 2016–2023, with the choices frozen after development.
  - **Holdout:** not run here (Phase 4).
- **Cutoff:** before the first game of each NFL week. A game's actuals count from 12:00 UTC the day after it (`features_as_of`). Forecasts are frozen and join their labels only through `evaluation_join` (T20).
- **B00, the comparator** (declared in [METHODOLOGY.md](METHODOLOGY.md) before it ran). It uses only the scoring side's own history: its last season regressed toward the league by a training-fit slope, then updated with this season's completed games using its own training-fit k. The scoring side is the offense for QB to K and the D/ST for D/ST.
- **DvP variants** add the opposing unit's residuals against the point-in-time B00 forecasts of its completed games this season:

  | Variant | Term |
  | --- | --- |
  | B01 | Raw points allowed minus the league mean |
  | B02 | Residual, unshrunk (B02r: baselines recomputed at the current cutoff) |
  | B03 | Residual × n/(n + k), with k fit on training seasons (B03r: recomputed baselines) |
  | B04 | The same with k from a declared grid (1–256), tuned on development |
  | B05 | Recency-weighted residual (half-life 2, 4 or 8 games), tuned on development |
  | B06 | Residual shrunk toward last season's residual × a training-fit slope |
  | B07 | B03 on non-touchdown points |
- **Practical minimum:** a variant must cut a position's development RMSE by at least 1% of B00's to become its candidate. This was fixed in `config/dvp/backtest.json` before any forecast ran.

## The comparator

| Group | Development RMSE / MAE / bias / Spearman | 2024 RMSE / MAE / bias / Spearman |
| --- | --- | --- |
| QB | 7.58 / 6.03 / +0.17 / 0.27 | 7.45 / 5.88 / −0.74 / 0.28 |
| RB | 9.87 / 7.74 / +0.14 / 0.25 | 9.20 / 7.21 / −0.15 / 0.24 |
| WR | 13.24 / 10.54 / +0.55 / 0.35 | 13.19 / 10.54 / −0.39 / 0.23 |
| TE | 7.66 / 6.03 / +0.06 / 0.33 | 7.67 / 5.77 / −0.67 / 0.33 |
| K | 4.51 / 3.60 / −0.00 / 0.10 | 4.87 / 3.85 / −0.24 / 0.10 |
| D/ST | 6.64 / 5.20 / −0.12 / 0.14 | 6.40 / 5.15 / +0.79 / 0.09 |

B00 is calibrated across deciles in development (QB: forecast 13.1 → 21.5, observed 13.3 → 21.5). A team-game total is mostly noise around a modest offense signal, which is why Spearman is 0.1–0.35.

## Development, 2017–2023 (change in RMSE vs B00, 95% season-block bootstrap)

| Group | B01 raw | B02 unshrunk | B03 shrunk | B04 tuned | B05 recency | **B06 with prior** | B07 non-TD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QB | +7.5% | +7.2% | −0.6% (−0.9, −0.4) | −0.6% (k 16) | −0.7% (h 4) | **−0.9% (−1.3, −0.5)** | −0.5% |
| RB | +7.5% | +7.3% | −0.6% (−1.0, −0.2) | −0.7% (k 16) | −0.7% (h 8) | **−0.8% (−1.2, −0.3)** | −0.5% |
| WR | +8.4% | +8.0% | −0.5% (−0.9, −0.3) | −0.5% (k 16) | −0.6% (h 8) | **−0.7% (−1.2, −0.3)** | −0.5% |
| TE | +8.4% | +8.2% | −0.1% (−0.4, +0.2) | −0.2% (k 32) | −0.1% (h 8) | −0.1% | **−0.2% (−0.3, −0.0)** |
| K | +8.1% | +8.3% | −0.1% (−0.2, +0.1) | −0.1% (k 64) | −0.1% (h 4) | **−0.1% (−0.3, +0.1)** | −0.1% |
| **D/ST** | +3.9% | +3.9% | −2.7% (−3.0, −2.4) | −2.7% (k 8) | −2.7% (h 8) | **−3.0% (−3.4, −2.6)** | −2.8% |

**Candidates frozen from development:**
- **D/ST: B06.** It clears the 1% minimum by a wide margin and improved in every one of the seven seasons.
- **QB, RB, WR, TE and K: B00.** Their best DvP variants gain 0.1–0.9%, below the minimum. For QB, RB and WR the gain is consistent (the intervals exclude 0) but small.

## Validation, 2024 (choices frozen; 95% week-block bootstrap)

| Group | Candidate | Its development change | **2024 change** | Same direction? | Meets the 1% minimum? |
| --- | --- | --- | --- | --- | --- |
| **D/ST** | **B06** | −3.0% | **−6.4% (−8.7, −4.2)** | yes | **yes** |
| QB | B00 (best DvP: B06) | −0.9% | +0.3% (−0.6, +1.1) | **no** | no |
| RB | B00 (B06) | −0.8% | −0.8% (−2.4, +0.7) | yes | no |
| WR | B00 (B06) | −0.7% | **+1.2% (−0.0, +2.4)** | **no** | no |
| TE | B00 (B07) | −0.2% | −0.0% (−0.4, +0.4) | yes | no |
| K | B00 (B06) | −0.1% | −0.0% (−0.6, +0.5) | yes | no |

In 2024, shrunk WR DvP (B03) was *worse* than B00 by 0.7% (0.2 to 1.2). For QB, RB, TE and K the 2024 intervals span zero.

**Plot:** [backtest-delta.svg](plots/backtest-delta.svg).

## Phase 4: the 2025 conditional holdout

The method was frozen in [`config/dvp/frozen.json`](../../../config/dvp/frozen.json) at 2026-11-24 03:16 UTC, before 2025 was forecast. It holds the hashes of the method files, configs and candidates, the audit run's outputs, the protocol, and the decision rule. The holdout stage verified every hash before running (code `165d140`; receipt [backtest-holdout.json](backtest-holdout.json)). Parameters were fit on 2016–2024.

| Group | Best DvP variant | 2025 change in RMSE (95%, week blocks) | Label |
| --- | --- | --- | --- |
| **D/ST** | B06 (the frozen candidate) | **−4.1% (−0.39 to −0.11 points)** | **PROMISING** |
| QB | B06 | −1.1% (−0.15 to −0.02) | INCONCLUSIVE: meets 1% only in 2025 |
| RB | B06 | −0.5% (−0.16 to +0.06) | NOT_USEFUL |
| WR | B06 | −0.6% (−0.19 to +0.03) | NOT_USEFUL |
| TE | B07 | −0.4% (−0.06 to −0.00) | NOT_USEFUL |
| K | B06 | −0.3% (−0.03 to +0.00) | NOT_USEFUL |

**Overall: PROMISING, for D/ST only.**
- **Status:** `CONDITIONALLY_HELD_OUT`. v0 and Phase A described 2025, but no 2025 forecast or parameter entered selection.
- **Placebos in 2025:** they give no uplift except one. The noise term improved TE by 0.65%, a reminder that sub-1% changes arise by chance.
- **Confirmation:** independent confirmation is the prospective 2026 window ([PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)).
- **Model card:** [MODEL_CARD.md](MODEL_CARD.md).

## What the variants teach

- **Shrinkage is the whole story.** Unshrunk DvP, whether a raw "points allowed" ranking (B01) or a residual (B02), makes QB-to-K forecasts 7–8% worse in development and 6–13% worse in 2024. For D/ST it is 4% worse in development and about even in 2024. A defense's season-to-date average is mostly noise, as Phase 2 found (k 20–50 games). Using it at face value hurts.
- **Tuned k matches Phase 2.** B04's best k is D/ST 8, QB, RB and WR 16, TE 32 and K 64, close to the REML values (D/ST 7, RB 20, QB 24, WR 27, TE 37, K 50). The k fit on training seasons alone does about as well as the tuned one.
- **A prior from last season helps** (B06 is best for five groups). This matches A07's carryover.
- **Recency weighting adds little.** For QB, despite its in-season drift, it is −0.7% against −0.6% in development, and nothing in 2024.
- **Non-touchdown residuals (B07)** do about as well as full ones: D/ST −2.8%, and within 0.02 RMSE points of B03 elsewhere. They are no clear improvement.
- **Recomputed baselines (B03r)** do no better than point-in-time ones (B03). The forecast doesn't need the extra machinery.

## Controls, diagnostics and sensitivity

- **B09, negative controls.** None improves meaningfully on B00; the largest gain is 0.3%, within noise:

  | Group | Shuffled opponents, dev / 2024 | Noise of the same spread, dev / 2024 | Last week's opponent, dev / 2024 |
  | --- | --- | --- | --- |
  | QB | +0.4% / +0.2% | +0.5% / +0.5% | +0.2% / +0.2% |
  | RB | +0.5% / +1.1% | +0.9% / +0.4% | +0.4% / +0.1% |
  | WR | +0.3% / +0.5% | +0.2% / +0.4% | +0.2% / +0.6% |
  | TE | +0.3% / −0.1% | +0.7% / +0.3% | +0.3% / −0.3% |
  | K | −0.0% / +0.0% | +0.5% / −0.3% | −0.0% / +0.2% |
  | D/ST | +1.8% / +2.9% | +4.0% / +3.6% | +2.6% / +1.3% |

  The D/ST gain comes from the actual opponent, not from adding any term (T24 on real data).
- **B08, where D/ST's gain comes from:**
  - **By opponent games:** in development, B06's gain grows with the opponent's games this season: −0.10 points with none (the prior alone), −0.17 after 1–3, −0.20 after 4–7 and −0.22 after 8 or more.
  - **By week:** in 2024 the gain is −0.20 in weeks 1–4 and −0.46 to −0.49 later.
  - **WR in 2024:** the loss comes from weeks 5–18 (+0.18 and +0.32 points); weeks 1–4 gained 0.26.
- **B10, per-game cutoffs.** Refreshing at each game's kickoff instead of before the week changed *no* B00 or B03 forecast in either stage. Each team plays once a week, so an earlier game that week only informs teams that aren't playing again. A per-game refresh can't help these estimators.
- **B12, a 48-hour slower availability rule.** In development it changes 6 B00 and 26 B03 forecasts, games whose results would arrive within 48 hours of the next week's first kickoff; in 2024, 2 and 6. RMSE moves by under 0.001. The conservative rule costs essentially nothing.
- **B11, contamination.** A planted provider projection, under its own name or renamed `opponent_expected`, stops the pipeline (`UNKNOWN_COLUMN`, tests).

## Status per spec gate (Phase 3)

| Item | Result |
| --- | --- |
| Method and metrics committed before evaluation | Yes: B00 and metrics in METHODOLOGY.md; practical minimum in the config before any forecast; candidates frozen before validation |
| Leakage tests | T15–T20, T22, T24 and T25 pass on synthetic seasons; T13 and B11 pass |
| `forbidden_vendor_projection_dependencies` | 0 |
| 2025 exposure | Seen descriptively by v0 and Phase A. No 2025 forecast was made or inspected before the freeze, and no parameter was fit on it. Phase 4 then used it as `CONDITIONALLY_HELD_OUT` (above) |

## Where this points (no production decision is made here)

- **D/ST:** the one group where DvP earns a place. B06 (k fit on training seasons, about 8, with a last-season prior) beats B00 by 3% in development and 6% in 2024. Phase 4 tests the frozen candidate on 2025, then on prospectively frozen 2026 games.
- **QB, RB, WR, TE and K:** the group-level matchup adds less than 1% in development and didn't replicate in 2024 (WR got worse). Expected label: `INCONCLUSIVE` (QB, RB) or `NOT_USEFUL` (WR, TE, K). That means zero DvP influence in a Sit/Start model unless a player-level test (Phase C) independently shows value.
- **Never use unshrunk DvP rankings:** they make forecasts worse at every position.
- **Weights are unchanged.** `feature_specs` still holds v0's constants, and no production weight changes without the owner (OWN-074).
