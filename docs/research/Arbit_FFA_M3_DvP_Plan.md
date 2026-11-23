# ARBIT FFA — M3-3 Defense vs. Position (DvP) Research, Build & Evaluation Specification

**Document version:** 1.1 — final revised implementation specification.  
**Workstream:** **Existing Slice M3-3, continued and expanded**; NOT a new stand-alone model slice or a request to rebuild the original study from scratch.  
**Status:** Implementation-ready research specification; not evidence that DvP is predictive.  
**Scope:** One isolated experimental factor in the Arbit FFA Family Sit/Start advisor.  
**Historical study:** NFL regular seasons 2016–2025, using Arbit's previously calculated, canonical league-specific **actual FFA fantasy points from completed games**.  
**Prior work:** The same implementing AI previously created/ran the first M3-3 evaluation and supplied the original methodology. The study's script, settings, results, reasoning, and artifacts are the starting state, not a new agent's hypothetical baseline.  
**Non-negotiable input rule:** **Never ingest or use ESPN's or any other provider's predetermined/projected fantasy points** for features, expected outcomes, baselines, targets, comparisons, training, tuning, calibration, or fallback. Independently computed Arbit forecasts *derived exclusively from eligible actual historical data* are allowed as model outputs.  
**Prime directive:** **Measure, don't assume, DvP's predictive value.** A valid outcome is zero production influence if the evidence does not support it.

## 0. Mandatory operating rules for the implementing agent

1. **Resume Slice M3-3.** Inspect existing M3-3 objectives, milestone status, experiment registry, scripts, configs, source data, reports, code commits, execution logs and original decisions. **You are the AI that implemented the first M3-3 experiment**: use that prior work as the known starting point, verify it against repository evidence, and continue from it. Do not silently label completed M3-3 work as newly planned, overwrite its findings, rename the milestone, or build a parallel competing DvP pipeline.
2. Read and follow repository-wide `AGENTS.md`, project instructions, existing architectural conventions and context-governance requirements before changes. Inspect the scoring layer, data contracts, schemas, tests, and `scripts/model/defense_position_study.py`. Do not claim those files have been reviewed until actually accessed.
3. **Authoritative scoring:** Use the existing Arbit-calculated FFA Family league scoring settings and already-determined **actual FFA fantasy points from completed NFL games/weeks**. Reuse the canonical scoring slice and its saved scored outcomes; do not substitute ESPN scoring, nflverse's generic fantasy-point fields, default PPR, half-PPR, DFS scoring, or alternate rules. nflverse final *raw stats* are valid for reconciling those FFA actuals.
4. **Absolute projection exclusion:** Never ingest, join, train on, validate against, use as a prior, blend with, calibrate to, or fall back to **ESPN pregame projected fantasy points** or **any other third-party provider's precomputed/predetermined fantasy-point projections**. This also prohibits projections concealed inside cached API payloads, imported rankings/forecast tables, or feature-engineering pipelines. Provider actual/final sports stats are a different category and may be used only under the completed-game/as-of rules. Enforce with schema, source-lineage, and executable tests—not merely policy text.
5. **Model forecasting is allowed:** B00 and all DvP variants MUST create their **own forecasts mathematically from eligible historical completed-game actuals**, known schedule/team metadata, and explicitly allowed past-realized football statistics. The word `projection` in a model-output field does not violate rule 4; *external predetermined projected fantasy points used as an input* does.
6. **Realized data must be temporally eligible:** For a prediction made at cutoff `T`, use a game's actual FFA result or realized stats as features only if that game was completed and its required outcome data were available by `T`. A game that has not begun, is underway, is suspended, or is complete only in hindsight is never an eligible pregame feature. A game's own completed outcome is a label **after the forecast is frozen**, never a same-game feature. Full-season final results are allowed for retrospective descriptive research, not look-ahead forecasting.
7. Work on an isolated branch; do not write to production, change live advisor weights, or replace canonical scoring tables. New analyses are offline, deterministic, reproducible and read-only by default.
8. Preserve the original M3-3 odd/even study as **M3-3 v0 baseline**, including raw intermediate results and provenance. Extend it through versioned experiments. If reproduction fails, document and resolve/disposition discrepancies before relying on v0 findings in subsequent tests.
9. Use nflverse as the primary NFL raw-stat/schedule foundation. Fetch supplementary free historical data only if required; record provider, license/terms, version and availability. Do not depend on paid inputs, opaque rankings, any provider's projected fantasy points, or precomputed strength-of-schedule fantasy projections.
10. Never confuse **statistical repeatability**, **next-game forecasting improvement**, **player-level Sit/Start impact**, and **within-factor shrinkage vs overall model weight**. Report these separately.
11. Prevent hindsight and test contamination: every historical forecast must use inputs and fitted parameters available at its simulated cutoff; strict holdout policies also apply. Historical final stat archives do not prove their corrected values were available at earlier cutoffs; document vintage limitations.
12. Do not fabricate results, counts, significance, completion status, source access, or successful tests. If a source/column is unavailable or cannot be shown projection-free, disable dependent experiments, record why, and run the valid remainder.
13. Record objectives, decisions, evidence, differences from M3-3 v0, tests, commands, artifacts, blockers, open questions, and next actions in durable project documentation so a fresh agent can resume without conversation context.
14. Execute as much as the repository/environment permit. Distinguish `EXISTING/REPRODUCED/PLANNED/EXECUTED/PASSED/FAILED/BLOCKED`, and do not declare success for unrun tests. Never promote to production without explicit authorization.

## 1. Research questions and separation of concerns

**RQ1 — Measure:** Do NFL defenses have a repeatable, position-specific tendency to permit above/below-expected FFA fantasy production?

**RQ2 — Explain noise:** How much observed defense-vs-position variation is attributable to defensive trait versus schedule, offensive quality, game-level randomness and transient conditions?

**RQ3 — Estimate evidence strength:** How does repeatability vary by position and observed sample size? Is the v0 split-half-to-`k` conversion consistent with stronger unequal-sample variance models?

**RQ4 — Forecast:** Does information known *before* Week `t` about a defense improve next-game forecasts of an opposing offense's FFA position-group points?

**RQ5 — Add value:** Does DvP improve on an offense-only baseline, and by how much? Is improvement consistent across years, weeks, positions, sample sizes and reasonable perturbations?

**RQ6 — Translate (conditional, downstream):** If the signal survives group-level testing, does it improve actual individual player FFA projections and pairwise Sit/Start choices beyond Arbit's existing baseline?

**RQ7 — Operationalize (conditional):** What estimator, confidence/shrinkage rule, freshness policy, eligibility rule and failure fallback are appropriate for use in the advisor?

Keep **discovery/reliability**, **chronological forecasting**, and **player-level incremental utility** as separate phases and outputs. A result of `REJECT/INCONCLUSIVE` is valid research. **M3-3 v0 is the existing starting experiment**; the new tests add evidence to this slice rather than replacing it. All historical fantasy-point outcomes must be finalized FFA actuals; all predictions must be independently generated by Arbit from permissible actual/history sources, never imported vendor projections.

## 2. Definitions and scoring contract

