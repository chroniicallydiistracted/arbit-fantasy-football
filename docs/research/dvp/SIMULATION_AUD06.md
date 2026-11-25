# M3-3 DvP: does the method find a signal that is really there, and only then? (AUD-06)

Owner final directive §9 (DEC-08), TASK-20261125-001.
- **Declared first:** [`config/dvp/simulation-v1.json`](../../../config/dvp/simulation-v1.json), pushed in `88876b8` before anything ran.
- **Ran from:** `cc25e2c`. **Summarized at:** `901da3d`.
- **Receipt:** [simulation-v1.json](simulation-v1.json). **Plots:** [plots/simulation](plots/simulation).
- **Raw results:** one line per repetition in `artifacts/dvp/simulation-v1/` (local).

**Short answer:**
- **No false promotions.** When there is no defensive signal, Arbit's complete procedure never promoted one: 0 of 300 repetitions per position, and 0 of 300 across six positions at once.
- **Strong signals are found.** When the signal is as strong as real D/ST's (k = 8), it promoted D/ST in 86% of repetitions and WR in 80%.
- **Moderate signals sit below the bar.** When it is moderate (k = 20), the procedure almost never promotes (2%) and mostly says INCONCLUSIVE. Its development gain (0.7–0.8%) sits just under the 1% minimum, which is what real QB, RB and WR show.
- **The intervals run narrow.** The estimators work; the uncertainty intervals are somewhat narrow, most of all the league bootstrap with only 11 week blocks.
- **No earlier conclusion changes.** Several gain qualifications.

## How it works

**The leagues** (`arbit_model.dvp.simulate`):
- **Shape:** synthetic leagues in the real data's own schema. Each has 32 teams, 17 weeks and ten seasons (2016–2025) split as the real study is: development 2017–2023, validation 2024, holdout 2025.
- **Points:** mean + the scoring side's strength + the studied unit's **known defensive trait** + noise.
  - **The trait's size** is set by its true k (noise variance ÷ trait variance per game): no trait, k = 60 (weak, like real WR and K), 20 (moderate, like RB) or 8 (strong, like D/ST's 9).
  - **Persistence:** traits and strengths persist across seasons with correlation 0.5.
  - **Touchdowns:** they carry 40% of the noise and none of the trait.
  - **Volume and efficiency** multiply to points.
- **The oracle** forecast knows the true mean. It is a reference only.

**What runs is Arbit's own code, unmodified:**
- the walk-forward estimators B00–B07 and the B09 controls;
- the exploratory rolling windows, split-half k and volume/efficiency channels;
- REML, the split-half and the season-cluster bootstrap;
- the frozen development selection (loaded from git at the frozen commit) and `walkforward.decide` at 1%;
- Phase C's `decisions` at 1.8 points;
- the league `decide` and `summarize`.

Random streams are separate for data, the walk, permutations and bootstraps.

| Experiment | What | Repetitions |
| --- | --- | --- |
| E1 | Estimator recovery: REML, split-half, interval coverage; the opportunity channels | 1,000 per scenario (intervals on 200) |
| E2 | The complete procedure, development to Phase C | 300 per scenario (the pilot fit the budget: about 1 hour on 8 workers) |
| E3 | Small-sample league decisions: 8 teams, 11 weeks | 2,000 per case; truth from 20,000 more on its own stream |
| U | Coverage of `walkforward.metrics`' block bootstrap against a known RMSE difference | 1,000 per condition, 1,000 replicates each (declared deviation from 2,000) |

All 33,100 repetitions ran, and none failed.

## Results

### Acceptance (declared before running)

| Criterion | Result |
| --- | --- |
| A1: null, PROMISING ≤ 5% per position; Phase B and C ≤ 5% | **PASS:** 0 of 300 (Monte Carlo upper bound 1.3%) |
| A2: six null positions, any PROMISING ≤ 10% | **PASS:** 0 of 300 |
| A3: strong signal, PROMISING ≥ 80% | **D/ST PASS** (86%, 81.6–89.5%). **WR INCONCLUSIVE:** 80.3% with an interval of 75.5–84.4% straddling 80% |
| A4: k recovery at k = 8 and 20 within 25% (median), convergence ≥ 95% | **PASS:** 15–19% error, 100% converged |
| A5: shrunk variant chosen among candidates ≥ 90% | **PASS:** 100% |
| A6: each B09 control cuts RMSE 1% in ≤ 5% | **PASS:** 0% under the null and under a strong signal |
| A7: bootstrap coverage 92–98% where blocks match the dependence (≥ 10 blocks) | **PASS:** 92.0–93.2% |
| A8: league, null false positives ≤ 7%; coverage 90–98% | **FAIL**, below |

