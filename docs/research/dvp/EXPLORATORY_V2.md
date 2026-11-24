# M3-3 DvP exploratory run v2: decoupled stages, rolling windows and split-half k

Owner audit AUD-05 (remediation 5) and AUD-03 (remediation 3). TASK-20261124-007. Receipt: [explore-v2.json](explore-v2.json), run `run-20261124-82f2711` at code `82f2711`. Declared first in [`config/dvp/explore-v2.json`](../../../config/dvp/explore-v2.json).

**Classification: EXPLORATORY.** These estimators came after the 2025 holdout was inspected:
- none of them is confirmatory;
- none changes the frozen candidates or the 2026 confirmation;
- at most, a promising one can be proposed for a new, separately frozen test on future games.

## Decoupled stages (AUD-05)

The frozen engine took its forecast targets from valid observation rows, so a cell whose label later turned out invalid was never forecast. It also wrote its forecast file after joining labels. The v2 run keeps the seven stages apart:

| Stage | What happens | Where |
| --- | --- | --- |
| 1. Scheduled targets | Every scheduled regular-season team-game × position group, from the schedule alone | `shadow.scheduled_targets` |
| 2. Point-in-time features | The frozen audit run's observations, every row checked by the contract, as of each preweek cutoff | `shadow.prepare_checked`, `asof.features_as_of` |
| 3. Forecast-only outputs | The frozen walk's own steps, plus the exploratory estimators; no label, score or status column | `shadow.walk_targets`, `shadow.forecast_only` |
| 4. Persistence | Each stage written once with SHA-256 and a manifest stating `labelsRead: false` | `dvp_explore.py forecast` |
| 5. Label retrieval | A separate command reads the observations, after checking the forecast hashes | `dvp_explore.py evaluate` |
| 6. Evaluation join | Labels joined by (game_id, offense, position) without dropping a target | `shadow.attach_labels` |
| 7. Coverage | Targets and label status per stage and position; only valid labels enter metrics | `shadow.coverage` |

**Coverage.** Each line gives targets / valid labels / refused-line labels, for K, RB, TE and WR. D/ST and QB have every label valid in all three stages.

| Stage | Targets per position | K | RB | TE | WR |
| --- | --- | --- | --- | --- | --- |
| Development 2017–2023 | 3,678 | 3,671 valid / 7 refused | 3,671 / 7 | 3,671 / 7 | 3,669 / 9 |
| 2024 | 544 | 543 / 1 | 543 / 1 | 543 / 1 | 542 / 2 |
| 2025 | 544 | 542 / 2 | 542 / 2 | 542 / 2 | 542 / 2 |

The refused-line cells now have forecasts. Their labels are reported as invalid instead of being removed before prediction.

**Reproduction.** On the valid rows, every frozen variant's RMSE, MAE, mean error, ΔRMSE and bootstrap interval equals the committed v1 receipts in all three stages and all six positions (`v1ReproducedOnValidRows: true`). Decoupling changes no reported result. The tests (`test_dvp_shadow.py`) show that:
- deleting later results, flipping their validity, changing their points or correcting them retroactively changes neither the earlier targets nor the earlier forecasts;
- an unplayed week can be forecast from the schedule alone.

## Rolling windows and split-half k (AUD-03)

New estimators, run inside the same walk on the same rows (`arbit_model.dvp.explore`):
- **`b05w3`, `b05w5`, `b05w8`:** the mean of the opposing unit's last 3, 5 or 8 point-in-time residuals, shrunk by n_m/(n_m + k) with the fold's REML k. With no game the forecast is B00.
- **`b03sh`:** B03 with v0's split-half k, from the training seasons only.

A built-in check recomputes the frozen B03 from the same residual history and stops on any difference.

**Change in RMSE against B00** (negative is better; the 1% practical minimum is the bar used everywhere):

