# M3-3 DvP methodology

Specification §1, §5–§7, §11.3. This document fixes the hypotheses, estimators, protections against look-ahead, and the metrics, before Phase B runs. Formulas name the code that computes them.

## Hypotheses

| | Question | Phase | Status |
| --- | --- | --- | --- |
| RQ1 | Does a defense (for D/ST, an offense) have a repeatable, position-specific tendency to allow FFA points beyond what its opponents usually score? | A | Answered descriptively ([reliability report](RELIABILITY_REPORT.md)) |
| RQ2 | Does adding that tendency to an offense-only forecast improve next-game forecasts of actual FFA position totals? | B | Development and 2024 validation done ([backtest report](BACKTEST_REPORT.md)): yes for D/ST, no credible gain elsewhere; 2025 holdout pending |
| RQ3 | If so, does it improve actual Sit/Start choices between players? | C | Only if RQ2 is credibly positive |

Zero production influence is an acceptable answer to every question.

## Data

- **Scoring truth:** Arbit's FFA actuals, built from completed regular-season games 2016–2025.
  - Targets index `6ffb62fb…` (R-072 repaired), scored under the league's rules: athlete `10e938eb…`, D/ST `16885a80…`.
  - They enter only through the lineage allowlist ([provenance](SOURCE_PROVENANCE.md)).
- **One cell** is a team-game and a position group: the summed FFA points of the offense's players at QB, RB, WR, TE or K, or the points the opposing D/ST scored. Refused, duplicate and uncovered cells are missing, never zero ([data quality](DATA_QUALITY.md)).
- **The unit whose tendency is measured** is the defense for QB to K, and the offense for D/ST. `faced` is the other side.

## Phase A estimators (`arbit_model.dvp.lab`, `reliability`)

**The model** (§6): a unit-season's cells are y = μ + a + e, with a the unit-season tendency (variance τ²) and e game noise (variance σ²).
- k = σ² / τ² is the games at which a unit's own record and the league average weigh equally.
- One game's reliability is 1 / (1 + k).
- After n games the record earns w(n) = n / (n + k).

**Adjustments** (`adjust`). y minus an expectation for what was faced:
- `none`: no expectation (v0 raw).
- `season`: the season's mean at the position.
- `loo_mean`: the faced side's mean in its *other* games that season (v0 adjusted).
- `loo_median`: the faced side's median in its other games.
- `loo_shrunk`: the faced side's other-game mean, shrunk toward the season mean with the faced side's own k.

All are retrospective: they use later games, so Phase A never forecasts.

**Split-half** (`split`, `assignment`, `random_splits`):
- Each unit-season's cells are divided in two by one of:
  - NFL week parity (v0);
  - alternating games;
  - first vs second half;
  - first 6 vs next 6;
  - home vs away;
  - a seeded balanced random split (1,000 seeds; their spread is the split's arbitrariness, not sampling error).
- Units need at least 4 cells per half.
- r is the Pearson correlation of the two halves' means across unit-seasons, and k = m(1 − r)/r with m the mean half size (v0's shortcut).
- r ≤ 0 identifies no k.

**Variance components** (`anova_components`, `reml_components`), one-way by unit-season, each unit with its own game count:
- **Method of moments:** τ² = (MSB − MSW) / n₀ with n₀ = (N − Σnᵢ²/N) / (g − 1), truncated at 0.
- **REML:** μ and σ² are profiled out. The restricted likelihood is maximized over λ = τ²/σ² ≥ 0, by a log-scale grid from 10⁻⁶ to 10³ and then golden-section search.
  - A maximum at λ = 0 is reported as a boundary estimate with no k.
  - A maximum at the grid's top edge is reported as not converged (T14).
- **Model check:** the expected split correlation with unequal halves is mean over units of √(m_a/(m_a+k) · m_b/(m_b+k)) (`implied_split_r`, T12).
- **Season-wide variance:** the variance of season means less their sampling noise (`season_component`).