**A8 in detail:**
- **Coverage of the true gain** is 77–87%, against 90–98% required.
- **The declared two-sided false-positive check fails in 3 of 4 null cases** (9–13% exclude zero).
- **A configuration issue explains part of that.** The declared null makes B06 add noise rather than nothing, so its true gain is slightly negative: −2.7 points for start, −13.1 for streaming (SIM-17). An interval below zero is then a correct detection.
- **A supplementary one-sided check,** labelled as such and not replacing the declared one, shows B06 falsely appearing better in only 2.4–4.7%.
- **The coverage shortfall is genuine,** and is explained under uncertainty below.

### E1: estimators against the truth

| Scenario (true k) | REML k, median (IQR) | Median error | Split-half k, median | Interval coverage of k (nominal 95%) |
| --- | --- | --- | --- | --- |
| Strong (8) | 9.1 (8.1–10.2) | 15% | 8.9–9.0 | 70–75% |
| Moderate (20) | 22.6–23.1 | 18–19% | 22.4–23.0 | 77–82% |
| Weak (60) | 74–77 | 34–36% | 71–72 | 87–89% |
| No signal (∞) | none in 63%; otherwise a median of about 300 | — | about 200 | — |
| Unequal exposure (20) | 24.0 | 22–23% | 24.1–24.8 | 78–81% |
| Random missing (20) | 23.6–23.7 | 22% | 23.9–24.1 | 78–81% |
| Informative missing (20) | 19.4–19.6 | 16–17% | 19.4–19.7 | 84–88% |
| Correlated errors (20) | 32.9–33.3 | 65–66% | 30.2–31.5 | 33–34% |
| Heavy tails (20) | 22.1–22.4 | 18–19% | 21.7–22.2 | 75–77% |

- **REML always converges.** It estimates k about 15% too high (log bias +0.13 at k = 8, +0.14–0.17 at k = 20, +0.33–0.35 at k = 60).
- **Why it runs high:** adjusting for the side faced adds estimation noise to the residual variance (σ̂² ≈ 111 against a true 100 for WR) and slightly attenuates the trait. The forecasts face the same adjusted residuals, so the estimate is the operative k for them. The bias is conservative: a little more shrinkage than the trait alone warrants. **MATHEMATICAL_LIMITATION.**
- **Split-half k matches REML** at every signal level, as in the real data (explore-v2).
- **Season-cluster intervals for k are too narrow** (70–89% against 95%): 7 season blocks, and the interval is centred on a biased estimate. **INSUFFICIENT_SAMPLE / MATHEMATICAL_LIMITATION.** The frozen method uses REML's point k, not this interval.
- **Correlated errors** (a shock shared by both sides of a game, plus a league-wide week shock) look like noise: k is overestimated 65% and its interval covers 33%. **MODEL_ASSUMPTION** (independent errors).
- **Volume and efficiency (SIM-14):** `opportunity.reliability` finds the channel every time.
  - Signal in volume: volume k 5.2 (WR) and 0.6 (D/ST), efficiency unidentified in 56–61%.
  - Signal in efficiency: efficiency k 5.5 and 11.1, volume unidentified in 60–65%.

### E2: the complete procedure

**Phase B labels:**