- `position`: Enumerate exact modeled FFA position groups from the repository configuration. Preserve original groups, including FB→RB mapping if canonical, and the special D/ST interpretation. Do not assume whether K is in scope; document whether included/excluded and why. Preserve negative fantasy totals.
- `game`: One completed, eligible regular-season NFL game with authoritative ID, season, week, actual kickoff/date, known completion/finalization state and exactly two participating teams. A schedule entry alone does not authorize use of score or stats as a pre-cutoff feature.
- `team_game`: One offense/team's participation in a game. Exactly two per completed game.
- `offense`: Team whose QB/RB/WR/TE/etc. roster production is being summed. For offensive position `p`, all **eligible** player FFA points earned for that team/game/position, regardless of how many players scored.
- `defense`: The opposing team. The offense's points by `p` are `fantasy_points_allowed` for that defense and position.
- `D/ST special case`: For matchup against offense `O`, the target is **opposing D/ST's actual FFA score against O**, not O's own D/ST score. Call this `dst_points_conceded_by_offense`; model `offense vulnerability` rather than falsely labeling it an ordinary positional-defense concession. Document known differences in FFA D/ST scoring, including sacks, turnovers, points allowed and special teams, where applicable.
- `true zero`: Complete game/team/position coverage with no eligible fantasy production. This is `0`, not NULL; a missing ingestion, unresolved player team/position, absent schedule record or incomplete scoring is `missing/invalid` until verified, not automatically zero.
- `delta`: Observed position-group FFA points minus a clearly specified baseline offense expectation. Positive `delta` = the defense allowed **more** than expected (favorable to opposing fantasy scorers); negative = fewer.
- `defense-season`: Team identity within one NFL season; no presumption that the same underlying defensive trait survives across seasons.
- `forecast cutoff`: Default is a fixed moment before the first NFL kickoff of the scoring week; **only previously completed games with sufficiently finalized FFA actuals available before that cutoff** may contribute historical feature values. A separate explicitly versioned *per-game-update* experiment may include earlier completed games from the same NFL week, but only if those games and results were available before the target game's own forecast cutoff. Never silently mix cutoff modes.
- `game count n`: Actual eligible games observed, not calendar weeks; bye weeks and canceled games contribute zero *exposure*, not zero fantasy points.

### 2.1 Hard data boundary: actual FFA outcomes versus projected points

**Allow as scoring truth:** (a) frozen FFA Family league scoring rules/configuration, (b) Arbit's canonical realized FFA player and D/ST fantasy scores from completed eligible games, and (c) underlying completed-game nflverse raw stats for auditing/recomputing those same actuals with the correct FFA rules. ESPN league *settings* are permitted solely to establish authoritative FFA roster/scoring configuration; ESPN or other providers' fantasy-*projections* are never permitted. External finalized scores are not the scoring authority when they conflict with Arbit's canonical FFA calculations.

**Allow as pregame model features when point-in-time eligible:** previously completed-game FFA actuals, realized prior-game opportunity/efficiency stats, historical schedules/results, team/player identity, and permissible priors computed solely from those realized observations. A preseason prior must come from eligible historical actuals or a neutral population estimate—not a provider's preseason fantasy forecast or rankings.

**Prohibit everywhere in this slice:** ESPN Fantasy's projected-point columns/API values; other vendor `projected_points`, `projected_fantasy_points`, pregame weekly rankings transformed into projected points, vendor rest-of-season forecasts, vendor player/D-ST position forecasts, commercial fantasy projections, and outside fantasy-point expectations even if freely available or backfilled after the fact. Do not copy public websites' fantasy points-allowed rankings without independently rebuilding them under FFA rules from actual completed games.

**Permit as experimental output, not imported input:** Arbit's own B00 offense-only forecast, B01–B12 DvP forecasts, derived `O_hat`, learned `k`, and model-estimated player points. Those values must have full derivation and source ancestry traceable exclusively to allowed data. Don't feed the model's predictions back as if they were observed actual scores; if stacking Arbit submodels later, declare it as a separate experiment with out-of-fold predictions and correct provenance.

**Mandatory row metadata:** `source_id`, `source_type` (e.g. `FFA_ACTUAL_FINAL`, `REALIZED_NFL_STAT`, `SCHEDULE`, `ARBIT_MODEL_OUTPUT`, `EXTERNAL_FANTASY_PROJECTION_FORBIDDEN`), original table/file/API field lineage, season/week/game/team/position IDs, `game_status`, `game_completed_at`, `ffa_scored_at` or best available finalization marker, `observed_or_generated`, scoring-config version/hash, and `feature_as_of`. If exact historical availability timestamps cannot be recovered, use a conservative timing rule and label this a backtest limitation; never fabricate vintage certainty.

**Enforcement:** use explicit source allowlists and typed actual-vs-forecast schemas. Unknown source type, unexplained projected-point field, ambiguous finality, mismatched scoring hash, or absent feature cutoff provenance must fail closed or be quarantined; produce a machine-readable exclusion audit. A text filter alone is insufficient: block vendor projections by *data lineage*, including renamed or nested fields.

### 2.2 Required time-eligibility examples

| Scenario | Eligible for a historical forecast? | Rule |
|---|---|---|
| FFA points from an NFL game completed the prior week, finalized before current cutoff | **Yes** | Realized FFA score, correct scoring rules, verified point-in-time availability |
| Prior completed-game nflverse stats used to validate those FFA actuals | **Yes** | Only observed stats; apply the game's completion/as-of requirement |
| Final FFA results from this week's completed Thursday game for a Sunday prediction | **Only under an explicitly selected per-game cutoff** | **Not** under a pre-Thursday/preweek locked forecast |
| Game still underway, delayed, or not finished at the cutoff | **No** | Partial or speculative result is not a finalized completed-game actual |
| Completed historical game that occurred *after* a simulated cutoff | **No as feature; yes later as label** | Historical archives do not override temporal eligibility |
| ESPN projected fantasy points published before kickoff in any past season | **Never** | Being pregame-available does **not** make an external forecast an acceptable input |
| A different vendor's projected fantasy points, renamed as `opponent_expected` | **Never** | Prohibition follows provenance, not column naming |
| Arbit B00 forecast computed only from prior FFA actuals | **Yes as model output/comparator** | Internally derived prediction, not a vendor projection |

The study **must** maintain two isolated datasets/views: `eligible_features_as_of_T` (past observed data only) and `realized_targets_after_T` (subsequently finalized FFA outcomes). Join them only for evaluation after forecasts have been written. Never train on or blend with external provider fantasy projections, even if those would improve holdout accuracy.

## 3. Required data and data lineage

### 3.1 Required, preferred existing repository sources

| Dataset | Grain | Required fields / purpose | Validation |
|---|---|---|---|
| `canonical_ffa_player_week` | player × game/team | player ID, game ID, season, NFL week, actual team, mapped FFA position, **already-computed actual FFA points**, scoring-config hash, game completed/finalized markers, stat snapshot provenance | only eligible finished games; unique player-game-team logic; reconcile canonical totals; resolve trades; no external projected points |
| `canonical_ffa_dst_week` | D/ST team × game | **already-computed actual FFA D/ST points**, game ID, team; scoring definition/version and game finality | one D/ST per completed team-game; reconcile FFA scoring rules; no projected D/ST scores |
| `nfl_schedule` | game | game ID, home/away, season, week, date/kickoff, regular-season and completed status | valid teams, no duplicate games, canceled/unfinished excluded |
| `team_game_position` | game × offense × position | sum of canonical points, quality flags, contributing player count | one validated record per position per team-game |
| `defense_game_position` | game × defensive side × position | opposing offense, raw allowed, baseline, residual, point-in-time feature versions | every offensive team-game maps to opposite defense |
| `historical_cutoff_index` | target game/week × as-of time | all **completed and sufficiently finalized** prior games, legitimate source versions, score availability metadata | no future or in-progress game; enforce preweek vs per-game cutoff policy |
| `experiment_registry` | experiment/run | name, M3-3 milestone/substage, version, config, split, model params, code/data hashes, seed, commands, status | original M3-3 v0 and extensions independently reproducible |
| `source_provenance_allowlist` | dataset/field ancestry | input classification, original provider, source type, feature allowed flag, score finality and scoring hash | block all vendor precomputed fantasy projections, including renamed/nested fields |
| `prohibited_source_audit` | candidate source/field | source path, offending field/lineage, action (`REJECT/QUARANTINE`), reason | automated proof that no forbidden projection contributes to B00 or DvP variants |