**Time** (`lag_profile`, `rolling_window`):
- **Lag profile:** the mean product of two season-centered cells of the same unit-season, by weeks apart (1–2, 3–4, …, 13–17), over the total variance. That is single-game reliability at that distance; a stable trait is flat.
- **Rolling window:** the correlation of a unit's previous w-game mean with its next game. Under a stable trait it is λ / √((λ + 1/w)(λ + 1)) (`implied_window_r`).

**Between seasons** (`carryover`): the same franchise's mean in seasons s and s + 1, both with 8 or more games. Reports r, the OLS slope, and the leave-one-season-out squared error of slope × last season against a reset to the league.

**Nulls** (`permutation_null`): within each season and week, the unit labels of that week's cells are shuffled (1,000 times). Every unit keeps its schedule and every week its values; only the link between a unit and its own results breaks.
- **p-value:** (1 + #null ≥ observed) / (1 + reps).
- **Multiple comparisons:** Holm's adjustment across the 12 tests (6 groups × raw and adjusted). Phase A is exploratory.

**Resampling** (`cluster_bootstrap`, `bootstrap_components`, `joint_orderings`):
- Percentile intervals from 2,000 resamples (seed 1729).
- **Reported:** resampling whole seasons, because one game links two units and a season's units share conditions. Unit and franchise resampling are reported for comparison.
- **Position orderings:** the same resampled seasons for every group at once.

**Components** (A09): each cell's points are split by the scorer's own rule contributions (yards, receptions, touchdowns, turnovers, kicking, D/ST tiers). These are admitted as `ffa_targets.*_contributions` and sum back to the cell exactly.

**Corrections** (A12): 2026 FFA points by position as first held, compared with the latest version, through the point-in-time gamebooks. These are admitted as `gamebook.*` (`FFA_ACTUAL_AS_OF`).

## Protection against look-ahead

| Protection | Where |
| --- | --- |
| A game's actuals count from 12:00 UTC the day after its game day (retrospective; final revisions only) | `observations.available_at`, `asof.features_as_of` |
| Features are filtered to `available_at ≤ cutoff`; a later row raises `FEATURE_AFTER_CUTOFF` | `asof` (T15, T34, T35) |
| Forecasts are frozen without labels; labels join only through `evaluation_join` on unique keys after freezing | `asof.FrozenForecasts`, `evaluation_join` (T20, T36) |
| A prior may come only from FFA actuals | `asof.league_prior` (T38) |
| Phase A's leave-one-out adjustments use later games and are labeled retrospective; Phase B never uses them | this document, B-phase code |
| 2025 was seen descriptively by v0 and Phase A, so it is at best `CONDITIONALLY_HELD_OUT`. No parameter is estimated on it before a frozen manifest | §12, `config/dvp/base.json` |

## Phase B, declared before it runs

**Folds:**
- **Development:** rolling origin by season. Fit on seasons ≤ s − 1, forecast every week of s, for s = 2017–2023.
- **Validation:** fit on 2016–2023, forecast 2024.
- **Holdout:** 2025 only from a frozen manifest trained through 2024, labeled conditional.

**Cutoff:** before the first game of each NFL week (`pre_first_game_of_nfl_week`). The per-game refresh is a separate experiment (B10).

**B00, the comparator (no defense information).** For the side that scores (the offense at QB to K; the D/ST for D/ST), position p, target week t of season s:
- **Prior:** last season's own mean at p, regressed toward the league mean by a slope fit on training seasons only. If there is no last season, the league mean.
- **In-season update:** Ô = (n·ȳ + k_own·prior) / (n + k_own), where ȳ is the side's mean over its n completed games of season s before the cutoff, and k_own is its own reliability constant estimated on training seasons only.
- **Week 1:** the prior alone.

Every quantity comes from completed-game FFA actuals known before the cutoff. B00 is never a provider projection.

**DvP variants** add w(n_d)·R̂_d to Ô:
- R̂_d is the opposing unit's mean residual against point-in-time offense baselines, over its completed games before the cutoff.
- w(n) = n / (n + k), with k estimated on training seasons only.

The variants (B01–B08 in the registry) differ in how R̂ and k are formed: raw, adjusted, shrunk, prediction-tuned k on a declared grid, recency-weighted, hierarchical, and by component.

**Metrics** (§7):
- **Primary:** RMSE per position on the common eligible rows: games where every variant and B00 have a forecast. Coverage is reported separately.
- **Paired comparison:** ΔRMSE against B00 on matching rows, with a season-block bootstrap interval (2,000, seed 1729).
- **Secondary:** MAE, mean signed error, calibration by forecast decile, Spearman rank correlation, and ΔRMSE by season, by early or late weeks and by sample-size bin.
- **Practical minimum:** 1% of B00's RMSE per position. It was fixed in `config/dvp/backtest.json` before any forecast ran, the conservative reading of §7: a smaller group-level gain would not change a Sit/Start choice.
- **Candidates:** chosen on development folds only, then frozen in `config/dvp/frozen-candidates.json` before validation ran. The holdout (2025) may evaluate only those.

**Decision labels** per position and overall (§7): `PROMISING`, `INCONCLUSIVE`, `NOT_USEFUL`, `BLOCKED`. An inconclusive result is never turned into a weight. No production weight changes without the owner.

**Controls:** shuffled defenses, pure-noise defenses and shifted labels must not improve on B00 (B09, T22, T24). Every forecast's ancestry must show `forbidden_vendor_projection_dependencies = 0` (T40).

## Phase C, declared before it ran

The full declaration is `config/dvp/sitstart.json`, committed as `317361f` before any Phase C quantity was computed.

**Gate:** Phase C starts only for a group with a credible group-level signal (§5). That is D/ST alone.

**Unit:** a D/ST is one unit per team, so its group-level forecast is its player-level forecast. Allocation (C01, C02) is the identity.

**C00:** B00. Arbit has no other player projection, and no provider projection is used.

**Decisions:**
- Every unordered pair of D/STs that both play in a week.
- Each model starts the higher forecast.
- A pair the units tied on actual points is excluded; a forecast tie earns 0.5.

**Metrics:**
- **Primary:** B06's pairwise accuracy minus B00's.
- **Secondary:** changed choices; actual points gained per changed choice; worst single choice and worst week; within-week Spearman; league top 8; close pairs; and a waiver-pool proxy (an assumption).

**Uncertainty:** week-block bootstrap, 2,000 replicates, seed 1729.

**Practical minimum: 1.8 points of accuracy.** Under a bivariate normal, pairwise accuracy is 0.5 + asin(ρ)/π. Phase B's 1% RMSE cut moves B00's development correlation from 0.1448 to 0.2011, so accuracy rises from 54.6% to 56.4%.

**Rule:**
- **PROMISING:** at least 1.8 points, with net points gained, in development, 2024 and 2025.
- **NOT_USEFUL:** below 1.8 in all three.
- **INCONCLUSIVE:** anything else.
- **BLOCKED:** an integrity check fails.

The same rule applies to the prospective 2026 window (`config/dvp/frozen-phase-c.json`).

## After the holdout: exploratory v2 and the prospective harness (owner audit, 2026-11-24)

These came after the 2025 holdout was inspected. They are versioned, never change the frozen candidates, and are labeled by what they can show.

- **Prospective 2026** (AUD-01, [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)):
  - the frozen estimator, through the adapter `arbit_model.dvp.shadow`, forecasts each window week from the schedule before its kickoff;
  - the forecasts are archived write-once with a hash-chained ledger and evaluated after the games;
  - only the complete predeclared window can confirm.
- **Decoupled stages** (AUD-05, [EXPLORATORY_V2.md](EXPLORATORY_V2.md)):
  - the target universe comes from the schedule, not from cells whose labels turned out valid;
  - forecasts are persisted before labels are read;
  - labels are joined without dropping a target, and invalid labels are reported, not removed.
- **Row contract** (AUD-04, [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md#enforcement-at-use-owner-audit-aud-04-task-20261124-007)): every observation row's lineage is checked where it is fit or forecast, and store objects are hashed before reading.
- **Exploratory estimators** (AUD-03), declared in `config/dvp/explore-v2.json` before results:
  - rolling 3/5/8-game residual windows, shrunk by n_m/(n_m + k_REML);
  - B03 with v0's split-half k fit on training seasons only.
  Compared with B03, B04, B05 and B06 on common rows with the frozen bootstrap. Descriptive only.