| Scenario | D/ST PROMISING | WR PROMISING | Mostly | Development gain of the best variant | Phase B and C both PROMISING (D/ST) |
| --- | --- | --- | --- | --- | --- |
| SIM-01 no signal | 0% | 0% | NOT_USEFUL 100% | −0.01% | 0% |
| SIM-16 no signal, six positions | 0% each | 0% each | NOT_USEFUL 100%; any position 0% | −0.01% | 0% |
| SIM-02 weak (k 60) | 0% | 0% | NOT_USEFUL 99% | −0.13% to −0.15% | 0% |
| SIM-03 moderate (k 20) | 1.7% | 1.3% | INCONCLUSIVE 61–66% | −0.72% to −0.78% | 1.3% |
| SIM-04 strong (k 8) | **86%** | **80%** | the rest INCONCLUSIVE | −2.6% to −2.9% | **77%** |
| SIM-05 abrupt change at week 9 | 12% | 7% | INCONCLUSIVE 67–69% | −0.9% to −1.0% | 7% |
| SIM-06 gradual drift | 3% | 4% | INCONCLUSIVE 59–64% | −0.8% to −0.9% | 2% |
| SIM-07 unequal exposure (k 20) | 1.7% | 1.0% | NOT_USEFUL 46–60% | −0.65% to −0.73% | 1% |
| SIM-08 random missing (k 20) | 0.3% | 0.7% | ~50/50 | −0.66% to −0.70% | 0.3% |
| SIM-09 informative missing (k 20) | 8.7% | 4.7% | INCONCLUSIVE 73–76% | −0.84% to −0.97% | 3% |
| SIM-10 correlated errors (k 20) | 0.3% | 0% | NOT_USEFUL 70–76% | −0.50% to −0.54% | 0.3% |
| SIM-11 heavy tails (k 20) | 3.7% | 3.0% | INCONCLUSIVE 56–63% | −0.78% to −0.81% | 1.3% |
| SIM-12 unequal schedule (k 20) | 1.7% | 3.0% | INCONCLUSIVE 57–62% | −0.78% to −0.82% | 0.7% |
| SIM-13a full turnover (k 8) | 87% | 85% | — | −2.7% to −2.9% | 79% |
| SIM-13b high persistence (k 8) | 90% | 85% | — | −3.1% to −3.2% | 85% |
| SIM-14a signal in volume (k 8) | 78% | 79% | — | −2.4% to −2.5% | 73% |
| SIM-14b signal in efficiency (k 8) | 84% | 70% | — | −2.4% to −2.8% | 74% |

**What the procedure does:**
- **False promotion: none.** No repetition without a signal produced a candidate, in any position. The 1% practical minimum, rather than any interval, does this work: the best null variant improves RMSE by 0.01% on average, so selection noise never approaches 1%. The winner's curse (development gain minus validation gain of the chosen variant) is at most 0.2 percentage points in every scenario. That is negligible, because selection among about 20 variants on seven seasons of thousands of rows is stable.
- **Detection power** depends on the trait's strength, and the bar is high:
  - strong (k = 8): 80–90%;
  - moderate (k = 20): about 2%, though the oracle, knowing the trait, gains about 2.2–2.3% more than it gains without one;
  - weak (k = 60): 0%.
  The shrunk estimators capture roughly half of the trait's value at k = 8 (−2.9% against the oracle's −5.4% attributable to the trait, net of what it gains by knowing side strength). They capture much less at k = 20 (−0.8% against about −2.2% to −2.3%). In-season sample sizes are the limit, not a defect. **INSUFFICIENT_SAMPLE.**