Discover actual file paths, table names and columns rather than implementing these illustrative names literally. Create stable derived schemas only when needed. Keep raw **realized** points, denominators and all transformations inspectable. **Do not introduce a new player-scoring engine if Arbit already stores the scored FFA game data**; use recalculation solely for audit fixtures and reconciliation. Reject `projected_points` found in generic provider APIs or raw integrations even when the same payload also contains useful actual stats; select/allowlist only the permitted realized fields.

### 3.2 Optional supplementary sources; only if relevant and available

nflverse schedules, play-by-play, team statistics, weekly rosters, player/team participation, drives, and advanced opportunity metrics. Research separately: opponent pass attempts, targets, routes (only when historical coverage supports it), carries, sacks, turnovers, tempo, pass rate, neutral-situation pass rate, red-zone opportunities and target depth. Never combine incomparable coverage windows without explicitly stratifying. Weather, injuries, personnel, betting totals and WR coverage assignments belong to later conditional experiments unless the current slice needs them for *diagnosing instability*, not as assumptions of a finished model.

**Data lineage:** record upstream release/version and retrieval date; FFA scoring rule/hash; game ID crosswalk; source transformations; `source_is_final` vs historical as-of availability; completeness flags; per-season coverage; `projection_free=true` plus the audited source ancestry for **every** forecast feature and training target. Provider-originated actual NFL football observations may be permitted; provider-originated projected fantasy points are not.

### 3.3 Mandatory reconciliation checks

- 2016–2020 each had a 16-game regular season; 2021–2025 each had a 17-game regular season. Across 32 teams this implies `5 × (32 × 16) + 5 × (32 × 17) = 5,280` scheduled team-games. The canceled BUF–CIN game in 2022 subtracts two, yielding **5,278 completed team-games**, assuming no additional eligible-game exclusions. Verify against actual schedules rather than force the count.
- Expect up to **320 defense-seasons** (32 × 10). Audit per-season team/game distribution, 2022 BUF/CIN and minimum sample eligibility per test; do not assume all 320 meet every filter.
- Verify each valid game creates exactly two team-games, offense↔defense symmetry, position-group game rows, and D/ST reverse matchup orientation. No postseason/preseason; no phantom zero for canceled game or byes.
- Audit team renames/relocations/abbreviations; player trades and team-week assignments; duplicate stats; multi-position mapping; rushing/receiving QB credit; negative outcomes; overtime; 2016–2025 scoring revisions and corrections.
- Cross-check small fixed samples against canonical game scores and manual calculations, including a zero-production TE, multi-WR offense, traded player, D/ST turnover and one canceled-game exclusion.
- Produce `data_quality_report.md` plus machine-readable anomalies; block any model that draws from unresolved invalid source rows.
- Reconcile completed-game finality and when scored FFA actuals would have been available at every simulated cutoff. Distinguish completed games with late stat corrections and time-stamped historical snapshots from unknown historical finalization timestamps; declare a conservative fallback instead of claiming exact vintage replay.
- Run a full projection-lineage scan over the reused M3-3 datasets and all new B00/B01–B12 inputs: prove there are **zero dependencies on predetermined ESPN or other vendor projected fantasy points**; fail closed on unknown dependencies.

## 4. Continue the existing M3-3 study: audit and reproduce v0 first

**Important continuity instruction:** The implementing AI already created this M3-3 first evaluation and supplied its logic. Begin by locating that **existing implementation, code commit, data snapshot and outputs**. Inventory what is already done and what remains to be expanded. Run an exact reproduction using the existing scoring data, rather than independently reinventing the v0 methodology or implying the baseline is absent. Investigate discrepancies before changing v0. Preserve original artifacts untouched and write extension artifacts under a separate versioned M3-3 run ID.

Inspect `scripts/model/defense_position_study.py` and original outputs, then verify/recreate:

1. Position sum for every complete team-game, FB→RB as previously configured, valid zero handling.
2. Defense inversion, with separate D/ST interpretation.
3. Raw points and retrospective **same-season leave-one-game-out** offense adjustment: for each offense-season-position observation, subtract the offense's mean from its *other* eligible games that season. Explicitly handle seasons with only one eligible baseline game and record counts. This uses future games and is **permitted only for descriptive reliability analysis**, not prospective forecasting.
4. Odd NFL calendar weeks vs even NFL calendar weeks, noting that this differs from alternating a team's played games. Require ≥4 games in each split, recording actual unequal half sizes.
5. Per-position split-half correlation across eligible defense-seasons, with raw vs adjusted versions separately. Report Pearson, Spearman, paired counts, game-count distributions, means, SDs, outliers, CIs and diagnostic scatter plots.
6. Reproduce v0 `r`, inferred single-game reliability, `k` and `w(n)` exactly. For WR, reference expected reported numbers `r≈0.158`, `single-game≈0.022`, `k≈44.1`, `w(8)≈15.4%`, but **verify** the actual code's denominator and effective half sizes. If `r=.158` and exact equal `m=8`, the simple formula gives `k≈42.63`, not 44.1; investigate weighting rather than silently fixing results.

Under an *equal-size, stable-latent-trait, independent-error* model:

```
r_m = m * tau2 / (m * tau2 + sigma2)
k = sigma2 / tau2 = m * (1 - r_m) / r_m
single_game_reliability = 1 / (1 + k)
w(n) = n / (n + k)
```

`tau2` = between-defense-season stable tendency variance; `sigma2` = within-defense-season single-game noise variance. The single-game number is *model-implied*, not separately observed. With unequal split sizes, the simple equal-`m` conversion is approximate; compare against an explicit variance-component model. A negative/small estimated correlation should not mechanically produce negative, infinite, or falsely precise model weights: mark unstable/unidentified and estimate uncertainty or use a constrained hierarchical estimator.

**Freeze M3-3 v0**: retain its existing outputs, source hashes, config and a reproduction/discrepancy report. Never erase the initial finding. Audit the v0 data lineage to confirm it used actual completed-game FFA results and no external predetermined fantasy projections; if a forbidden input is found, preserve the original as historical evidence but mark its conclusions **CONTAMINATED/NOT VALID FOR INFERENCE**, then rerun a projection-free corrected branch.

## 5. Experiment program

Every new M3-3 experiment must specify **hypothesis**, estimator, dataset, actual-vs-generated data classification, cutoff, permitted source ancestry, training/forecast timeline, baseline comparator, evaluation metric, uncertainty interval, sensitivity checks, and conclusion. Version the experiment before examining 2025 predictive holdout results. No B/C experiment may use provider-projected fantasy points at any stage; all target labels are actual completed-game FFA scores.

### Phase A — Descriptive and reliability experiments

