# M3-3 DvP opportunity volume and scoring efficiency (A09 and B07 extended)

Owner audit AUD-02 (remediation 2). TASK-20261124-008. Receipt: [explore-v3.json](explore-v3.json), run `run-20261124-ef59e6f` at code `ef59e6f`. Declared first in [`config/dvp/explore-v3.json`](../../../config/dvp/explore-v3.json).

**Classification: EXPLORATORY.** This work comes after the 2025 holdout was inspected. It changes no frozen candidate and doesn't affect the 2026 confirmation.

**The question.** Two defenses can both allow 30 WR points a game:
- one on 25 targets (1.2 points per target);
- the other on 15 targets (2.0 points per target).

Total points allowed can't tell them apart. Here each cell is split into **volume** and **efficiency** (FFA points per unit of volume), and each part's repeatability and forecasting value is measured separately.

## Data: present, admitted, reconciled

The earlier "not yet admitted" note was not a data gap. Arbit already uses these counts (`gamebook.OPPORTUNITY_COLUMNS`, `team_features` `opps_pg`, `feature_specs` `opp_dvp_<pos>_opps_pg`). nflverse's weekly player and team statistics hold every count needed for 2016–2025, with no null values.

- **Sources:** the exact files each season's FFA targets were built from (`stats_player_week_<season>` and `stats_team_week_<season>` manifests pinned in index `6ffb62fb…`). Every object's bytes were re-hashed before reading.
- **Admission** (`arbit_model.dvp.opportunity.admit_realized`) applies the firewall's rules and field catalog on a versioned allowlist, because `provenance.py` is frozen:
  - the generic `fantasy_points` and `fantasy_points_ppr` columns were dropped and recorded;
  - an unknown column such as `opponent_expected` stops the run (`test_dvp_opportunity.py`).

**Volume per cell:**

| Group | Volume | Also kept |
| --- | --- | --- |
| QB | dropbacks (pass attempts + sacks) + carries | attempts, sacks, carries |
| RB | carries + targets (FB and HB count as RB) | receptions |
| WR, TE | targets | receptions |
| K | field-goal + extra-point attempts | |
| D/ST | the offense's plays (pass attempts + sacks + carries) | dropbacks, sacks, turnovers |

**Reconciliation.** Player attempts, sacks and carries summed per team-game equal the team statistics in **all 5,278 team-games** (0 differ). Every team-game has both sources.

**Coverage** of valid FFA cells, out of 5,278 cells per group:

| Group | Volume present | Zero volume | No statistics row | Efficiency defined |
| --- | --- | --- | --- | --- |
| D/ST | 5,278 | 0 | 0 | 5,278 |
| QB | 5,269 | 0 | 9 | 5,269 |
| RB | 5,265 | 0 | 0 | 5,265 |
| WR | 5,261 | 0 | 0 | 5,261 |
| TE | 5,227 | 18 | 19 | 5,227 |
| K | 5,191 | 58 | 15 | 5,191 |

- **Missing rows:** all 43 cells without a statistics row have 0 FFA points. Their players played without recording a statistic. The cells are kept as `missing` and never imputed.
- **Zero volume:** these cells keep volume 0 and carry no efficiency (no division by zero), and none of them has points.
- **True zeros with volume** (0 points on positive volume) stay in: 266 D/ST, 89 K, 72 TE and 1 WR cells.

## Reliability: which part repeats (A09 extended)

REML k, in games for half weight (lower is more repeatable). Each measure is leave-one-out adjusted for the side faced, with a 95% season-cluster bootstrap (1,000 replicates, seed 1729):

| Group | Points allowed | **Volume allowed** | **Efficiency allowed** | Unit-season correlation: volume ~ efficiency |
| --- | --- | --- | --- | --- |
| D/ST | 7.2 (6.0–8.6) | 18.9 (14.5–27.7) | **7.2 (6.2–8.5)** | −0.41 |
| QB | 24.2 (16.1–41.3) | 28.8 (20.5–53.6) | 27.2 (17.8–45.3) | −0.13 |
| RB | 19.5 (15.9–26.4) | **17.1 (13.1–25.2)** | 32.3 (18.8–84.2) | +0.16 |
| WR | 26.7 (17.5–58.3) | **23.9 (17.0–38.8)** | 42.3 (25.2–114.1) | −0.12 |
| TE | 37.4 (23.3–96.4) | 47.9 (31.7–89.3) | 170 (80–1,611) | +0.08 |
| K | 50.5 (33.3–98.5) | **21.3 (14.1–36.0)** | 438 (104–3,869) | −0.02 |

**What repeats:**
- **RB and WR:** the volume a defense allows (carries and targets) repeats a little faster than its points allowed. Efficiency (points per opportunity) repeats much more slowly, so the opponent signal at these positions is mostly volume.
- **K:** volume allowed (attempts) is far more repeatable than points (k 21 against 51). Kicking efficiency allowed is noise (k about 440): a defense doesn't change an opposing kicker's accuracy.
- **D/ST is the reverse.** Efficiency (D/ST points per offensive play: sacks, turnovers, points and yards allowed) carries the whole signal, with the same k as points (7.2). The number of plays an offense runs repeats weakly. It correlates negatively with D/ST points per play (−0.41): offenses that run more plays tend to be better offenses.
- **QB and TE:** neither part is clearly more repeatable than the total.
- **Duplication:** volume and efficiency tendencies are nearly uncorrelated except for D/ST, so they carry separate information. Points allowed is mostly efficiency for D/ST (0.99) and QB (0.88), and a mix elsewhere.

