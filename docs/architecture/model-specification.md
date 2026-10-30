# Arbit Model and Analytical Validation

Version 0.1 · 2026-10-30 · Proposed methodology, no trained model or measured performance yet.

## Shared analytical contract

Arbit Model owns point-in-time statistical features, player evaluation distributions, rankings, archetypes and common roster value. Advisors apply decision-specific constraints to those same outputs. Input: canonical player/defense entity, season and prediction horizon, observation cutoff, dataset manifest, validated FFA rules, league snapshot, and model policy version. Output: projected stat distribution, exact-rule fantasy distribution, expected value, quantiles, position-relative value, evidence contributions, sample/coverage diagnostics and provenance.

One evaluation horizon is never silently compared with another: weekly points, draft-season value, and rest-of-season value have distinct semantics. Fantasy scoring is a core service, not reimplemented in models or UI. Model output missingness is explicit and advice can abstain. A confidence label identifies evidence quality; a calibrated probability is a different quantity and needs its own validation.

## Data and feature methodology

Use nflverse as the primary source. Begin with interpretable volume × efficiency decomposition, shrinkage, and uncertainty; add ML only when evaluation supports it. Features cover historical and current production; attempts/targets/snaps/air yards/red-zone work; efficiency and EPA/success where appropriate; team pace/pass tendency; opponent context and positional defense; opportunity stability, depth/injury context if covered, recent weighted trends, schedule and byes. Feature inclusion follows a publication-time coverage inventory. Advanced historical participation cannot be treated as an available in-season input merely because it appears in the final data file.

Position-specific models separate QB rushing/passing, RB rushing/receiving, WR/TE targets/efficiency, kickers and team defense when FFA settings use them. Partial-game injury and DNP labels need explicit treatment; do not drop poor outcomes selectively. New players use position/role priors and wider intervals. Opponent strength estimates shrink small samples. Environmental effects and news enter only with sourced, historically observable features and measurable benefit.

Define each feature's name, unit, grain, denominator, window, minimum sample, missing indicator, cutoff eligibility, transformation version and provenance. Model artifacts pin training rows, feature definitions, code revision, seed, dependency lock hash, rule hash and evaluation configuration. Preserve source revisions for reproduction. Scoring nonlinear bonuses over simulated stat lines is essential; applying bonus rules to average yards produces biased expectations.

## Baselines and evaluation design

- Baseline A: trailing weighted player opportunity/efficiency with position/role shrinkage and configured FFA scoring.
- Baseline B: previous-season or positional replacement baseline appropriate to cold starts.
- Optional comparison: labeled ESPN or other public projections for benchmarking, never the primary statistical foundation.

Use rolling-origin season/week splits. Reserve the latest complete eligible season as final holdout where sufficient history exists, with earlier seasons for development; choose exact seasons only after dataset coverage audit. Respect the actual information availability time, embargo late corrections and fit preprocessing within each training fold. Hyperparameter tuning never touches the final holdout. Evaluate regular/postseason separately if their populations differ.

Report by position, role, sample size, injury/rookie subgroup and week: MAE/RMSE of points/stat components; rank correlation and top-k regret; quantile loss and 50%/80% interval coverage; reliability and Brier score for explicitly modeled events. Weekly matchup simulations also need a held-out calibration/reliability report and a defined dependency structure among teammates/opponents. Include uncertainty in estimated improvement using block bootstrap by week/season, not independent player rows that ignore shared games.

Proposed first release gate: all lineage/leakage checks pass; aggregate point MAE no worse than baseline A on the untouched holdout; any position >5% worse than its baseline stays on baseline A; reported 80% interval coverage between 75% and 85% for groups with at least 100 holdout observations. Smaller groups are labeled insufficiently validated. These are proposed policies, not research findings or achieved performance; amend in an ADR before evaluating a candidate, never tune the gate after seeing results. Baselines themselves can be released with clear status if they satisfy correctness and coverage checks. Retain a prior validated release for rollback.

## Advisor policies

### Lineup

Solve a constrained assignment over every eligible roster slot: maximize sum of expected points for the default objective, with unique-player assignment, mandatory locks, inactive/bye restrictions and actual FFA slot rules. Verify small cases by exhaustive search. For a matchup objective, simulate joint fantasy outcomes against the actual opponent roster, including transparent assumptions about unconfirmed opposing starters. Same-game correlations need an explicit fitted/shrunk model or a labeled independence assumption; no hidden precision. Report lineup alternatives, expected gain, uncertainty and decision sensitivity, not just a best label.

### Waivers

Value a legal add/drop as the team's optimized roster utility after versus before, including the replacement player, positional depth, upcoming byes and the selected horizon. Recheck actual ownership/waiver status. FAAB guidance requires FFA's real budget and transaction context; no inferred budget. Rank by expected useful roster gain, with uncertainty and opportunity evidence; a high projected scorer already covered by stronger starters may have little roster-specific benefit.

### Trades

Evaluate both complete post-trade rosters with required drops, eligibility, locks/deadlines and rest-of-season schedule. Derive package value from shared distributions and team opportunity cost; cannot add per-player ratings across incompatible scales. Enumerate bounded one-for-one and multi-player candidate packages, prune dominated or illegal packages, expose horizon and utility changes for both teams. Feasibility starts as a qualitative, explained rules/needs assessment. A numerical acceptance model requires recorded genuine proposals/outcomes and enough labels for held-out calibration; inaugural FFA history cannot support invented learned acceptance likelihoods. No messages or proposals are submitted automatically.

### Draft

Track all picks, current roster/needs, scoring and remaining eligible players. Optimize marginal roster value with scarcity, expected next-pick availability, byes and plausible opponent strategies. Run seeded simulations across scenario policies and ADP priors if an appropriate supplementary ADP source is approved. If none is available, use transparent model-ranking-based simulated selection, label it scenario behavior, and do not call it observed FFA draft probability. Historical NFL training data does not equal FFA drafting history. Backtest with held-out drafts when available and measure availability calibration. Full-draft simulations and roster-construction strategies remain required, even if initial data integration uses manual draft-state fixtures.

### Archetypes and comparisons

Begin with versioned interpretable statistical descriptors (for example high-volume receiving role) with declared thresholds, position-specific scaling and minimum sample. If clustering is introduced, fit on training data, measure stability across seeds/seasons, inspect feature contributions and map clusters to understandable labels. Archetypes can overlap and expire with role change; low evidence yields unclassified. Classifications explain measured role/tendency, not character or certainty. They are reused in Scout, recommendations and draft analysis.

## Monitoring and release records

Track missing features, source lag, rule/mapping changes, distribution drift, subgroup errors and calibration after each settled week. Drift prompts diagnosis and fallback, not blind retraining. Model run status: experimental, baseline, validated, retired. Every release report records data cutoff, holdout policy, metrics and sample counts, baseline comparison, limitations, approval/adoption record and rollback artifact. Explanations reference measured contributions and counterfactual sensitivity; any LLM narration must be constrained to those facts and is optional.