- **A00: Raw DvP landscape.** League/position/year distributions, team mean, within-team SD, percentiles, outliers, negative scores, coefficient of variation where meaningful; compare raw defensive rankings with adjusted rankings.
- **A01: v0 odd/even exact replication.** Raw and leave-one-out-adjusted split-half Pearson; reproduce original r/k/weights.
- **A02: Split method sensitivity.** Calendar odd/even; alternating played games; 1st vs 2nd half; first 6 vs next 6; repeated random balanced splits (e.g. 1,000 deterministic seeds); varying minimum-game requirements. Do **not** interpret all random splits as independent samples.
- **A03: Opponent adjustment sensitivity.** None; retrospective leave-one-out mean; robust median; season/league-strength-adjusted offense baseline; check whether adjustments improve *repeatability* and, separately, forecasting.
- **A04: Position-specific sample stability.** QB/RB/WR/TE/DST and any other configured group; stratify game counts and broad eras. Compare CIs across positions and avoid overinterpreting cross-position differences.
- **A05: Variance decomposition.** Fit variance-component models for between defense-season `tau2`, within defense-season noise `sigma2`, season-wide effects and where feasible offense/opponent effects. Include unequal game counts. Compare method-of-moments or hierarchical partial pooling with v0 `k`; report boundary estimates, convergence and uncertainty.
- **A06: Temporal stability.** First→second-half correlations, weeks-apart decay, rolling windows, 3-/5-/8-game behavior, schedule order, early vs late, personnel-era shifts when data exists. Diagnose whether odd/even masks within-season defensive changes.
- **A07: Between-season carryover.** Defense `season s` vs `s+1`, with team-ID continuity and relocations; fit decayed prior vs complete seasonal reset. Never describe 44 games as 2.5 seasons of guaranteed persistent trait.
- **A08: Noise, placebo and null.** Shuffle defense labels/outcomes within compatible season/position strata while preserving observation structure; repeat correlations to construct null distribution. Negative control: future/random opponent labels must not create a forecast benefit. Bootstrap uncertainty by appropriate season/team-season clusters and check against ordinary iid bootstrap for sensitivity.
- **A09: Signal decomposition.** If existing history supports it, separate *volume* (opponent plays, pass attempts/targets/carries) from *efficiency* (points per opportunity), touchdowns, turnovers and explosive plays. First test repeatability; don't assume additional complexity helps.
- **A10: Data/era robustness.** Pre/post 2021 schedule length; exclude 2020 and 2022 individually; 2016–2020 vs 2021–2025; leave-one-season-out, outlier trimming/winsorization comparison, home/away, bye/rest and known schedule anomalies. Report substantive differences.
- **A11: M3-3 source/score audit.** Validate original v0's FFA-scoring hash, realized-outcome status, source ancestry and elimination of external fantasy projections; compare initial M3-3 conclusions with the validated reproduction and document what changed (if anything).
- **A12: Completion and correction sensitivity.** Compare completed-game-only eligibility against games with uncertain as-of score-finalization timestamps; quantify the effect of late stat corrections and conservative exclusions on r, k and coverage. This is a *data-vintage diagnostic*, not permission to use future final results as features.

### Phase B — Chronological next-game prediction experiments

Build an **as-of feature engine**. For every scheduled test game `g` in week `t`, generate all inputs from **completed games with eligible FFA actual results known by the locked pre-week cutoff**. For an offense's expected position-group points, compute an **Arbit-owned, past-actuals-only** estimator; shrink early-season observations toward a neutral prior built from previously completed historical games and log its derivation and exposure. If no offense history, use eligible prior-season/league FFA actuals—**never ESPN's or a vendor's projected scores and never the full target season**. Adjustments of defense history must also use only information available at the then-current cutoff; retrospective leave-one-out values cannot be recycled directly. Separate the target game's eventual finalized FFA score (evaluation label) from all pregame inputs. Optional per-game-update mode is a separate experiment, not a silent exception to the preweek policy.

Use a reproducible evaluation sequence: **development 2016–2023; validation/tuning 2024; conditionally held-out forward predictions on 2025.** Historical development performance is not an unbiased test if trained/tuned on the same years; create rolling-origin, out-of-fold development folds (for example, train through year `s-1`, forecast year `s`) with sufficient startup history. Lock preprocessing, feature variants, metrics, tuning grid and decision rules *before inspecting any 2025 predictive outcomes*; train selected parameters using through-2024 eligible actuals, then predict 2025. **Integrity qualification:** M3-3 v0 was already computed over **2016–2025**, so 2025 is NOT fully untouched at the research-question / descriptive-analysis level. It can serve as a restricted evaluation of prospectively generated 2025 forecasts only if neither those outcomes nor 2025-derived r/k/summary parameters informed the selected candidate. Disclose prior exposure. If the implementing AI has already inspected 2025 prediction errors or tuned features using 2025, do not call it an untouched holdout; treat 2025 as exploratory and reserve future **2026 chronological shadow predictions** (only future games after a registered freeze) or a later season for genuine confirmation. Never tune v0 `k` using all 2016–2025 if evaluating its 2025 predictions. All historical targets, including 2025, are **actual finalized FFA scores**, never vendor projected points.

Test variants using the **same** offense forecast, games, scoring and eligibility:

- **B00: Offense-only null.** **Internally calculate** the position group's next-game expected FFA points using only prior completed-game actual FFA scores and permissible realized historic stats; no DvP feature and **no ESPN/vendor projected-point baseline, seed or imputation**. This is the mandatory base comparator.
- **B01: Raw DvP naive.** Add prior-games defense raw position points allowed vs contemporary league average (with explicit handling of small `n`).
- **B02: Adjusted DvP.** Use prior-only offense-adjusted defensive residuals; no reliability shrinkage.
- **B03: v0 k-shrunk adjusted DvP.** `defense_effect = w(n) × mean(prior-only adjusted residuals)` with position-specific `k` estimated exclusively on historical training data. Forecast: `offense_expected + defense_effect` (subject to any selected calibrated scaling). Compare n=0, 1, 2, 4, 8, 12, 16 explicitly.
- **B04: Empirically tuned k.** Search a predeclared reasonable grid of nonnegative `k`; tune on development/2024 without inspecting 2025. Measure whether prediction-optimal `k` agrees with reliability-inferred `k`.
- **B05: Recency DvP.** Exponential decay with predeclared half-life grid (e.g. 2/4/8 games), rolling 3/5/8 games, plus shrinkage. Compare effective sample size rather than using raw game count if weights differ: `n_eff = (sum weights)^2 / sum(weights^2)` as an approximation under independent observation noise.
- **B06: Temporal/hierarchical DvP.** Partial pooling with defense-season random intercept, optional dynamic state and cross-season prior learned exclusively from past years. Compare against simpler B03 rather than adopting complexity automatically.
- **B07: Opportunity/efficiency alternatives.** If valid historical inputs available at forecast time, test defensive rates (allowed targets, carries, pass attempts, per-target/per-carry FFA value) independently and jointly. Watch for double counting with the offense baseline.
- **B08: Context-stratified DvP diagnostic.** Test conditional impact by season week, sample count, underdog/favorite when valid pregame free information exists, and matchup type without adding unavailable weather/injury datasets to the required base implementation.
- **B09: Adversarial negative controls.** Defense labels shuffled within appropriate years, random noise, next-week labels improperly shifted, and intentionally future-contaminated fixtures in *unit tests only*. Legitimate forecast should beat placebo; deliberate future leaks must trigger assertions.
- **B10: Cutoff-policy sensitivity.** Compare forecasts frozen before first game of the week versus explicit pregame refreshes that may incorporate additional **already-completed** Thursday/Sunday games. Quantify accuracy/coverage improvements and document different real-world decision availability. Never give a locked preweek model access to late-week results.
- **B11: Projection-contamination resistance.** Inject extreme synthetic ESPN/vendor projected-point rows or renamed equivalent fields into test-only inputs; assert B00–B10 predictions are unchanged or pipeline fails closed, with offending lineage recorded. This is an **integrity test**, not an allowed predictive variant.
- **B12: Actual-score as-of robustness.** Evaluate when finalized FFA scoring snapshots become eligible, compare late-correction treatment, and report how many forecasts lose historical coverage under conservative available-by-cutoff eligibility. Never allow uncertainty to be replaced by vendor projected values.

