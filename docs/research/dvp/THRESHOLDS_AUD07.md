# M3-3 DvP: what the frozen thresholds mean (AUD-07)

Owner final directive §10 (DEC-08), TASK-20261125-001.
- **Rule:** [`config/dvp/threshold-sensitivity-v1.json`](../../../config/dvp/threshold-sensitivity-v1.json), declared and pushed before computing (`88876b8`).
- **Receipt:** [threshold-sensitivity-v1.json](threshold-sensitivity-v1.json), from `e65dcea`.

**Nothing here changes a threshold.** Phase B's 1% relative RMSE and Phase C's 1.8 points with net points gained stay frozen, as do every label and the 2026 confirmation rules. The grid below is descriptive, not an optimal rule, and is never used to choose a threshold for 2026.

## D1: the 1.8-point derivation, reproduced and qualified

**The original** ([`sitstart.json`](../../../config/dvp/sitstart.json) `practicalMinimumDerivation`):
- **The relation:** for a bivariate normal forecast and outcome with correlation ρ, the chance a forecast orders a random pair correctly is 0.5 + asin(ρ)/π.
- **The step:** a calibrated forecast's MSE is var(y)(1 − ρ²), so a 1% RMSE cut needs ρ' = √(1 − 0.99²(1 − ρ²)).
- **The inputs:** with ρ = 0.1448, D/ST B00's development Spearman, ρ' = 0.2011 and accuracy rises from 54.63% to 56.45%. **That is 1.82 points.** Reproduced exactly.

**The reviewer's reading is right.** The 1.8 points is not an exact consequence of the 1% RMSE threshold. It rests on four assumptions, none of which holds exactly here:

| Assumption | What the data say |
| --- | --- |
| Bivariate normal | D/ST points are integers with ties, skewed (−11 to 35, median 5) |
| Pearson ρ in the formula | Spearman 0.1448 was used. The actual development Pearson of B00 is 0.1504; a bivariate normal would give 0.1515. Either gives **1.77 points** instead of 1.82 |
| A calibrated forecast (MSE = var(1 − ρ²)) | True only for the best linear predictor; B00's best linear recalibration has slope 0.83 |
| Independent random pairs | The pairs are within-week D/ST pairs. The formula predicts B00's accuracy at 54.81% (at its Pearson), but it is **55.68%** |

**An RMSE change does not determine a ranking change.** Measured on the actual development forecasts:
- **A recalibration** of B00 (α + βB00) cuts RMSE by 0.068% and changes pairwise accuracy by **0.000 points**: every pair keeps its order.
- **Across the 25 D/ST variants**, the RMSE change and the accuracy change come apart:
  - B01, B02 and B02r raise RMSE by 3.9% yet raise accuracy by 3.2–3.4 points;
  - B04 at k = 1 cuts RMSE only 0.3% but gains 3.5 points, where the formula implies 0.6;
  - the B09 controls raise RMSE by 1.8–4.0% and lose 1.0–2.8 points.
- **For the shrunk variants the formula lands close:** B06 −2.985% → implied 4.42 against an actual 4.45; B03 implied 4.04 against an actual 3.85.

**Corrected interpretation:** the 1.8-point Phase C minimum is a **predeclared practical heuristic**, calibrated to Phase B's 1% at B00's development correlation under a bivariate-normal approximation. It is the right order of magnitude (1.77–1.82) but not a derived equivalence. It is preserved as frozen. The documents that called it "the accuracy change implied by" the 1% minimum now say it is a heuristic so calibrated.

## D2: sensitivity (descriptive)

**Phase B labels** under the frozen rule. At each threshold t, the best DvP variant is chosen by development RMSE, unchanged by t, and becomes the candidate if it cuts B00's RMSE by at least t in development. The rule then runs on its validation and holdout changes. **The 1% row reproduces every frozen holdout label.**

