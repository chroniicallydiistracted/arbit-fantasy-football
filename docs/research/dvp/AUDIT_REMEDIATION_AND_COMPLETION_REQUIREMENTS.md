# M3-3 — Independent Audit Remediation and Completion Requirements

## Objective

Continue the existing M3-3 Defense vs. Position research implementation under OWN-074 and the original DvP Research, Build & Evaluation Specification v1.1.

An independent review has accepted the overall architecture, historical research approach, original M3-3 continuity, and provisional position-level conclusions. However, it identified remaining implementation gaps and limitations in the plan-completion audit.

Do not rebuild the research pipeline or discard the completed experiments. Correct and extend the existing implementation.

Preserve all original historical receipts, frozen configurations, experiment results, code versions, and prospective candidate declarations.

## Mandatory requirements

- Continue using the FFA Family league's canonical scoring configuration and actual fantasy points from completed NFL games.
- Never use predetermined ESPN or other provider-projected fantasy points.
- Never modify or retrospectively optimize the frozen 2026 confirmation methodology using outcomes from its evaluation window.
- Do not assign production model weights or integrate experimental factors without owner approval.
- Follow all existing repository governance, documentation, testing, and accountability requirements.

## Remediation 1 — Prospective infrastructure readiness

Priority: Immediate.

Separate prospective infrastructure readiness from future-data evaluation.

Implement an independently executable prospective shadow forecasting harness that:

- Constructs target fixtures from scheduled upcoming NFL games, without requiring actual score rows.
- Preserves the frozen B00 and D/ST B06 estimators.
- Verifies frozen method hashes and applicable configuration hashes.
- Uses only data actually available before the designated forecast cutoff.
- Captures the precise historical data snapshots and source manifests available at forecast time.
- Generates and immutably archives forecast-only artifacts before kickoff.
- Records actual forecast generation timestamps, feature cutoffs, parameters, scoring hashes, data lineage, and forecast hashes.
- Prevents overwriting or backdating previously generated forecasts.
- Separately evaluates archived predictions after completed-game FFA actuals become available.
- Preserves missing or missed forecasts honestly.
- Applies the frozen Phase B and Phase C decision rules.

Use a versioned adapter or harness outside the frozen method where feasible. Do not silently alter the frozen estimator.

Where actual FFA roster availability exists in 2026, capture it prospectively as a separate, predeclared league-constrained decision evaluation.

If a forecast cannot be generated before kickoff, record it as missed. Any subsequently reconstructed forecast must be classified as retrospective, not prospective.

## Remediation 2 — A09 and B07 opportunity/efficiency experiments

Investigate Arbit's existing opportunity infrastructure in `gamebook.py`, `team_features.py`, the point-in-time data reader, feature specifications, and nflverse field catalog.

Determine the actual historical coverage of passing attempts, dropbacks, carries, targets, receptions, kicking attempts, plays and other eligible realized statistics.

Where coverage supports it:

- Admit the realized-statistical sources through the existing projection firewall.
- Reconcile opportunity totals and scoring outputs.
- Separate volume and efficiency measurements by position.
- Measure their descriptive reliability independently.
- Construct actual-history-only forward predictors.
- Evaluate individual and combined opportunity/efficiency signals.
- Compare against B00 and existing DvP variants on common eligible samples.
- Test for duplicated information and unstable denominators.
- Document missing coverage, true zeros, invalid observations, and fallback behavior.

Retain the current non-touchdown B07 implementation as its own distinct variant.

Do not treat a source's absence from the current DvP allowlist as proof that the historical data does not exist.

Where inputs are genuinely unavailable, provide evidence of attempted retrieval, coverage evaluation and the resulting blocker.

## Remediation 3 — Recency and original estimator comparison

Expand the forecasting experiments with:

- Rolling three-game defensive residuals.
- Rolling five-game defensive residuals.
- Rolling eight-game defensive residuals.
- Appropriate shrinkage and minimum-history behavior.
- A training-only split-half-derived k variant representing the original methodology.
- Comparison against existing REML, grid-tuned, recency-weighted and cross-season-prior estimators.

Preserve the existing frozen candidates.