### Phase C — Conditional player-level Sit/Start impact

**Only begin after Phase B has an identified, credible group-level signal or a compelling reason to test a specific conditional signal.** Discover Arbit's existing player-projection implementation and FFA league configuration first; do not reuse any imported ESPN/other vendor projected scores that may exist elsewhere in the product. C00 must be an **Arbit-computed** player baseline using eligible historical actuals, not the league host's canned projection.

- **C00:** Existing **internally derived, projection-source-compliant** player baseline, no DvP. If the current Arbit baseline includes vendor-projected fantasy points, build or isolate a lawful actual-history-only baseline for this research before comparison; do not mask the contamination.
- **C01:** Add a conservative group-level DvP adjustment to individual forecasts using only past-known player-specific usage/share and team expected opportunity. Never add the entire WR-group adjustment to each WR.
- **C02:** Compare additive-point, proportional-share and opportunity × efficiency allocation. No double-counting with QB/receiver correlated output or existing game-script/weather features.
- **C03:** If route/slot/outside, target share or role data has sufficient consistent coverage, test it as a conditional secondary interaction; do not require it for the v1 study.
- **C04:** Build historical realistic same-position and lineup-slot Sit/Start comparisons (including FLEX if league permits), using players eligible and plausibly available before kickoff. Pairwise target: which candidate scored more actual FFA points? Avoid cherry-picking only close decisions in the primary metric; report close-projection subgroup separately.
- **C05:** Compare decisions and projection errors: offense/player baseline vs +DvP; report pairwise decision accuracy, tie policy, average actual points gained/lost from changed choices, number of recommendations changed, and worst-case regret. Evaluate lineups with league roster/scoring constraints where trustworthy history exists.

If player-level data/contracts are unavailable, mark Phase C `BLOCKED`; this does **not** invalidate group-level testing.

## 6. Statistical estimation, uncertainty and model logic

**Research estimator:** For defense `d`, position `p`, season `s`, game `g`, `Y = FFA position-group points allowed`. Retro residual: `R = Y - mean(other games of same offense-season-position)`. Odd/even split uses defense-season mean residual in each subset. Calculate correlation with CIs, sample counts and dispersions. An optional hierarchical form is `R(d,s,g,p) = mu(s,p) + alpha(d,s,p) + epsilon(d,s,g,p)` with `alpha` a defense-season latent effect. Where needed, incorporate offensive expectation uncertainty and season-wide effects; avoid fitting an unidentifiable parameter set.

**Forecast estimator:** `O_hat(o,p,t)` = **Arbit-computed** time-correct offense position expectation from completed-game FFA actuals, `R_hist(d,p,t)` = weighted mean of defense adjusted residuals from completed games observed before cutoff, `w = n/(n+k)` for ordinary unweighted eligible games or an independently justified effective-N rule for time decay. Basic prediction `Y_hat(o vs d,p,t) = O_hat + w * R_hist` (optional **internally** tuned multiplicative calibration learned only from eligible FFA actuals). Explicitly report whether residuals were calculated using point-in-time offense baselines as each historical game happened or recomputed using information known by *current* cutoff; test both when feasible and never allow post-target data. **Do not interpret any `O_hat` or `Y_hat` as a provider projection; each is constructed here from observed scores.**

**Varying observations:** Correct unequal split exposure; for independently noisy split means with sizes `mA,mB`, their expected correlation under the variance-component model is approximately `sqrt([mA/(mA+k)] [mB/(mB+k)])`. Don't silently replace each half size with 8 or infer an exact `k` from one pooled r without checking. If sample correlation is near 0 or negative, label identification weak and use a nonnegative constrained variance estimate / interval rather than an invalid negative k.

**Resampling/inference:** Use clustered or blocked methods preserving appropriate game/team/season dependencies; 320 defense-seasons are not 320 fully independent franchises, and the same game connects two teams. Compute uncertainty on correlations, k and improvements with at least 1,000 deterministic resamples where feasible; compare cluster schemes (season blocks and defense-season blocks) and flag wide intervals. Apply multiple-comparison control (or clearly distinguish exploratory from confirmatory results) if evaluating many position/variant combinations. Do not treat a single favorable p-value as production proof.

**Shrinkage meaning:** `w(n)` is credibility assigned to that defense-specific estimate **inside the DvP estimator**; it is *not* the percent of overall Sit/Start model weight. A low r does not alone prove there is no incremental predictive utility.

**Distribution:** FFA position totals may be skewed and contain negatives/zeros, so inspect assumptions; compare means vs robust estimates, squared-error metrics vs absolute-error metrics, and ordinary vs robust residual likelihood where justified. Never use a count-only family blindly on signed fantasy points.

**Conditional dependence:** If adding QB and WR/RB/TE defensive factors in a common player model, identify shared scoring and game-environment effects. Test for collinearity and avoid treating correlated features as independent evidence.

## 7. Primary evaluation metrics and decision rules

**Phase A (descriptive):** split-half Pearson/Spearman, raw vs adjusted r, variance components `tau2/sigma2`, model-implied single-game reliability, k/w(n), confidence intervals, split sensitivity, season variation, age-of-evidence decay.

**Phase B (primary):** held-out **per-position forecast RMSE** and paired delta relative to B00 on exactly matching games; secondary MAE, mean signed error (bias), per-season and per-position calibration (e.g. predicted vs observed decile means), rank correlation, and performance by early/late season/sample-size bin. Report both per-game absolute points and relative changes. RMSE is sensitive to outliers; MAE helps diagnose whether improvements are broadly distributed.

**Phase C (conditional):** player-level RMSE/MAE and true pairwise correct-choice percentage plus fantasy points gained/lost from changed choices; number of actionable changes and calibrated confidence where available. Account for selection/eligible-player bias.

**Baseline parity:** Compare all variants on a *common eligible sample* of **finalized actual FFA outcomes**. If a variant needs extra data, show both common-sample comparisons and its reduced coverage; never claim superiority solely because it skipped hard games. No model may claim performance improvement by comparing against ESPN/vendor projected fantasy points; B00 is the independent Arbit actual-history-only comparator.

**Predetermined research decision rule (suggested default):**

- `PROMISING`: better than B00 on the designated evaluation period (conditionally held-out 2025 if integrity is defensible, otherwise future prospectively frozen games), improvement direction broadly consistent across pre-evaluation rolling folds and not solely a few outlier games; uncertainty and coverage clearly reported; no data leakage, vendor-projection use, or broken tests. If the predeclared paired uncertainty interval excludes 0, stronger evidence.
- `INCONCLUSIVE`: improvement is small, interval overlaps zero, changes sign materially by season/position, or model cannot be distinguished from simple baselines. Do not convert inconclusive into a positive model weight.
- `NOT USEFUL`: no meaningful incremental improvement or systematic deterioration, despite complete valid test coverage. Recommend zero influence in the Sit/Start model unless a narrower subgroup is independently validated later.
- `BLOCKED`: insufficient verified completed-game FFA data, conflicting scoring, detected vendor-projection dependency, unavailable as-of features or failing data/leakage contracts. Never label blocked as a negative scientific finding.