| Position (best DvP) | Development / 2024 / 2025 relative RMSE change | 0% | 0.25% | 0.5% | **1%** | 1.5% | 2% | 3% |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D/ST (B06) | −2.99% / −6.36% / −4.06% | P | P | P | **P** | P | P | I |
| QB (B06) | −0.85% / +0.26% / −1.14% | I | I | I | **I** | N | N | N |
| RB (B06) | −0.84% / −0.85% / −0.54% | P | P | P | **N** | N | N | N |
| WR (B06) | −0.74% / +1.21% / −0.58% | I | I | I | **N** | N | N | N |
| TE (B07) | −0.19% / −0.00% / −0.35% | P | I | N | **N** | N | N | N |
| K (B06) | −0.12% / −0.04% / −0.30% | P | I | N | **N** | N | N | N |

P = PROMISING, I = INCONCLUSIVE, N = NOT_USEFUL.

**Uncertainty** (development 95% interval, relative to B00's RMSE):

| Position | Development interval | 2024 and 2025 intervals |
| --- | --- | --- |
| D/ST | −3.4% to −2.6% | Exclude zero in all three periods |
| RB | −1.2% to −0.3% | Both include zero |
| WR | −1.2% to −0.3% | 2024: −0.01% to +2.4% |
| QB | −1.3% to −0.5% | 2024: −0.6% to +1.1% |
| TE | −0.35% to −0.01% | — |
| K | −0.27% to +0.06% | — |

**Phase C (D/ST only):**
- **Labels:** PROMISING at every threshold from 0 to 3 points, and INCONCLUSIVE at 5 points, because development's +4.45 misses it. The 2024 and 2025 gains are +8.55 and +6.62.
- **Net points** from changed decisions are positive in every period, with per-week 95% intervals above zero: development +173 to +279, 2024 +238 to +658, 2025 +137 to +482.
- **Coverage and the hit rate when changed:**

  | Period | Pairs | Decisions changed | B06 right when changed |
  | --- | --- | --- | --- |
  | Development | 53,867 | 32.5% | 57% |
  | 2024 | 7,992 | 37.3% | 61% |
  | 2025 | 7,984 | 38.4% | 59% |

- **Phase C for the other positions was never run,** because they missed Phase B. Their Phase C outcome under a lower Phase B threshold is not evaluated and is not inferred.

**Phase B × Phase C for D/ST:** both are PROMISING for every Phase B threshold up to 2% and every Phase C threshold up to 3 points. Only the strictest corner (3%, or 5 points) turns either INCONCLUSIVE; none turns NOT_USEFUL.

## D3: conclusions

- **Robust:**
  - D/ST B06's historical classification. It is PROMISING across the reasonable grid (0–2% and 0–3 points), with all three periods improving and their intervals excluding zero.
  - NOT_USEFUL for TE and K at any threshold above 0.25%: their gains are a fraction of a percent with intervals reaching zero.
- **Sensitive:**
  - **RB** is PROMISING at thresholds up to 0.5%: a small (0.5–0.85%), consistent improvement in all three periods, though its 2024 and 2025 intervals include zero.
  - **QB and WR** turn INCONCLUSIVE below 1%: one period worsens, 2024 for both.
  - **TE and K** are PROMISING only at 0%.
  - The frozen 1% minimum is what separates RB's small gain from a promotion. That reflects the predeclared judgement that under 1% would not change a sit/start decision. It is not evidence that RB's DvP has no signal.
- **Qualifications for the eligibility registry:**
  - RB aggregate DvP shows a consistent sub-threshold improvement, not "no signal". Unsupported at the practical minimum.
  - QB is inconclusive, with one period worse.
  - WR is unsupported at 1%; inconclusive at 0.5% or below.
- **Governance for later slices:**
  - Declare practical minima as practical heuristics, and say what they were calibrated to and what they assume.
  - Report every candidate's outcome at a small threshold grid beside the frozen one, so a near-threshold finding is visible without being promoted.
  - Never pick a threshold after seeing which one promotes.
  - Where a ranking decision matters, measure the decision metric directly (as Phase C does) rather than infer it from RMSE.