## Forecasting (B07 extended)

The new estimators run inside the same decoupled walk as every frozen variant: same rows, cutoffs and B00 (`explore.make_opportunity_extra`). For the opposing unit's completed games before the cutoff, each is measured against what the scoring side usually produces (its other games this season, shrunk to last season's league level):
- **`b07v`, volume channel:** the volume residual × the side's expected efficiency.
- **`b07e`, efficiency channel:** the volume-weighted efficiency residual × the side's expected volume. Efficiency is a ratio of sums, with a league pseudo-volume prior, so small denominators can't blow up.
- **`b07ve`:** both channels.

Each channel is shrunk by n/(n + k) with its own training-only REML k. The existing non-touchdown **`b07`** is kept as its own variant.

**Change in RMSE against B00** (negative is better; the practical minimum is 1%):

| Group | Stage | B03 | B06 (frozen D/ST) | B07 non-TD | **b07v** volume | **b07e** efficiency | **b07ve** both |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D/ST | Development | −2.65% | **−2.99%** | −2.80% | +0.10% | −2.60% | −2.62% |
| D/ST | 2024 | −5.35% | **−6.36%** | −5.09% | −0.15% | −5.10% | −5.27% |
| D/ST | 2025 | −3.38% | **−4.06%** | −3.50% | +0.19% | −3.50% | −3.48% |
| QB | Development | −0.59% | −0.85% | −0.47% | −0.06% | −0.39% | −0.47% |
| QB | 2025 | −1.05% | −1.14% | −0.64% | −0.38% | −0.53% | −0.96% |
| RB | Development | −0.65% | −0.84% | −0.52% | −0.48% | −0.18% | −0.58% |
| RB | 2024 | −0.46% | −0.84% | −0.27% | −0.55% | −0.14% | −0.60% |
| RB | 2025 | −0.36% | −0.54% | −0.12% | −0.01% | −0.31% | −0.34% |
| WR | Development | −0.51% | −0.74% | −0.50% | −0.28% | −0.12% | −0.44% |
| WR | 2024 | +0.73% | +1.21% | +0.38% | +0.33% | +0.20% | +0.46% |
| WR | 2025 | −0.90% | −0.58% | −0.60% | +0.01% | −0.42% | −0.54% |
| TE | 2025 | −0.62% | −0.81% | −0.35% | −0.22% | −0.09% | −0.29% |
| K | Development | −0.05% | **−0.12%** | −0.05% | −0.11% | +0.00% | −0.11% |
| K | 2024 | −0.06% | −0.04% | −0.05% | **−0.21%** | +0.01% | −0.20% |
| K | 2025 | −0.26% | −0.30% | −0.26% | **−0.53%** (−0.04 to −0.01 points) | −0.01% | −0.53% |

The receipt has every stage and position, intervals, MAE, and the comparison with B04 and B05.

**Findings:**
- **D/ST: the efficiency channel is the DvP signal, and volume adds nothing.**
  - `b07e` matches B03 (term correlation 0.99) and falls short of B06's last-season prior.
  - `b07v` is no better than B00.
  - The frozen B06 stays best.
- **K: the volume channel beats B03 in all three periods, and B06 in 2024 and 2025.** In development it ties B06 (−0.11% against −0.12%). That is consistent with its reliability (volume k 21 against points k 51).
  - The gain is tiny: −0.11%, −0.21% and −0.53%.
  - It is far below the 1% practical minimum. Kicker scoring is mostly the kicker's own volume and luck.
- **RB:** the combined channel (`b07ve`) is close to B03 and below B06 in every period. Volume alone does better than B06 nowhere.
- **WR, TE and QB:** no channel beats B03 or B06. WR 2024 is worse with every opponent term, as before.
- **Duplication:**
  - Outside D/ST, the volume and efficiency terms mostly correlate 0.4 to 0.9 with B03's term, so they largely re-express the same opponent information. The exceptions are QB's volume term (0.28 to 0.36) and K's efficiency term (0.14 to 0.67).
  - Combining them recovers about what B03 already has.
- **Unstable denominators** are handled by ratio-of-sums efficiency, the league pseudo-volume prior and game-count shrinkage. No efficiency estimate is ever made at zero volume.

## Comparison with the original M3-3 results

| Original conclusion | After opportunity and efficiency |
| --- | --- |
| D/ST is the one group where DvP helps | Confirmed. Its signal is per-play efficiency (sacks, turnovers, scoring held down), not the volume of plays |
| RB and WR DvP is under 1% | Unchanged. Their repeatable part is volume allowed, which forecasts about as well as the total |
| K DvP is noise | Refined: kicking volume allowed repeats (k 21), and as a forecast it matches or beats the other opponent terms (best in 2024 and 2025). It is still far under the 1% minimum, so K stays NOT_USEFUL for production |
| A09: touchdowns allowed are noise | Consistent: efficiency allowed (which carries touchdowns) is the slow-repeating part for WR, TE and RB |

**Possible future test (not a candidate now):**
- a K volume-channel term;
- an RB combined term.

Each would need its own predeclared rule and a separately frozen evaluation on future games. Neither changes the 2026 confirmation.