Do **not** require an arbitrary p-value or universal minimum percentage improvement across all positions; predeclare any *practical* minimum improvement after inspecting baseline error and the impact on decision quality **using development data only**. **Treat 2025 as conditionally confirmatory at best**, due to v0's existing exposure to 2016–2025; clearly state what was previously examined. Don't repeatedly inspect or retune to 2025; if used for forecast tuning, require truly later prospectively frozen predictions for independent confirmation.

## 8. Test catalog: mandatory automation and audit

Implement `pytest` or the existing repository test framework, plus small fixed fixtures. Every test must be runnable locally/CI without paid APIs.

**M3-3 continuity and the actual-score/projection firewall**

- **T29** locate original M3-3 script, configs, input snapshots, result artifacts, milestone notes, and prior findings; verify the new workflow builds on them instead of rewriting or orphaning them; produce a checkable continuity manifest.
- **T30** verify canonical per-game/player and D/ST source rows contain **finalized actual FFA** outcomes under the league configuration; independently spot-check computed examples. Reject default PPR/nflverse generic fantasy scoring as a substitute.
- **T31** scan candidate tables, APIs, CSVs, caches, feature pipelines and prediction baselines for ESPN/other provider **projected fantasy points**, including `projected_*`, vendor matchup rankings converted to predicted points, nested fields and renamed projected values; build a lineage-based reject/quarantine manifest.
- **T32** inject bogus ESPN projected scores and other-vendor projected fantasy scores into test-only fixtures, including through an alias such as `opponent_expected`; assert forbidden values cannot influence B00–B12 or C00–C05 outputs, either by exclusion or explicit pipeline failure.
- **T33** fail closed on input with unknown actual-vs-projection source category or absent critical ancestry; a benign-looking column name must not bypass the provider-projection exclusion.
- **T34** games not started, in progress, suspended, canceled, unfinalized, or after cutoff have no usable **actual FFA score** as a pregame feature; verified completed games may contribute after their actual result is available. Preserve canceled-game coverage as missing, not zero.
- **T35** a Thursday game completed before Sunday can enter Sunday pregame-refresh experiments, but **never** the locked preweek forecast; an in-progress Sunday game cannot enter an afternoon prediction under either mode.
- **T36** targets and training labels are actual completed-game FFA points; model-generated forecasts live in distinct columns/tables; joining actual labels into feature creation is impossible by schema and time assertion.
- **T37** scoring settings/hash changes trigger explicit invalidation/recomputation/annotation; no silent switches between PPR/half-PPR/FFA scoring and no use of vendor scores to fill FFA gaps.
- **T38** B00 fallback/prior can be reconstructed using only historically eligible final FFA scores; refuse unknown-provider projected-point seed, weekly forecast, preseason ranking, or imported estimate.
- **T39** late-stat-correction fixture respects configured score availability and archives limitations; same earlier forecast does not change when *future* actuals/retroactive provider projections are altered.
- **T40** generated prediction ancestry and final report machine assertions demonstrate `forbidden_vendor_projection_dependencies == 0`; automatically mark research results invalid if nonzero.

**Scoring/aggregation**

- **T01** deterministic player-point sum from canonical FFA fixtures; no different scoring logic.
- **T02** FB→RB only when specified; exact position whitelist, unknown/dual positions flagged.
- **T03** true zero TE and other zero outputs; ingestion missingness remains distinct from true zero.
- **T04** negative points and decimals preserved; no clamping/rounding before aggregation.
- **T05** multi-player, traded-player, duplicate and same player/two-team edge cases.
- **T06** exactly two team-games per finished valid game; no postseason, bye/canceled or duplicate games; per-year reconciliation to authoritative schedule.
- **T07** offense/defense side reversal and score sign; D/ST special offense-vulnerability orientation with small manually verified fixtures.

**Statistical calculations**

- **T08** leave-one-game-out expectation manually matched; singleton/no-baseline handled without NaN/infinite weights.
- **T09** odd vs even *NFL week*, not index order; compare alternative split implementations.
- **T10** half minimum `>=4` enforced by actual eligible games, no future-filled phantom games.
- **T11** known synthetic equal-size example reproduces `r_m`, `k`, `r1` and `w(n)`; tests `n=0`, `n→∞`, nonnegative bounds, r≈0, r<0 and invalid inputs.
- **T12** unequal half sizes produce expected variance-model handling and warnings for approximate shortcut.
- **T13** fixed seed → same bootstrap, permutation, fold assignments and metrics; different seed changes stochastic draws but not source data.
- **T14** hierarchy/model fitting recognizes non-convergence and zero-variance/boundary cases rather than falsely reporting an identified effect.

**No-leakage and evaluation**

- **T15** as-of `t` features contain no game outcome after forecast cutoff; direct time assertions for every source row.
- **T16** perturb or delete future weeks/2025 data and prove earlier historical features/forecasts are identical (within deterministic tolerance).
- **T17** no use of target game's own result, season-end offense mean, rest-of-season injury/stats, or holdout outcomes in training/normalization.
- **T18** 2016–2023/2024/2025 split integrity, no overlapping targets, no hyperparameter optimization using 2025.
- **T19** all variants share identical eligible target rows for primary comparisons; coverage differences surfaced.
- **T20** predictions generated and stored before outcomes merged; test join by immutable game/team/position key and 1-to-1 row count.
- **T21** synthetic generated data with known stable defensive effect: estimator recovers correct sign and increased reliability as n grows, within Monte Carlo tolerance.
- **T22** synthetic pure-noise defense: shrinkage/variant test should not systematically improve held-out predictions; diagnose false positive rate.
- **T23** synthetic defense trait shift after injury/change: temporal methods detect expected degradation vs static split method.
- **T24** permutation/placebo signals have no stable material uplift across seeds.
- **T25** time-aware offense baselines correctly handle cold starts, weeks with no past games and postseason boundary.
- **T26** scoring/ID compatibility with Arbit player projection system; ensure no direct writing to existing prediction weights.
- **T27** artifact schema, config hash, run manifest, summary statistics and exported metrics can be read back and reproduced from same snapshot.
- **T28** robustness test where a single outlier NFL game or entire season is omitted; quantifies effect rather than silently hiding it.

All failed tests must block claims of valid production or holdout results. **T29–T40 are mandatory source-integrity gates** and must be executed, not merely documented; if their preconditions are unavailable, classify the affected research as `BLOCKED`. Classify known warnings separately from failures. Existing T01–T28 remain mandatory; numbering deliberately preserves the original tests to maintain M3-3 traceability.

## 9. Execution sequence, gates and proposed repo structure

**Phase 0 — M3-3 continuation, audit & freeze.** Read instructions and **existing M3-3** history; identify what the same agent has already done; map current script/data/results/commit; validate the canonical FFA final-score inputs and all source ancestry; reproduce v0 without altering it; create `M3-3_CONTINUITY.md`. **Gate:** original report traced, scoring/game reconciliation understood, and no vendor-projection dependency (T29–T33, T37–T38).

**Phase 1 — Projection-free completed-game pipeline.** Reuse existing final FFA point tables; build validated game/team/position views, offense/defense inversion, D/ST handling, source provenance, completed-game finality and as-of index; write T01–T07 and T30–T40 with exclusion/quality reports. **Gate:** data, finality, projection-exclusion and time-correctness tests pass.