- **Choosing the estimator:** every candidate was a shrunk variant. Which one tracks the data-generating process:
  - B07 when the trait lives only in non-touchdown points (the generator's design);
  - B06 when traits persist across seasons (SIM-13b: 95% B06);
  - recency (B05) after an abrupt change (60%).
  Raw DvP (B01) is never chosen. It is 9–10% worse than B00 without a signal, and 3.6–4.5% worse even with a strong one.
- **Assumption violations:**
  - non-stationary traits (abrupt change, drift) are mostly missed (3–12%);
  - correlated errors suppress detection (0–0.3%);
  - informative missingness raises detection slightly (5–9%, with a real signal present);
  - heavy tails and an unequal schedule change little.
  None produced a false promotion.
- **Phase C:**
  - pairwise accuracy changes −0.06 points without a signal (NOT_USEFUL every time);
  - +4.2 to +4.4 points with a strong one, close to the real D/ST's +4.4 to +8.5;
  - +1.2 to +1.3 points with a moderate one, below 1.8.
- **Controls (SIM-15):** the B09 placebos never helped: about 0% without a signal, 1.4–4.2% worse with one.
- **Exploratory estimators:**
  - rolling 3/5/8-game windows lose to full-season shrinkage when traits are stable, and match recency weighting after an abrupt change;
  - split-half-k shrinkage equals REML's;
  - the volume channel wins when the trait is in volume (D/ST −4.1% against B07's −2.5%);
  - the efficiency channel wins when it is in efficiency (WR −2.7%).

### Uncertainty (C7)

| Bootstrap | Condition | Coverage (nominal 95%) |
| --- | --- | --- |
| `walkforward.metrics`, week blocks | independent rows; week shocks; shared-game pairs; unequal exposure (17 blocks) | 92.0–93.2% |
| same | temporal AR(1) shocks across weeks | 91.0% |
| same, row-level blocks under week shocks | (a deliberate mismatch) | 95.8%: common week shocks cancel in the RMSE difference |
| season blocks | 7 / 5 / 3 seasons | 90.4% / 86.5% / 73.4% |
| `league.summarize`, every week a block (corrected) | 11 weeks, start / stream | 77–87% |
| `league.summarize`, changed weeks only (v1) | same | 64–84% |
| naive decision-level bootstrap | same | 80–90% start, **44–49% stream** |

**Implications:**
- **Phase B:**
  - **Validation and holdout intervals** (17 week blocks) are close to nominal.
  - **Development intervals** (7 season blocks) cover about 90%: somewhat narrow, a MATHEMATICAL_LIMITATION of few blocks.
  - **Labels** use point estimates against the 1%, not intervals, so no label is affected.
- **League evaluation:**
  - **The correction was right:** v1's changed-weeks bootstrap is the worst of the block methods, and the all-weeks correction improves it.
  - **It is still too narrow:** 77–87% with 11 blocks. A naive decision-level bootstrap would be badly wrong for streaming, because one recommendation is shared by many managers (PB-AUD-05).
  - **The reported C05L intervals are too narrow:** −96 to +74 for start/sit, −202 to +398 for streaming. The finding that they are inconclusive becomes firmer, not weaker. **MATHEMATICAL_LIMITATION / INSUFFICIENT_SAMPLE.**

## Does AUD-06 change an earlier conclusion?

No. It supports or qualifies each one:

| Earlier conclusion | What the simulation says |
| --- | --- |
| D/ST B06 PROMISING (historical) | Supported. The procedure never promoted a null signal in 900 position-repetitions (SIM-01, SIM-16), and promotes a D/ST-strength signal 86% of the time. Real D/ST's development gain (−2.99%) and Phase C gain (+4.4) match a strong, stable trait |
| QB, RB and WR not useful or inconclusive | Qualified. Their real development gains (−0.74% to −0.85%) are what a moderate true trait (k ≈ 20) produces, and the procedure almost never promotes that. "Not useful at the practical minimum" is not "no signal" (consistent with AUD-07) |
| TE and K not useful | Consistent with a weak or absent trait (k ≥ 60 gives about −0.1%) |
| The k values used for shrinkage | Slightly conservative (about 15% high); harmless |
| C05L-2026 league results inconclusive | Strengthened: their intervals are too narrow, so the true uncertainty is larger |
| Raw DvP harmful; shrinkage essential | Confirmed |

**No material methodological defect was found.** No software defect, no false promotion, and no change to the frozen 2026 methodology. The frozen experiment continues unchanged (§5.4).

**Limitations to carry forward:**
- k intervals and league intervals undercover.
- Non-stationary and error-correlated signals are mostly missed (a sensitivity limit, not a false-positive risk).
- The generator puts the whole trait in non-touchdown points, which favours B07. Real data chose B06, consistent with cross-season persistence (SIM-13b).

**Governance for later slices:**
- Keep practical minima on point estimates; they control false promotion far better than nominal intervals with few blocks.
- When a decision rule uses intervals, use one designed for few blocks, or report its simulated coverage.
- Treat "not useful at the practical minimum" as distinct from "no signal".

## Reproduce

```sh
POLARS_MAX_THREADS=1 ARBIT_SIM_OUT=<main>/artifacts/dvp/simulation-v1 \
  uv run python scripts/model/dvp_simulate.py run --experiment E2 --scenarios SIM-01,SIM-04 --reps 300 --workers 8
uv run python scripts/model/dvp_simulate.py truth --reps 20000
uv run python scripts/model/dvp_simulate.py summarize
```

Repetitions are resumable and deterministic, with seeds from `SeedSequence(20261125)` by experiment, scenario and repetition. Fast checks of the generator are in `libs/arbit-model/tests/test_dvp_simulate.py`; they run in CI.