All additional experiments conducted after the original holdout was inspected must be versioned and classified as exploratory unless evaluated on a separate, legitimately frozen future sample.

## Remediation 4 — Strengthen data provenance enforcement

Audit and strengthen validation at ingestion, observation preparation, model fitting and forecast generation.

Verify the bytes of content-addressed source manifests and Parquet objects against their expected digests where not already enforced.

Validate permitted source categories, actual-versus-generated classifications, scoring hashes, ancestry and required row metadata.

Add contamination fixtures where prohibited or unknown source values appear inside otherwise permitted column names.

Retain all existing projection-exclusion tests.

Do not claim universal contamination resistance based solely on unknown-column rejection or code-token scanning.

## Remediation 5 — Decouple forecast targets from evaluation labels

Construct the forecast target universe independently from eventual finalized scoring-cell validity.

Keep these stages explicitly separate:

1. Scheduled targets.
2. Point-in-time feature inputs.
3. Forecast-only outputs.
4. Immutable forecast persistence.
5. Actual-outcome retrieval.
6. Evaluation joins.
7. Invalid-label and coverage reporting.

Expand tests to verify that deleting future outcomes, altering future validity flags, changing target results or introducing retroactive corrections cannot alter forecasts generated before those outcomes became available.

Preserve missing labels rather than removing their forecast targets before prediction.

## Remediation 6 — Expanded statistical simulation and robustness testing

Implement a deterministic, repeated-seed statistical simulation suite.

Include:

- Pure-noise defensive traits.
- Weak, moderate and strong known traits.
- Midseason trait changes.
- Unequal game exposure.
- Missing observations.
- Correlated game-level errors.
- Outlier outcomes.
- Multiple placebo and permutation conditions.

Measure false-positive frequency, effect recovery, estimation bias, uncertainty interval coverage, and incremental forecasting performance.

Expand T16, T17, T20, T22, T24 and related tests to cover the original specification's complete semantics.

Retain the existing deterministic regression tests.

Document the original Phase C practical threshold derivation as an approximate heuristic rather than an exact conversion from RMSE improvement. Do not retrospectively change the frozen threshold.

## Remediation 7 — Rebuild the plan-completion audit's requirement coverage

Extend `dvp_plan_audit.py` and `PLAN_COMPLETION_SCOPE.md` to distinguish:

- COMPLETE_VERIFIED
- PARTIAL
- BLOCKED_EXTERNAL
- PENDING_FUTURE_DATA
- NOT_APPLICABLE
- DEFERRED_APPROVAL
- NOT_IMPLEMENTED
- FAILED

Map each original specification requirement and sub-experiment to its actual implementation, test coverage and execution evidence.

Do not classify an experiment as complete merely because its registry status is EXECUTED or its identifier exists.

Validate expected individual variants for each position and stage, rather than only the aggregate presence of variant families.

Record which tests establish complete requirement coverage and which establish only partial coverage.

Maintain reproducible receipts, artifact hashes, rerun results, and explicit documentation of every unresolved requirement.

## Feature eligibility and downstream model governance

Preserve existing production feature calculations and original shrinkage constants.

Create or update machine-readable research eligibility metadata indicating:

- D/ST B06: promising research candidate, awaiting independent confirmation and approval.
- QB DvP: inconclusive.
- RB, WR, TE and K tested aggregate DvP methods: currently unsupported for production predictive influence.
- Opportunity/efficiency methods: exploratory, pending evaluation.

Ensure future Sit/Start model development agents cannot mistake an existing feature definition for evidence of validated predictive usefulness.

## Completion criteria

Complete all remediations that do not depend on future NFL game outcomes, unavailable historical data, or explicit owner authorization.

The prospective infrastructure must be built and tested now; future outcome evaluation remains pending until eligible games are completed.

Provide an updated completion report containing:

- Every independent audit finding and its disposition.
- Implementation changes and affected files.
- Commands and actual test results.
- New experimental findings.
- Comparisons with the original M3-3 results.
- Frozen-method integrity verification.
- Remaining legitimate blockers.
- Updated machine-readable audit receipt.
- Explicit confirmation that no provider projections or unauthorized production weight changes were introduced.

Do not describe the slice as fully complete while achievable implementation requirements remain unresolved.