**Phase 2 — Reliability lab.** Implement A00–A12 including exact v0 continuity, score-finalization sensitivity and optional variance-component models; generate tables/plots/CIs, evaluate unstable k assumptions. **Gate:** reproducible interpretation, all conclusions tied to actual FFA outcomes, no vendor-projection lineage, no forced predictive claim.

**Phase 3 — Walk-forward engine.** Implement preweek as-of cutoff, past-actuals-only offense baseline B00, variants B01–B12, and optional independent per-game refreshes; write leakage tests T15–T25 and T32–T40; run development folds and 2024 validation. **Gate:** selected method/metrics committed and 2025 exposure status documented; forbid contaminated holdout claims.

**Phase 4 — Restricted holdout / prospective confirmation.** Freeze candidate trained through 2024; evaluate on 2025 actual FFA outcomes **only if** no 2025 predictive outcome or 2025-estimated parameter affected model selection. Because v0 already included 2025, clearly label the result `CONDITIONALLY_HELD_OUT`, not fully untouched. If contaminated, mark 2025 exploratory and prospectively freeze the method before forecasting **future** 2026 games/later seasons as an honest confirmatory shadow test. Produce paired metrics, intervals, errors and recommendation. **Gate:** explicit `PROMISING/INCONCLUSIVE/NOT USEFUL/BLOCKED` per position and globally, with honest independence qualification.

**Phase 5 — Conditional downstream translation.** If justified, implement C00–C05 using Arbit's own projections derived from eligible past actuals and actual completed FFA player outcomes, without production changes. If the current app has an external-prediction dependency, replace/segregate it for this research rather than comparing against vendor projections. **Gate:** only promote with credible incremental evidence and explicit project approval.