| Group | Stage | B03 (REML k) | **B03sh (split-half k)** | B05 exp. h8 | **3-game** | **5-game** | **8-game** | B06 (frozen D/ST candidate) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D/ST | Development | −2.65% | −2.66% | −2.67% | −1.54% | −2.19% | −2.58% | **−2.99%** |
| D/ST | 2024 | −5.35% | −5.18% | −5.10% | −2.94% | −3.65% | −4.53% | **−6.36%** |
| D/ST | 2025 | −3.38% | −3.32% | −3.28% | −1.25% | −2.51% | −3.29% | **−4.06%** |
| QB | Development | −0.59% | −0.58% | −0.66% | −0.46% | −0.61% | −0.62% | −0.85% |
| QB | 2024 | −0.19% | −0.18% | −0.11% | −0.03% | −0.25% | −0.18% | +0.26% |
| QB | 2025 | −1.05% | −1.08% | −1.10% | −0.61% | −0.94% | −0.86% | −1.14% |
| RB | Development | −0.65% | −0.60% | −0.68% | −0.38% | −0.60% | −0.55% | −0.84% |
| RB | 2024 | −0.46% | −0.47% | −0.44% | −0.08% | −0.27% | −0.43% | −0.84% |
| RB | 2025 | −0.36% | −0.36% | −0.57% | −0.63% | −0.80% | −0.44% | −0.54% |
| WR | Development | −0.51% | −0.38% | −0.57% | −0.28% | −0.44% | −0.52% | −0.74% |
| WR | 2024 | +0.73% | +0.48% | +0.73% | +0.40% | +0.48% | +0.50% | +1.21% |
| WR | 2025 | −0.90% | −0.69% | −0.80% | −0.24% | −0.27% | −0.47% | −0.58% |
| TE | Development | −0.10% | −0.13% | −0.08% | +0.02% | −0.11% | −0.11% | −0.10% |
| TE | 2025 | −0.62% | −0.57% | −0.62% | −0.25% | −0.52% | −0.59% | −0.81% |
| K | Development | −0.05% | +0.04% | −0.07% | −0.04% | −0.07% | −0.08% | −0.12% |
| K | 2025 | −0.26% | −0.24% | −0.30% | −0.15% | −0.27% | −0.27% | −0.30% |

The receipt holds every stage, interval, MAE and the comparison with B04 (grid k). TE and K 2024 are left out of the table above: every estimator there is within 0.3% of B00.

**Findings:**
- **Rolling windows don't beat full-season shrinkage.** The shorter the window, the worse, at every position.
  - For D/ST, the 3-game window keeps about half of B03's gain, and the 8-game window is close to B03.
  - Dropping a unit's older games this season throws away signal. This matches Phase A's finding that the D/ST tendency is stable within a season (A06).
- **QB doesn't gain from short windows** despite its within-season drift (A06). Recency is already captured by exponential weighting (B05), which does no better.
- **RB 2025 is the only place a window does best:** the 5-game window reaches −0.80% against B06's −0.54%. It is worse than B06 in development (−0.60% against −0.84%) and in 2024 (−0.27% against −0.84%). It is under 1% everywhere, so it doesn't replicate.
- **Split-half k forecasts about as well as REML k,** even where the two k differ a lot:
  - D/ST: −2.66% against −2.65% in development, −3.32% against −3.38% in 2025.
  - WR split-half k ranges from 10 to 55 games across folds, against REML's 19 to 30. The forecast changes little because shrinkage is flat near those k.
  - The original v0 method was not the problem; REML is the steadier estimate of the same thing.
- **Nothing beats the frozen B06 for D/ST** in any stage. No exploratory estimator crosses 1% for any position other than D/ST.

**k by fold** (games for half signal):

| Fold | D/ST REML / split-half | QB | RB | WR | TE | K |
| --- | --- | --- | --- | --- | --- | --- |
| 2017 | 5.3 / 8.7 | 31.1 / 12.7 | 20.1 / 33.9 | 19.0 / 10.2 | 16.2 / 16.7 | 31.4 / 16.7 |
| 2020 | 7.5 / 8.8 | 19.7 / 19.2 | 20.0 / 18.8 | 30.1 / 35.2 | 39.8 / 39.7 | 78.6 / 270.1 |
| 2023 | 8.0 / 8.9 | 25.6 / 24.4 | 18.2 / 19.1 | 30.4 / 55.3 | 31.5 / 30.7 | 52.4 / 62.2 |
| 2024 | 8.0 / 9.3 | 24.8 / 22.5 | 18.8 / 20.3 | 24.0 / 36.5 | 38.7 / 40.9 | 56.0 / 59.6 |
| 2025 | 7.4 / 8.8 | 27.3 / 25.0 | 18.8 / 20.2 | 28.9 / 48.0 | 41.5 / 48.1 | 58.7 / 69.9 |

Split-half k is noisier from fold to fold (K's 270 games in 2020), as A02 found for split methods. REML uses every unit's own game count.

## Comparison with the original M3-3 results

| Original conclusion | After v2 |
| --- | --- |
| D/ST B06 is PROMISING; QB INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL | Unchanged. No exploratory estimator changes a position's picture |
| Shrinkage is the whole story; unshrunk DvP hurts | Reinforced: shorter windows behave like less shrinkage toward the season's evidence and do worse |
| Tuned k (B04) matches REML | Split-half k does too, within noise |
| Results on valid cells | Identical when the targets come from the schedule. The refused-line cells are now forecast and reported as invalid labels |