**Recommended logical structure** (adapt existing repo; don't duplicate modules unnecessarily):

```text
scripts/model/defense_position_study.py       # existing Slice M3-3 v0; preserve original
scripts/model/dvp/                          # extend the existing M3-3 architecture, not a parallel rebuild
config/dvp/                                # pinned YAML/JSON experiments, seeds, splits
model/dvp/                                 # reusable pure model/prediction functions if idiomatic
tests/model/dvp/                          # synthetic, unit, integration, leakage, regression
docs/research/dvp/                        # M3-3 continuity, actual-score/projection firewall, decisions
artifacts/dvp/<run_id>/                   # versioned M3-3 runs; never overwrite initial outputs
```

Do not commit bulky raw NFL tables or personally identifying data. Prefer Parquet for derived observations, CSV for human-readable metrics, JSON for manifests, Markdown for explanation, SVG/PNG for plots. Use an existing Python environment/package manager; declare and pin new dependencies only when needed. Modularize ingestion, mapping, aggregation, adjustment, reliability, modeling, backtesting, reporting and validation.

**Required CLI contracts** (implement in repo-idiomatic form; examples are interfaces, not assertions that scripts exist):

```bash
python -m <project_dvp_cli> audit --config config/dvp/base.yaml
python -m <project_dvp_cli> reproduce-v0 --config config/dvp/base.yaml
python -m <project_dvp_cli> reliability --config config/dvp/reliability.yaml
python -m <project_dvp_cli> backtest --config config/dvp/backtest.yaml --stage development
python -m <project_dvp_cli> backtest --config config/dvp/backtest.yaml --stage validation
python -m <project_dvp_cli> backtest --config config/dvp/frozen.yaml --stage holdout
python -m <project_dvp_cli> report --run-id <id>
pytest tests/model/dvp -q
```

`holdout` command must require a frozen validated manifest/config; never launch it from an exploratory tuning run. Make dry-run, verify-only, and resume modes available when appropriate. Use atomic output writes and idempotent reruns.

## 10. Config and machine-readable result schema

Use explicit default config, not code-hidden heuristics. Preserve actual project keys if an existing M3-3 config already exists and extend it compatibly:

```yaml
project: arbit-ffa
workstream_id: M3-3
workstream_mode: continue_existing_experiment
slice: defense_vs_position
original_study_script: scripts/model/defense_position_study.py
scoring_source: existing_canonical_ffa_layer
scoring_basis: actual_ffa_points_from_completed_games_only
external_predetermined_fantasy_projections_allowed: false
source_policy:
  enforce_lineage_allowlist: true
  fail_on_unknown_source: true
  allowed: [canonical_final_ffa_actuals, completed_game_realized_nfl_stats, historical_schedule_metadata, internal_model_outputs_as_outputs_only]
  forbidden: [espn_projected_fantasy_points, other_vendor_projected_fantasy_points, imported_fantasy_point_forecasts, vendor_projection_based_priors]
  allow_vendor_actual_stats_after_completion: true
  scoring_config_hash_required: true
as_of_policy:
  required_game_status: completed_and_finalized
  finalized_actual_available_by_forecast_cutoff: true
  default_cutoff: pre_first_game_of_nfl_week
  per_game_update_is_separate_experiment: true
  target_labels_join_only_after_forecasts_frozen: true
seasons: [2016,2017,2018,2019,2020,2021,2022,2023,2024,2025]
season_type: REG
split:
  development: [2016,2017,2018,2019,2020,2021,2022,2023]
  validation: [2024]
  holdout: [2025]
forecast_cutoff: pre_first_game_of_nfl_week
holdout_integrity:
  prior_m3_3_v0_uses_2025: true
  status_2025: conditional_holdout_only_if_no_predictive_contamination
  use_prospective_future_2026_games_if_2025_contaminated: true
positions: discover_from_ffa_config
min_split_half_games: 4
original_half_method: nfl_week_odd_even
experiment_methods: [A00,A01,A02,A03,A04,A05,A06,A07,A08,A09,A10,A11,A12,B00,B01,B02,B03,B04,B05,B06,B07,B08,B09,B10,B11,B12]
primary_metric: RMSE
secondary_metrics: [MAE,mean_error,season_rmse,position_rmse]
bootstrap_replicates: 2000
random_seed: 1729
holdout_requires_frozen_manifest: true
write_to_production: false
```

Every `experiment_results.json` record must include `workstream_id=M3-3`, `experiment_id`, `status`, `hypothesis`, `data_hash`, `scoring_hash`, `code_commit`, `source_ancestry_hash`, `forbidden_vendor_projection_dependencies=0`, `actual_game_finality_policy`, `as_of_policy`, `train/validation/test_periods`, `holdout_independence_status`, `sample_count`, `coverage_pct`, `estimator`, `parameters`, `primary_metric`, `baseline_metric`, `absolute_delta`, `relative_delta`, `interval`, `placebo_summary`, `subgroups`, `tests_passed`, `limitations`, `evidence_paths`, `decision`, `reason`, `next_steps`. Assertions must fail if an external projected-point dependency is detected.

## 11. Required reports, visuals and handoff

Deliver at least:

1. `README.md` / `RUNBOOK.md`: setup, data provenance, exact execution commands, reuse, runtime and offline behavior; explicitly label research **Slice M3-3 continuation** and vendor-projection exclusion.
2. `DATA_DICTIONARY.md` + `DATA_QUALITY.md` + `SOURCE_PROVENANCE.md`: field definitions, canonical **completed-game actual FFA** scoring source, cutoff/score-finality gates, joins, coverage, anomalies, counts, excluded vendor-projection fields and known exclusions.
3. `METHODOLOGY.md`: hypotheses, original and extended formulas, assumptions, look-ahead protections and predeclared metrics.
4. `M3-3_CONTINUITY.md` + `V0_REPRODUCTION.md`: existing study's original owner/logic, paths, experiment stages and decisions; original vs reproduced r/k/weights for *every* position, especially WR 0.158/44.1; original artifacts preserved.
5. `EXPERIMENT_REGISTRY.md` + machine-readable config/results: all planned/executed/blocked studies and fixed seeds.
6. `RELIABILITY_REPORT.md`: raw/adjusted odd-even, other splits, variance models, CI, noise tests, season variations, half-game counts, plots and interpretation.
7. `BACKTEST_REPORT.md`: actual-FFA-outcome paired B00 vs all variants, rolling folds, 2024 tuning, **honestly qualified 2025 conditional holdout / prospective follow-up**, uncertainty, leak/projection-firewall tests and error analysis.
8. `MODEL_CARD.md`: scope, intended/not intended uses, feature availability, model limitations, safety fallbacks, performance by position and whether eligible for promotion.
9. `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`: evidence-backed choices, code/files changed, test output, unresolved issues, next runnable action and clear continuation context.
10. `FORECASTS.parquet`, `METRICS.csv`, `RESULTS.json`, run manifest/hash and reproducible plots (split scatter, correlation with CIs, rolling repeatability, k-vs-n weight curves, error by season/position, paired improvement by variant, calibration).
11. `PROJECTION_EXCLUSION_AUDIT.json` + `SCORE_FINALITY_AUDIT.json`: machine-checkable inventories proving zero vendor projected fantasy-point ancestry and that every training feature was an eligible past observed actual at its declared cutoff; include quarantined or unavailable cases.

**Before completion**, run the entire relevant test suite **including T29–T40**, verify original M3-3 artifacts unchanged, reproduce from pinned configuration, inspect an independently generated sample of outputs for sign/units/join correctness, and provide a final per-position conclusion table with `repeatable trait?`, `forward benefit?`, `effect-size estimate`, `uncertainty`, `stable across seasons?`, `recommended use`, and `limitations`. Report `source_provenance_pass`, `score_finality_pass`, `forbidden_vendor_projection_dependencies=0`, and honest 2025 holdout status before claiming any successful result.

## 12. Final decision logic

```text
Existing Slice M3-3 implementation and original results discovered/preserved?
  NO  -> Investigate repository and past work; flag CONTINUITY_BLOCKER.
  YES -> Inputs have canonical FFA scoring + completed actual game results +
         verified point-in-time eligibility + zero external fantasy projections?
         NO  -> BLOCKED/CONTAMINATED; quarantine disallowed fields, correct
                the source and rerun without overwriting M3-3 v0.
         YES -> Original v0 reproducible?
                NO  -> Report discrepancies; resolve or explicitly disposition.
                YES -> Estimate reliability + uncertainty from FFA actuals.
                       Signal absent/unstable? Do not automatically abandon;
                       run prespecified low-cost forward placebo/baseline test.
                       Forward B00 (actuals-only) vs DvP comparison improves
                       next-game forecasts of actual FFA position totals?
                         NO  -> NOT USEFUL/INCONCLUSIVE; DvP production effect=0.
                         YES -> Robust to eras, perturbations, uncertainty,
                                simplicity, matching coverage and no leakage?
                                  NO  -> INCONCLUSIVE; research only.
                                  YES -> PROMISING at team-position level.
                                         Does projection-free Arbit player A/B
                                         improve actual FFA Sit/Start choices?
                                           NO  -> Retain research; don't promote.
                                           YES -> Recommend controlled
                                                  integration after approval.

2025 validation status is always labeled accurately:
  clean prospective parameters despite earlier descriptive 2025 exposure
    -> CONDITIONALLY_HELD_OUT; state limitation;
  any 2025 forecast tuning/outcome peeking -> EXPLORATORY;
    only a future, prospectively frozen 2026+ run can confirm independently.
```

## 13. Known caveats to explicitly resolve in write-up

- The historic 2016–2025 data contain 32 teams × 10 seasons, **not** 320 independent defensive organizations; avoid underestimating uncertainty.
- M3-3 v0 was already implemented by the same AI and its descriptive study used all 2016–2025 seasons: don't overwrite it, don't call 2025 entirely untouched, and don't use 2025-derived parameter estimates for purportedly held-out 2025 predictions.
- V0 adjusted offense means use *other games in the same completed season*; these are appropriate for retrospective research only. Forecast backtesting must be point-in-time.
- Only already-determined **actual FFA points from games completed and result-available by each cutoff** may train or inform B00/DvP forecasting. Historical final data used as *later outcome labels* must be kept separate. Never blend in ESPN's or any provider's predetermined projected fantasy points, even when those were available pregame.
- Odd/even week agreement can conceal midseason personnel/scheme changes; add chronological tests without deleting v0.
- `w(8)≈15%` is *within-DvP shrinkage* under a specified model, **not** 15% contribution to the full Sit/Start model.
- Position-group FFA totals measure matchup context, not the player-specific fraction or role adjustment.
- A null group-level result does not exclude all possible player-level conditional matchup signals; a positive repeatability result does not guarantee a useful forecast.
- Model assumptions and any backtest evidence must be evaluated independently by position; do not use WR `k` for QB/TE/DST by default.
- Verify whether the source stats are truly available through 2025 in the repository; some legacy nflverse bundled `player_stats` artifacts were superseded by per-season `stats_player` releases. Existing canonical FFA data take precedence if complete.
- Historical final stats can differ from data available at the time due to stat corrections; report this limitation and use vintage archives if available.
- No production merge solely because correlations look positive. Only confirmatory incremental predictive and player decision value can justify influence.

## 14. Source references for methodology and upstream data (verify as needed)

- nflreadr schedule field dictionary: https://nflreadr.nflverse.com/articles/dictionary_schedules.html
- nflreadr player stats loading/docs: https://nflreadr.nflverse.com/reference/load_player_stats.html
- nflreadr data update schedule: https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
- nflverse data release repository: https://github.com/nflverse/nflverse-data
- NFL's canceled 2022 Buffalo–Cincinnati game: https://www.nfl.com/_amp/week-17-buffalo-cincinnati-game-will-not-be-resumed-neutral-afc-championship-gam
- Split-half methodology and permutation sensitivity: https://pmc.ncbi.nlm.nih.gov/articles/PMC8858277/

## Start now — implementing agent instruction

**You are extending the original work that YOU already completed for Slice M3-3.** Begin by reading the existing Arbit repository and source-of-truth context. Find `scripts/model/defense_position_study.py`, the existing first M3-3 experiment, its scoring slice, configuration, execution logs and outputs. Establish exactly what was done, how it was done, and what evidence was produced. Preserve it before changing anything. Build `M3-3_CONTINUITY.md`, the file-level source map and the score/projection provenance allowlist. Verify that all inputs are completed-game **actual FFA-scored points**, not ESPN or other providers' predetermined fantasy-point projections. Reproduce v0 r/k/weights under the original settings, reconcile the expected 5,278 historical completed team-games, write and execute T01–T07 and T29–T40, and report mismatches. Then extend **the existing M3-3 slice** through A/B/C experiments in order, executing tests, documenting real results and decisions, and never claiming 2025 was a wholly untouched study period.

**Hard non-negotiables:** Existing FFA scoring rules and completed-game actual scores are the only fantasy-scoring truth; no external provider fantasy projected points at any point, including baseline B00, training, tuning, imputation, or fallback; own Arbit forecasts calculated from eligible actual historical results are valid; no production weight/deployment changes without approval. Do not ask for preferences already encoded by repository configuration. Ask a targeted question only if a genuinely missing decision would materially change correctness or safety; otherwise take the most conservative reproducible action, document the assumption, and continue.
