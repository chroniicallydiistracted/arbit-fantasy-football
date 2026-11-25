# Arbit FFA — M3-3 Independent Audit Reconciliation, Final Remediation and Research Completion Directive

## 1. Assignment and overarching objective

Continue the existing **M3-3 — Defense vs. Position (DvP)** research workstream for the Arbit FFA Fantasy Football Sit/Start advisor.

Assume the responsibilities of:

- Senior statistical research engineer.
- Senior software and data engineer.
- Research methodology auditor.
- Data integrity and temporal-integrity auditor.
- Software quality assurance engineer.
- Project knowledge and governance maintainer.

Your assignment is to independently reconcile the external audit findings against the actual local development environment, resolve all remaining achievable implementation requirements, execute the outstanding research experiments, and complete the comprehensive M3-3 plan audit.

The overarching research question remains:

> Does Defense vs. Position contain sufficiently reliable, incremental, forward-predictive information under FFA scoring to improve Arbit's fantasy football decisions?

The objective is not to force DvP into the production model.

Negative, inconclusive, and statistically insignificant findings are legitimate research outcomes.

This assignment continues the existing implementation. Preserve accepted work and do not unnecessarily rebuild the research architecture.

---

## 2. Mandatory context acquisition

Before implementing changes, recover and reconcile the complete project and workstream context.

Review:

- Global and project-level AGENTS.md files.
- All applicable project governance requirements.
- Authoritative owner decisions, including OWN-061, OWN-074 and OWN-076.
- The original M3-3 DvP Research, Build & Evaluation Specification.
- `docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md`.
- `docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md`.
- `docs/research/dvp/PLAN_COMPLETION_SCOPE.md`.
- `docs/research/dvp/PROSPECTIVE_2026.md`.
- `docs/research/dvp/PLAYER_LEVEL_REPORT.md`.
- `docs/research/dvp/LEAGUE_CONSTRAINED_2026.md`.
- `docs/research/FFA_2026_DATA_INVENTORY.md`.
- Existing statistical research reports, experiment configurations and receipts.
- Existing plan audit implementation and receipts.
- Frozen Phase B and Phase C manifests.
- Exploratory v2 and v3 research configurations and outputs.
- The Week 12 prospective archive and ledger.
- Existing ESPN API documentation, source contracts and league-history infrastructure.
- Relevant tasks, decisions, handoffs, changelogs and unresolved issues.
- PRs #14, #15, #16 and #17.
- Any subsequent relevant commits or uncommitted local work.

The most recently independently reviewed main commit was:

`2e2520f423b0d4c1e80fca5b5a593e771ac01b2d`

Do not assume this remains the latest repository state.

Identify and reconcile changes made since that commit.

Preserve unrelated local changes and comply with existing repository governance and development procedures.

---

## 3. Independent audit reconciliation — mandatory before remediation

The external reviewer inspected the merged GitHub repository, implementation code, tests, configurations, research receipts, individual decision records, commit metadata and CI results.

However, the reviewer did not have direct access to:

- The complete local PostgreSQL database.
- All locally stored nflverse datasets.
- Raw ESPN API response bodies.
- Ignored research artifacts.
- Every historical Parquet file.
- The actual hosting environment.
- All historical execution logs.
- The complete local execution environment.

You have access to substantially more evidence.

Therefore, **you are required to critically evaluate every external audit finding rather than automatically agreeing with it or implementing its proposed correction.**

### 3.1 Required finding dispositions

For each audit finding, assign one of the following independent assessment dispositions:

| Disposition | Meaning |
|---|---|
| AGREE | The finding accurately identifies a defect, omission or methodological limitation |
| PARTIALLY_AGREE | The concern is valid, but its scope, severity, cause or proposed remediation requires qualification |
| DISAGREE | Direct evidence establishes that the finding is incorrect |
| ALREADY_RESOLVED | The issue has already been corrected and sufficient verification exists |
| NOT_APPLICABLE | The requirement does not meaningfully apply to this implementation |
| UNVERIFIED | Available evidence is insufficient to establish or reject the finding |

These are audit-assessment dispositions, not substitutes for the final implementation-completion statuses.

### 3.2 Required reconciliation evidence

For every finding, document:

1. The external reviewer's assertion.
2. The original specification requirement it relates to.
3. The actual current implementation.
4. Relevant source files and line references.
5. Relevant local data, API evidence or execution artifacts.
6. Tests or experiments used to verify the assertion.
7. Your independent assessment.
8. Your reasoning.
9. Whether remediation is required.
10. Your proposed remediation or alternative.
11. Its expected effect on existing findings.
12. Verification and completion criteria.

Create a durable human-readable reconciliation report and a machine-readable finding register within the existing research documentation structure.

Use stable identifiers so subsequent agents can trace each finding through assessment, implementation, testing and closure.

### 3.3 Rules for disagreement

You are explicitly authorized and encouraged to disagree with an external finding when evidence supports disagreement.

However:

- Do not dismiss a finding merely because existing tests pass.
- Do not dismiss a finding merely because the previous plan audit passed.
- Do not rely exclusively on your own earlier documentation or conclusions.
- Demonstrate the actual behavior through source inspection, local data examination, reproducible calculations or targeted tests.
- Distinguish evidence from interpretation.
- Identify whether an external reviewer misunderstood an implementation detail or whether the implementation genuinely satisfies the original requirement through a different route.

If an alternative remediation satisfies the original requirement more effectively than the external recommendation, implement the alternative and document the reasoning.

You do not need additional owner approval for conservative implementation decisions within the established scope.

If a disagreement would materially change the research objective, an established owner decision, frozen methodology, confirmation criteria, production behavior or a previously declared experimental scope, preserve the existing state and escalate the decision.

Do not return only a reconciliation report or another proposed implementation plan. Complete the remaining authorized work after reconciling the findings.

---

## 4. Authoritative owner decisions

The following decisions resolve the currently outstanding owner questions.

Record them through the repository's established owner-decision governance process.

### DEC-01 — Inaugural FFA season

2026 is the inaugural season of the FFA Family Fantasy Football League.

This is already established under OWN-076.

Do not:

- Investigate previous FFA seasons.
- Search for previous league identifiers.
- Request previous league identifiers from the owner.
- Attempt to retrieve pre-2026 FFA league records.
- Treat their absence as a data gap or blocker.

Continue using historical NFL statistics from 2016–2025, scored under the current FFA rules.

Pre-2026 league-constrained FFA manager evaluation is NOT_APPLICABLE.

### DEC-02 — Prospective forecast timer authorization

The owner authorizes installation and operation of the six-hourly prospective research timer for the declared 2026 Weeks 12–18 research window.

This authorization includes the necessary research-only operational safeguards, installation, verification, ingestion dependencies, archival publication, retry mechanisms, recovery mechanisms and failure reporting described below.

Do not create unrelated services.

Do not allow the service to modify production model weights, execute fantasy transactions, alter league settings or change production application behavior.

The timer must not continue indefinitely after its research responsibilities conclude.

### DEC-03 — Prospective evaluation integrity

Preserve the existing frozen B00 and B06 methods, candidate selection, thresholds and confirmation window.

The owner authorizes operational and evaluation-integrity corrections.

This does not authorize modifying the statistical methodology or optimizing the frozen candidate using observed prospective outcomes.

### DEC-04 — Comprehensive transaction versioning

Defer development of a comprehensive production-grade transaction-versioning system to a future workstream.

The absence of comprehensive version preservation must be documented as a historical limitation.

However, preserving the exact normalized league data used by M3-3 as immutable research inputs is required now.

Deferring production transaction versioning does not authorize leaving the current research experiment irreproducible.

### DEC-05 — Trade replay

Do not expand M3-3 into a full trade-management model.

The current Weeks 1–11 dataset reportedly contains no completed trades.

Nevertheless, historical ownership reconstruction must detect unsupported executed ownership-changing transactions and refuse to silently produce incorrect ownership states.

Implement complete trade replay only where the existing source contracts and available evidence support a bounded, trustworthy implementation.

Otherwise, fail closed and register complete trade replay as downstream work.

### DEC-06 — Historical availability and streaming

Continue researching realistic FFA D/ST decision sets.

Where exact historical availability cannot be established, classify the corresponding analysis as reconstructed, estimated or uncertain.

Do not treat historical unowned players as automatically claimable.

A complete competitive waiver simulator, multi-manager acquisition simulator, roster-value optimization model or long-term acquisition strategy is outside M3-3's scope.

### DEC-07 — D/ST B06 research eligibility

Retain D/ST B06 as the frozen promising historical research candidate.

The new FFA-specific league-constrained results are inconclusive.

Do not promote or reject B06 solely because of the exploratory Weeks 1–11 findings.

Do not assign production influence or modify any production model weight.

### DEC-08 — Outstanding research

Proceed with AUD-06 and AUD-07.

Both must be implemented and executed, not merely documented as future experiments.

### DEC-09 — Comprehensive completion audit

Complete remediation 7 and the research eligibility metadata before declaring the M3-3 development phase complete.

The existence of 221 audit items, 215 DONE classifications and 164 passing checks does not independently establish full compliance with the original specification or subsequent remediation requirements.

### DEC-10 — Scope control

Once the remaining achievable M3-3 requirements have been completed, stop expanding the research workstream.

Additional interesting findings may become future research leads without requiring their full implementation within M3-3.

The prospective evaluation may remain pending while other Sit/Start model slices are developed.

---

## 5. Non-negotiable research and implementation requirements

### 5.1 Scoring authority

Use the actual FFA Family scoring configuration.

Arbit's canonical model targets must be independently calculated from eligible completed-game NFL statistics under the validated FFA scoring implementation.

Use nflverse as the primary raw NFL statistical foundation.

Eligible free raw-data sources may supplement nflverse where a genuine data gap exists.

ESPN official actual fantasy points may be used for scoring reconciliation and appropriately scoped historical league analysis.

They must not silently replace Arbit's canonical scoring targets.

### 5.2 Provider projection prohibition

Never use predetermined provider:

- Projected fantasy points.
- Predicted player statistics.
- Player rankings as predictive shortcuts.
- Matchup ratings as predictive shortcuts.
- Fantasy recommendations.
- Projected values disguised as historical features.
- Projections as training labels, baselines, fallback estimates or evaluation targets.

Arbit must calculate its own forecasts.

This prohibition does not exclude legitimate ESPN actuals, historical rosters, lineups, transactions, league settings, completed-game statistics or matchup results.

Maintain and enforce the existing data provenance protections.

### 5.3 Temporal integrity

Distinguish:

- Event occurrence time.
- Source publication time.
- Source observation time.
- Ingestion time.
- Normalization time.
- Prediction cutoff.
- Forecast generation time.
- Durable archival time.
- External publication time.

A historical transaction's effective timestamp is not sufficient proof that the exact current representation of that transaction was available at the original decision cutoff.

Preserve the distinction between retrospective reconstruction and actual archived point-in-time evidence.

### 5.4 Frozen methodology

Do not overwrite or retrospectively change:

- Original M3-3 v0 evidence.
- Frozen historical forecasts.
- Frozen B00 and B06 estimators.
- Frozen Phase B and Phase C decision criteria.
- Original Week 12 forecast evidence.
- Existing prospective declarations.
- Original historical research receipts.

If a material methodological defect is discovered, preserve the original method and evidence, document the defect, and propose a separately versioned correction.

Do not silently repair a frozen estimator and continue representing the resulting predictions as the original experiment.

### 5.5 Previously accepted work

AUD-02 through AUD-05 were accepted by the previous independent remediation review, subject to their documented qualifications.

Do not reopen those experiments without new evidence of a material problem.

Preserve their results and rerun them only where necessary for regression verification, integration, reproducibility or the comprehensive audit.

---

# 6. Phase A — Complete outstanding prospective operational remediation

Priority: Immediate.

Complete this phase before undertaking expensive statistical research or other development that might jeopardize the Week 13 forecast window.

The Week 13 declared forecast window is December 1, 2026 at 12:00 UTC through December 4, 2026 at 01:15 UTC, subject to the authoritative schedule and actual data readiness.

## AUD-01a — External archival evidence

### External finding

The existing systemd service runs the prospective harness and creates a local export, but does not automatically publish or externally timestamp the forecast evidence.

The original Week 12 archive benefited from independently observable GitHub publication before kickoff.

An unattended local archive does not automatically provide the same evidence.

### Required reconciliation

Inspect the actual installed or proposed services, export implementation, publication procedures and local hosting environment.

Determine whether another existing service already provides the required external verification.

### Required remediation

Where the finding remains valid:

- Publish a cryptographic commitment to the forecast artifact, manifest and relevant evidence before the forecast cutoff.
- Prefer a dedicated research-evidence branch or another independently verifiable timestamp mechanism.
- Preserve the original forecast bytes and hashes.
- Record local archival and external publication times separately.
- Record publication attempts, results and failure reasons.
- Retry failed publication without regenerating or overwriting forecasts.
- Verify the remotely published commitment against the local archived evidence.
- Prevent publication from interfering with concurrent development or requiring automatic merges into main.

Local Git author or commit timestamps alone are insufficient proof of external publication timing.

Because the repository is public, publish only appropriately sanitized research evidence or cryptographic commitments.

Do not publish credentials, member information, private league snapshots, unnecessary account identifiers, raw provider payloads or sensitive database details.

## AUD-01b — Source ingestion and data readiness

### External finding

The prospective harness rebuilds FFA scoring targets from locally held nflverse data but does not itself establish that those files are refreshed in time for each forecast window.

### Required reconciliation

Trace the actual ingestion-to-forecast dependency chain.

Determine whether existing ingestion services already reliably provide:

- Updated NFL schedules.
- Completed-game player statistics.
- Completed-game team statistics.
- Required D/ST data.
- Canonical FFA scoring targets.
- Relevant source manifests and timestamps.

### Required remediation

Verify or implement a research-safe refresh dependency.

Readiness checks must establish eligible historical data completeness, not merely the presence of a completed game ID.

Distinguish:

- Source not yet published.
- Source published but not retrieved.
- Retrieved but invalid.
- Eligible and verified.
- Postponed, canceled or exceptional game.
- Data integrity failure.
- Forecast execution failure.

Never substitute provider projections or fabricated values for unavailable actual data.

## AUD-01c — Complete prospective evaluation window

### External finding

The previously reviewed evaluator classified a week as completed if it appeared among schedule rows with completed status.

A single completed game could satisfy that condition.

The evaluator also accepted both PROSPECTIVE and MISSED weeks when determining whether the complete confirmation window existed.

### Required remediation

Verify the current logic and correct it where necessary.

Require explicit reconciliation of:

- Every scheduled game.
- Every eligible archived forecast.
- Every required actual evaluation label.
- Missing labels.
- Invalid labels.
- Canceled and postponed games.
- Duplicate or conflicting archives.

Distinguish:

- PENDING
- INTERIM
- MISSED
- RETROSPECTIVE
- REHEARSAL
- INCOMPLETE_WINDOW
- BLOCKED
- CONFIRMED
- NOT_CONFIRMED

A missed forecast must not satisfy the full prospective-window requirement.

An incomplete window may produce descriptive findings, but must not receive the same independent-confirmation classification as a complete window.

Preserve separate Phase B and Phase C evaluation outcomes.

Apply the original frozen research criteria.

Implement direct tests of the actual completion gate, including:

- Only the first game of a week is completed.
- Multiple games remain incomplete.
- All games complete but required labels are missing.
- A forecast week is missed.
- A retrospective forecast exists for a missed week.
- The full declared window is complete and valid.
- A subset of the declared window is evaluated.
- An archived forecast fails timing or integrity verification.

Do not test only the formatting or replacement of descriptive result labels.

## AUD-01d — Archival transaction integrity

### External finding

Forecast directory creation, durable persistence, ledger updates and publication occur as separate operations.

An interrupted execution may leave partially completed archival state that cannot be recovered safely.

The recorded generation time also may not establish that durable archival completed before cutoff.

### Required remediation

Implement or verify:

- Transactional archive staging.
- Atomic publication of complete local artifacts where supported.
- Durable persistence.
- Concurrency protection.
- Archive and ledger consistency.
- Recovery of interrupted operations.
- Idempotent retries.
- Detection of conflicting or duplicated archives.
- Integrity verification of archived input objects and forecast artifacts.
- Verification that required archival operations completed before cutoff.

Test failures:

- During forecast generation.
- During temporary artifact creation.
- Before final archive creation.
- After archive creation but before ledger append.
- After ledger append but before external publication.
- During publication.
- During concurrent execution.
- During host shutdown or process termination.
- When execution crosses its forecast cutoff.

Do not regenerate an existing valid prospective archive to recover from a later publication failure.

Treat local hash chains as tamper-evidence mechanisms, not absolute guarantees of immutability.

## PB-AUD-07 — Actual prospective availability capture

### External finding

The new prospective implementation assigns free-agent and waiver status from transaction drop timestamps and a 24-/48-hour heuristic, despite Arbit already storing observed ESPN availability states in league snapshots.

Additional concerns:

- The original `freeAgents` field contains every unowned D/ST, including potentially unavailable units.
- Teams with no rostered D/ST may be absent from the prospective roster mapping.
- Claimable-only evaluation may be skipped when the free-agent pool is empty, even if a manager holds eligible units.
- Roster snapshots, waiver rules and latest transactions may be read from different observation times.

### Required reconciliation

Inspect the actual league document, normalized availability contracts, snapshot timing, provider status mappings and prospective implementation.

Determine whether directly observed availability is complete and trustworthy for all 32 D/ST units.

### Required remediation

Starting with the next prospective capture:

- Include all eight FFA teams, including teams holding zero D/ST units.
- Capture actual observed D/ST availability from the same verified league snapshot used for ownership.
- Preserve its observation time, content hash, applicable rule version and freshness relative to forecast generation.
- Distinguish OWNED, FREE_AGENT, WAIVERS and UNKNOWN.
- Validate the complete D/ST universe.
- Ensure contradictory ownership and availability states fail closed or become explicitly unavailable for the affected research evaluation.
- Use reconstructed availability only as a separately labeled fallback.
- Do not label stale reconstructed information as directly observed.
- Evaluate roster-only, unowned-pool and strictly claimable-pool experiments separately.
- Evaluate claimable-only decisions even when the free-agent pool is empty, provided eligible held units exist.
- Identify teams without any eligible decision rather than silently omitting them.

Apply individual-game lock and basic roster feasibility constraints where relevant.

Preserve the original Week 12 archive.

If actual Week 12 availability can be recovered from the original corresponding snapshot, create a separately versioned supplemental evidence record. Do not rewrite the original archive.

Keep the league-constrained evaluation descriptive and separate from frozen Phase B and Phase C confirmation.

## Timer installation and verification

After reconciling and addressing the time-sensitive operational requirements, install the authorized timer.

Verify:

- The actual hosting environment supports the chosen service mechanism.
- It remains operational across user logout and host reboot.
- Required systemd user-session and lingering behavior.
- Persistent scheduling and missed-run behavior.
- Existing ingestion dependencies.
- Correct executable and environment paths.
- Appropriate read-only database access.
- Least-privilege publication credentials.
- Execution timeouts.
- Concurrency protection.
- Retry behavior.
- Actionable alerts.
- External evidence publication.
- Manual recovery procedures.
- Automatic termination or disabling after its research responsibilities conclude.

Test the complete operational dependency chain rather than only checking that a timer is enabled.

If a host limitation prevents installation, document the specific blocker and provide a verified alternative procedure.

Do not allow the Week 13 forecast window to be missed because other research work is incomplete.

---

# 7. Phase B — Reconcile and remediate the remaining Phase B audit findings

The external reviewer accepted the overall Phase B architecture, inaugural-season clarification, ESPN infrastructure reuse, substantial historical coverage and execution of league-constrained research.

Do not rebuild those foundations.

Address the following targeted findings.

## PB-AUD-01 — Incomplete live content reconciliation

### External finding

The live transaction verification reportedly compares transaction IDs, types and statuses, but not complete normalized transaction contents.

The live scoring verification reconciles returned lineups internally but may not directly compare every live lineup entry against stored captures.

The four period-9 FUTURE_ROSTER records are explained as appearing on period 8's response, but the current audit may accept that explanation without positively locating them.

### Required reconciliation

Inspect actual local raw ESPN responses, stored captures, transaction records, receipts and existing source normalization.

Determine whether full-content comparisons were performed elsewhere.

### Required remediation

Where not already covered:

- Compare normalized transaction contents field by field or through canonical content hashes.
- Compare player identities, source and destination teams, transaction items, execution statuses, proposed timestamps and processed timestamps.
- Distinguish actual revisions from harmless provider representation differences.
- Reconcile live historical lineup entries against the stored historical captures.
- Verify starters, bench, IR, player IDs, slot assignments and actual points.
- Compare the union of relevant transaction pages.
- Positively locate and reconcile the four future-roster records or document the remaining discrepancy.
- Preserve actual retrieval scope and timestamps.
- Qualify completeness claims to reflect what was actually verified.

Use the existing guarded ESPN client and established request budgets.

Do not modify live league records.

## PB-AUD-02 — Unsupported ownership changes and effective timestamps

### External finding

The ownership replay processes executed FREEAGENT, WAIVER and ROSTER ADD/DROP events but does not implement completed trade transfers.

An executed waiver without a processed timestamp may fall back to its proposed timestamp.

The current dataset reportedly contains no completed trades, so these issues may not affect Weeks 1–11.

### Required remediation

- Verify the existing transaction contracts and observed ownership-changing event types.
- Require an appropriate effective timestamp for executed transactions.
- Never treat an executed waiver's proposal time as its processing time without explicit supporting source evidence.
- Detect unsupported executed ownership-changing transactions.
- Fail closed when reliable replay cannot be established.
- Validate draft ownership and uniqueness.
- Preserve replay inconsistencies rather than silently correcting them.
- Verify exact-cutoff replay states independently of period-end replay states.

Implement completed trade replay only when its normalized contract and execution semantics are sufficiently established.

Otherwise, register it as downstream work.

Add synthetic tests for unsupported trades, missing waiver processing times, conflicting ownership transitions, simultaneous events and later transactions.

## PB-AUD-03 — Unvalidated historical availability reconstruction

### External finding

The historical availability implementation uses:

- Less than 24 hours since drop: WAIVERS.
- Between 24 and 48 hours: WAIVERS_OR_FREE_AGENT.
- More than 48 hours: FREE_AGENT.

The actual league uses scheduled traditional waiver processing, and Tuesday is not among its recorded processing days.

Elapsed time since a drop alone may not establish immediate claimability.

Existing league snapshots contain observed availability information that could be used to validate the reconstruction.

### Required remediation

- Inspect actual acquisition settings, waiver processing days and individual-game lock rules.
- Compare reconstructed availability against directly observed availability in historical snapshots.
- Use the relevant available snapshots rather than limiting verification to ownership agreement.
- Validate the provider's normalized availability mappings.
- Preserve snapshot timing and avoid comparing different moments as if they were simultaneous.
- Identify the impact of the documented snapshot outage.
- Quantify false assumptions of immediate claimability.
- Quantify overly restrictive classifications.
- Quantify uncertain classifications.
- Determine whether the 24-/48-hour heuristic is sufficiently supported.
- Improve the reconstruction where reliable league rules and evidence permit.

Produce classification comparison tables covering observed versus reconstructed states.

Distinguish VERIFIED, RECONSTRUCTED, ESTIMATED and UNKNOWN.

Do not claim that a near-cutoff snapshot independently verifies an exact cutoff state unless intervening changes have been accounted for.

Where exact historical availability cannot be recovered, retain a conservative estimated-availability experiment and explicit uncertainty bounds.

Do not introduce an unvalidated replacement heuristic merely because it produces more favorable research results.

## PB-AUD-04 — Bootstrap treatment of zero-change weeks

### External finding

The league-constrained bootstrap reportedly constructs its resampling population from decisions where B00 and B06 differ.

This excludes weeks with evaluated decisions but zero changed recommendations.

In the original Start/Sit experiment, Weeks 7 and 8 contain zero incremental points and were omitted from the bootstrap population.

The external reviewer reported an all-week recalculation changing the interval from approximately −90 to +80 points to approximately −96 to +74.

### Required reconciliation

Independently reproduce both calculations.

Determine the correct uncertainty estimand and resampling population.

Do not assume the reviewer's approximate recalculated interval is authoritative without reproducing it.

### Required remediation

For the cumulative decision-point difference:

- Preserve every eligible evaluation week.
- Include weeks with zero changed decisions as zero incremental gain.
- Distinguish zero-change weeks from weeks with genuinely missing evaluation coverage.
- Preserve dependence among manager decisions within the same week.
- Record the number of independent resampling blocks.
- Preserve reproducible seeds and documented interval methods.

Add deterministic regression tests.

Rerun the affected uncertainty calculations.

Include this issue in AUD-06's broader uncertainty and small-sample validation.

Do not modify the frozen historical Phase B or Phase C thresholds.

## PB-AUD-05 — Streaming feasibility and shared acquisition constraints

### External finding

The streaming experiment evaluates each FFA manager independently.

In certain weeks, all eight managers receive the same recommended free-agent D/ST.

Those recommendations cannot all be executed simultaneously.

The current experiment may also omit roster capacity, the D/ST position limit and the need for an accompanying legal player drop.

### Required remediation

Preserve the independent-manager experiment.

Explicitly classify it as an independent, single-week recommendation evaluation rather than a simultaneous league-wide acquisition strategy.

Where trustworthy historical evidence supports it:

- Validate roster capacity.
- Validate position limits.
- Determine whether a legal accompanying drop exists.
- Account for locked players.
- Distinguish an immediately executable acquisition from one requiring an additional roster transaction.
- Identify unknown or unverifiable feasibility.
- Report shared recommendations and acquisition collisions.

Do not fabricate the future opportunity cost of dropping a player.

Do not represent gross D/ST point improvements as net roster-management value.

Do not build a complete competitive acquisition or multi-week waiver simulator within M3-3.

Document those as separate future workstreams.

## PB-AUD-06 — Manager comparison and matchup eligibility

### External finding

The model forecasts use a preweek decision cutoff, whereas actual manager starters come from finalized historical lineups.

FFA's individual-game locks permit later acquisitions and lineup changes.

The manager's eventual starter may therefore differ from the players available to the manager at the original prediction cutoff.

The existing decision receipt records option counts and selected units but may not preserve the exact eligible candidate set.

### Required remediation

Preserve the exact eligible decision set for every evaluated manager and week.

Record:

- Decision timestamp.
- Owned D/STs.
- Eligible playing D/STs.
- Availability state and evidence.
- Roster and position constraints.
- B00 selection.
- B06 selection.
- Actual finalized starter.
- Whether the actual starter was eligible at the model's cutoff.
- Relevant later ownership changes.
- Actual outcomes.
- Reconciliation status.

Separate strictly comparable manager decisions from those involving different decision times.

For matchup counterfactuals:

- Verify the recommended unit was eligible and could legally have been started.
- Reconcile the actual starter's points.
- Hold the opponent's actual score constant intentionally.
- Clearly classify the result as an individual-decision counterfactual.
- Handle ties, unknown scores and missing eligibility explicitly.

Do not interpret hypothetical matchup reversals as proof of increased league win probability.

## PB-AUD-08 — Immutable league inputs and reproducible Phase B audit

### External finding

The updated plan audit reruns the original historical research stages but reportedly does not independently rerun the new FFA inventory or league-constrained experiment.

Instead, its Phase B checks primarily inspect previously generated receipts, status flags and source markers.

The experimental NFL inputs are pinned, but historical league inputs are loaded from the current database at execution time.

Future transaction revisions, stat corrections or league-rule changes could alter a rerun.

### Required remediation

Preserve research-specific immutable normalized league inputs containing the minimum necessary:

- Draft ownership.
- Relevant historical transactions.
- Finalized lineup captures.
- Applicable historical rules and rule hashes.
- Relevant matchup results.
- Required archived snapshot states.
- Identity mappings.
- Observation and effective timestamps.
- Historical availability evidence.

Record artifact hashes and source ancestry.

Avoid unnecessarily retaining or publishing member identifiers and private league information.

Provide an independently reproducible research execution path that does not depend on mutable current league state.

Regenerate:

- Ownership replay.
- Availability reconstruction.
- Decision sets.
- Forecast-to-decision mappings.
- Experimental outcomes.
- Summary metrics.
- Uncertainty calculations.

Compare regenerated results against their corresponding committed research receipts.

Integrate this work into remediation 7 rather than building a redundant audit system.

Preserve the original Phase B v1 results. If corrections alter the analysis, publish a separately versioned corrected result and explain the difference.

---

## 8. Reevaluate Phase B conclusions after corrections

The external reviewer independently reconciled the following original receipt totals:

| Experiment | Decisions | Changed choices | B00 points | B06 points | B06 minus B00 |
|---|---:|---:|---:|---:|---:|
| Owned D/ST Start/Sit | 28 | 12 | 197 | 191 | −6 |
| Estimated free-agent streaming | 88 | 77 | 565 | 611 | +46 |
| Streaming including waiver units | 88 | 78 | 579 | 675 | +96 |

The receipt also reports:

- Actual managers scored 201 points in the original 28 roster-only comparisons.
- B06 would have changed two actual losses into wins and one actual win into a loss.
- Week 11 contributed +92 points to the streaming experiment.
- Excluding Week 11 as a sensitivity illustration would change the cumulative streaming difference from +46 to −46.
- All reported uncertainty intervals span zero.

Independently verify these results and their interpretations.

Do not selectively remove Week 11 from the primary experiment.

If the remediation changes eligibility or decision counts, report:

- Original sample.
- Corrected sample.
- Added or removed decisions.
- Reasons for those differences.
- Original and corrected outcomes.
- Whether any earlier conclusion changes.

The working research conclusion remains:

- D/ST B06 has promising historical group-level and unrestricted decision evidence.
- FFA-specific roster-constrained utility is inconclusive.
- FFA-specific streaming utility is inconclusive.
- Independent prospective confirmation remains pending.

Change these classifications only if the corrected evidence warrants it, with explicit reasoning.

Do not modify production weights.

---

# 9. Phase C — AUD-06 statistical simulation and robustness suite

Complete the outstanding statistical validation work using known synthetic data-generating processes.

The purpose is to determine whether the actual Arbit estimators and complete research-selection procedure behave correctly when the true underlying signal is known.

Do not limit validation to single fixed-seed fixtures.

## C1. Predeclare simulation configuration

Before executing the full suite, version and record:

- Simulation scenarios.
- Data-generating processes.
- True signal parameters.
- Sample sizes.
- Exposure distributions.
- Repetition counts.
- Random seeds.
- Estimators.
- Selection rules.
- Evaluation metrics.
- Uncertainty methods.
- Expected mathematical invariants.
- Acceptance criteria.
- Computational budget.
- Conditions for classifying an outcome as inconclusive.

Separate random streams for data generation, fitting, permutations and uncertainty estimation.

Do not modify acceptance criteria after observing results without creating a new version and documenting the rationale.

## C2. Required scenarios

At minimum, implement the following:

| ID | Scenario |
|---|---|
| SIM-01 | Pure noise with no defensive trait |
| SIM-02 | Weak known defensive signal |
| SIM-03 | Moderate known defensive signal |
| SIM-04 | Strong known defensive signal |
| SIM-05 | Abrupt midseason trait change |
| SIM-06 | Gradual defensive trait drift |
| SIM-07 | Unequal game exposure |
| SIM-08 | Randomly missing observations |
| SIM-09 | Informative, nonrandom missing observations |
| SIM-10 | Correlated within-game and within-week errors |
| SIM-11 | Heavy-tailed noise and extreme outcomes |
| SIM-12 | Unequal opponent quality and schedule difficulty |
| SIM-13 | Cross-season persistence and personnel turnover |
| SIM-14 | Separate opportunity-volume and efficiency signals |
| SIM-15 | Repeated placebo and shuffled-opponent controls |
| SIM-16 | Multiple competing null predictors and selection overfitting |
| SIM-17 | Small-sample league-constrained decision evaluation |
| SIM-18 | Zero-change weeks and shared manager-decision dependence |

Use representative NFL-like schedules and appropriate offensive-position and D/ST orientations.

Clearly distinguish idealized scenarios from deliberate assumption violations.

## C3. Repetitions and computational requirements

Use enough independent repetitions to support meaningful statistical conclusions.

As a starting point:

- At least 1,000 repetitions for inexpensive estimator-level experiments.
- Several hundred or more repetitions for computationally expensive full-pipeline experiments.
- Additional repetitions where Monte Carlo uncertainty materially affects interpretation.

Document computationally justified deviations.

Report Monte Carlo uncertainty for estimated statistical frequencies.

Do not silently reduce repetitions to achieve a favorable result or convenient completion status.

Separate fast deterministic CI tests from the expensive research execution suite.

## C4. Estimator coverage

Evaluate the applicable actual implementations of:

- Original split-half reliability.
- Spearman–Brown-derived k.
- REML variance components.
- Raw DvP.
- Opponent-adjusted DvP.
- Reliability-shrunk DvP.
- Grid-tuned shrinkage.
- Rolling three-, five- and eight-game estimators.
- Exponential recency estimators.
- B06 cross-season prior.
- B07 non-touchdown variant.
- Opportunity-volume estimator.
- Efficiency estimator.
- Combined opportunity/efficiency estimator.
- B00 no-matchup baseline.
- B09 placebo controls.

Use an oracle benchmark where meaningful: a synthetic predictor with knowledge of the true simulated parameters.

The oracle is a research reference, never an eligible production input.

Prefer exercising the actual Arbit implementations over simplified replacements that could conceal implementation defects.

## C5. Required statistical measurements

Measure and report:

- True and estimated signal variance.
- True and estimated noise variance.
- True and estimated reliability.
- True and estimated k where identifiable.
- Estimation bias.
- Estimation variance.
- Mean squared estimation error.
- False-positive frequency.
- Detection power.
- Interval coverage.
- Interval width.
- Boundary behavior.
- Convergence behavior.
- Forecast RMSE.
- Forecast MAE.
- Incremental predictive improvement.
- Correct rejection frequency.
- Correct candidate recovery frequency.
- False promotion frequency.
- Sensitivity to sample size.
- Sensitivity to correlated errors and assumption violations.

Under a pure-noise scenario, the true persistent-signal variance is zero and k may be effectively infinite.

Do not impose an arbitrary finite value merely to simplify reporting.

Distinguish an estimator identifying nonzero variance from a complete research procedure incorrectly promoting a predictor.

## C6. Full research procedure validation

This requirement is mandatory.

Evaluate the complete development, estimator-selection, validation and evaluation procedure.

Under simulated null scenarios, measure how often the complete procedure incorrectly identifies a promising candidate.

Under simulated signal scenarios, measure how often it:

- Detects useful signal.
- Selects an appropriate estimator.
- Passes its intended validation gates.
- Rejects a genuinely useful signal.
- Overestimates predictive importance.
- Selects an estimator because of sampling noise.

Account for multiple positions, estimator families, shrinkage configurations and competing predictors.

Do not confuse individual statistical significance with practical research promotion criteria.

## C7. Uncertainty validation

Assess the suitability of existing bootstrap methods under:

- Independent observations.
- Defense-season clustering.
- Season-level clustering.
- Week-level clustering.
- Shared-game dependence.
- Shared manager decisions.
- Temporal dependence.
- Unequal exposure.
- Small numbers of independent blocks.
- Zero-change evaluation periods.
- Missing decision outcomes.

Evaluate whether nominal 95% intervals achieve approximately their intended coverage under the assumptions for which they were designed.

Where assumptions are deliberately violated, report the resulting limitations.

Distinguish:

- Software defects.
- Mathematical limitations.
- Statistical model assumptions.
- Insufficient sample size.
- Configuration issues.
- Invalid interpretation.

Do not automatically treat every unfavorable simulation result as an implementation defect.

## C8. Verification and deliverables

Produce:

- Versioned simulation configuration.
- Scenario definitions.
- Executable simulation framework.
- Machine-readable results.
- Estimator comparison tables.
- False-positive and power analysis.
- Confidence-interval coverage analysis.
- Selection-procedure analysis.
- Robustness plots.
- Reproduction commands.
- Statistical interpretation.
- Regression and reproducibility tests.
- Documented limitations.
- Position-specific implications where relevant.

State whether AUD-06 changes any earlier M3-3 conclusions.

Preserve frozen prospective methodology even if simulations reveal limitations.

Material methodological defects must be explicitly recorded and escalated rather than silently changing the ongoing frozen experiment.

---

# 10. Phase D — AUD-07 threshold interpretation and sensitivity

Preserve the existing frozen research thresholds:

- Phase B: minimum 1% relative RMSE improvement.
- Phase C: minimum 1.8 percentage-point improvement in pairwise decision accuracy.
- Phase C: positive net fantasy-point gain, as defined by the frozen rule.

## D1. Correct the mathematical interpretation

The external reviewer identified that the original documentation describes the 1.8-percentage-point threshold as though it were an exact mathematical consequence of the 1% RMSE threshold.

The derivation reportedly uses a theoretical relationship under bivariate normal assumptions and B00's development Spearman correlation.

Independently inspect and reproduce the original derivation.

Explain:

- The relationship originally used.
- Its distributional assumptions.
- Pearson versus Spearman correlation.
- Forecast calibration and bias.
- Why a given RMSE improvement does not uniquely determine pairwise ranking improvement.
- Why the frozen threshold is better interpreted as a predeclared practical heuristic.

Do not retrospectively alter the frozen threshold.

If the original calculation differs from the external reviewer's understanding, provide the exact derivation and supporting evidence.

## D2. Exploratory threshold sensitivity

Create a separately versioned descriptive sensitivity analysis.

Suggested Phase B relative RMSE thresholds:

- 0%.
- 0.25%.
- 0.5%.
- 1%.
- 1.5%.
- 2%.
- 3%.

Suggested Phase C pairwise accuracy thresholds:

- 0 percentage points.
- 0.5 percentage points.
- 1 percentage point.
- 1.8 percentage points.
- 2 percentage points.
- 3 percentage points.
- 5 percentage points.

Evaluate classifications alongside:

- Consistency across periods.
- Statistical uncertainty.
- Net actual points.
- Decision coverage.
- Decision regret.
- The interaction between Phase B and Phase C requirements.

Do not present the suggested grid as an empirically optimal decision rule.

Do not use the resulting analysis to select a more favorable threshold for the already-frozen 2026 confirmation.

## D3. Required conclusion

Document:

- Which findings are robust to reasonable threshold variation.
- Which findings are sensitive to the selected thresholds.
- Whether D/ST B06's historical classification remains supported.
- Whether any other position's classification requires additional qualification.
- Implications for research governance in future Arbit model slices.

---

# 11. Phase E — Research eligibility and downstream model governance

Create or extend the existing machine-readable research eligibility registry.

Inspect the existing feature registry and governance architecture before deciding the implementation route.

Avoid redundant registries.

The registry must prevent subsequent agents from confusing:

- A feature's existence with its predictive validity.
- Historical reliability with forward-predictive value.
- Research eligibility with production eligibility.
- Prospective confirmation with integrated-model utility.

Record:

- Feature and workstream identifiers.
- Position.
- Estimator and version.
- Definition.
- Eligible sources.
- Scoring configuration.
- Historical reliability evidence.
- Forward-prediction evidence.
- Unrestricted decision evidence.
- Actual FFA league-constrained evidence.
- Simulation findings.
- Prospective confirmation status.
- Research classification.
- Production eligibility.
- Required approvals.
- Known limitations.
- Reconsideration requirements.
- Evidence references.
- Last evaluation date.

Required initial classifications:

| Feature | Research disposition |
|---|---|
| D/ST B06 | PROMISING historical candidate |
| D/ST FFA league-constrained utility | INCONCLUSIVE, subject to corrected evidence |
| QB aggregate DvP | INCONCLUSIVE |
| RB aggregate DvP | Tested methods unsupported |
| WR aggregate DvP | Tested methods unsupported |
| TE aggregate DvP | Tested methods unsupported |
| K aggregate DvP | Tested methods unsupported |
| K opportunity volume | Exploratory future research lead |
| Other opportunity/efficiency variants | Exploratory |
| Legacy DvP features | Existing definitions do not establish predictive eligibility |

Apply fail-closed eligibility validation at the appropriate model assembly or governance boundary.

Do not activate an experimental feature or modify existing production predictive behavior.

Preserve existing legacy calculations and shrinkage constants unless a separately authorized task changes them.

Even if B06 is prospectively confirmed, it must later demonstrate incremental contribution against the integrated Sit/Start model containing other predictive slices.

---

# 12. Phase F — Complete remediation 7: comprehensive plan-completion audit

This is the final development gate.

Extend the existing audit rather than creating an unrelated replacement.

## F1. Complete requirement inventory

Reconcile every applicable requirement from:

- Original M3-3 specification.
- Original AUD-01 through AUD-07.
- AUD-01a through AUD-01d.
- Phase B requirements B0 through B8.
- PB-AUD-01 through PB-AUD-08.
- Authoritative owner decisions.
- Research eligibility requirements.
- Subsequent accepted implementation decisions.

Preserve original requirement identifiers where feasible.

Introduce stable subrequirement identifiers for previously aggregated requirements.

Do not silently remove inconvenient requirements from the inventory.

## F2. Completion statuses

Replace or extend the coarse DONE/OPEN classifications with:

| Status | Meaning |
|---|---|
| COMPLETE_VERIFIED | Fully implemented, executed and supported by appropriate evidence |
| PARTIAL | Some functionality exists but required work remains |
| BLOCKED_EXTERNAL | A genuine external dependency prevents completion |
| PENDING_FUTURE_DATA | Infrastructure exists, but required future observations do not |
| NOT_APPLICABLE | The requirement has no meaningful application |
| DEFERRED_APPROVAL | Intentionally awaiting required owner approval |
| NOT_IMPLEMENTED | Achievable functionality has not been built |
| FAILED | Implementation or verification failed |

Distinguish research experiment outcomes from implementation-completion classifications.

An executed experiment returning NOT_USEFUL may be COMPLETE_VERIFIED.

A missing implementation cannot be classified as BLOCKED_EXTERNAL merely because it has not been developed.

Reassess the previous open items:

- C03: route, slot and target-share interactions are not applicable to the currently eligible D/ST-only Phase C research.
- C05L-HIST: NOT_APPLICABLE under OWN-076.
- C05L-2026-EXP: complete only after the applicable Phase B corrections are resolved and verified.
- C05L-2026-PRO: future evaluation remains pending, while its collection infrastructure must be operational now.
- P4P: separate infrastructure readiness from future outcomes.
- P5W: DEFERRED_APPROVAL.
- G06: explicitly establish whether dry-run and resume modes are appropriate and required under the original specification; document the reasoning.

## F3. Semantic requirement verification

Do not mark a requirement complete solely because:

- A source file exists.
- An experiment identifier exists.
- A registry reports EXECUTED.
- A test contains the requirement identifier.
- A previously generated receipt reports success.
- CI passed.
- A documentation marker appears in source code.

Verify actual:

- Implementation behavior.
- Mathematical definitions.
- Applicable positions.
- Estimator variants.
- Experimental stages.
- Data coverage.
- Source eligibility.
- Temporal constraints.
- Test assertions.
- Decision-set eligibility.
- Output schemas.
- Execution evidence.
- Reproducibility.
- Known limitations.

Require direct evidence for each independently meaningful subrequirement.

## F4. Reproduction

Rerun all feasible relevant stages using the appropriate immutable source snapshots.

Include:

- Original M3-3 reproduction.
- Historical reliability analysis.
- Development forecasting.
- Validation forecasting.
- Conditional holdout evaluation.
- Original Phase C evaluation.
- Exploratory v2 and v3 experiments.
- FFA 2026 inventory and normalized input verification.
- Ownership reconstruction.
- Availability reconstruction.
- Corrected league-constrained evaluation.
- Statistical simulations.
- Threshold sensitivity.
- Prospective archival verification.
- Research eligibility validation.

Do not require a mutable live ESPN response to be byte-identical to an earlier historical response when legitimate corrections or new events have occurred.

Separate:

- Reproduction of pinned historical inputs.
- Current-source coverage verification.
- Expected source revisions.
- Unexplained discrepancies.

Preserve original outputs.

Never overwrite a previous receipt merely to make a reproduction check pass.

## F5. Audit self-validation

Add negative controls proving that the audit detects incomplete or incorrect implementation.

At minimum, test:

- Missing required estimator variant.
- Missing position or experimental stage.
- Required experiment not executed.
- Required test skipped.
- Stale receipt.
- Modified frozen artifact.
- Prohibited provider projection dependency.
- Incorrect source lineage.
- Incorrect historical ownership.
- Incorrect availability classification.
- Ineligible decision option.
- Zero-change weeks omitted from the intended bootstrap population.
- Missing normalized league input artifact.
- Incorrect prospective week completion.
- Missed forecast incorrectly classified as prospective.
- Unsupported ownership-changing transaction.
- Blocked requirement without evidence.
- Research factor improperly marked production-eligible.

Demonstrate that passing the audit requires actual compliance, not merely internally consistent positive flags.

## F6. Final receipt

Generate a fresh machine-readable audit receipt containing:

- Specification versions and hashes.
- Audited commit.
- Requirement inventory version.
- Independent finding reconciliation dispositions.
- Implementation-completion statuses.
- Data snapshot identifiers.
- Artifact hashes.
- Frozen-method verification.
- Experiment outcomes.
- Test execution outcomes.
- Reproduction results.
- Audit negative-control results.
- Remaining blockers.
- Pending future-data requirements.
- Deferred owner approvals.
- Overall development-completion assessment.

Do not reuse the previous 221-item inventory or its completion percentage without reconciliation.

---

# 13. Required implementation and research verification

Follow the project's established testing and governance procedures.

Execute all applicable:

- Unit tests.
- Integration tests.
- Data-contract tests.
- Point-in-time tests.
- Mathematical regression tests.
- Property-based tests where appropriate.
- Statistical simulation experiments.
- Research reproducibility tests.
- Prospective operational tests.
- Archive recovery tests.
- Audit self-validation tests.
- Foundation validation.
- Runtime validation.
- Context governance validation.
- Formatting and linting.
- Type checking.
- Applicable full Python test suites.

Distinguish:

- Tests executed in CI.
- Tests executed locally.
- Research experiments executed separately.
- Tests requiring real historical data.
- Synthetic verification.
- Skipped or blocked verification.

Report actual commands, results, failures, skips and execution scope.

Do not claim that passing CI establishes successful execution of expensive research experiments unless CI actually executed them.

Use established branch, commit, review, merge and governance processes.

Verify the final merged main state and applicable CI results.

---

# 14. Persistent knowledge and accountability

Throughout execution, maintain the repository's authoritative knowledge system.

Record:

- Original objective.
- Current task scope.
- Audit finding reconciliation.
- Decisions and their reasoning.
- Owner authorizations.
- Assumptions.
- Alternatives considered.
- Implementation changes.
- Mathematical methodologies.
- Data provenance.
- Temporal-integrity limitations.
- Tests and their results.
- Research outputs.
- Unexpected findings.
- Reproduction instructions.
- Outstanding issues.
- Deferred work.
- Future-data dependencies.
- Changelog.
- Handoffs.

After every meaningful analytical or development step, establish:

1. What was found or implemented.
2. How it was verified.
3. How it relates to previous findings.
4. Whether any earlier conclusion changed.
5. What it contributes to the original M3-3 objective.
6. What remains unresolved.

Maintain sufficient context for a fresh agent to resume the work without requiring the owner to reconstruct its history.

---

# 15. Required execution order

Proceed in the following order, adjusting only where evidence establishes a dependency or urgency requiring a different sequence.

1. Recover and reconcile current repository and local development context.
2. Independently assess the external audit findings.
3. Resolve AUD-01a through AUD-01d.
4. Resolve PB-AUD-07.
5. Install and verify the authorized prospective timer.
6. Resolve PB-AUD-01 through PB-AUD-06.
7. Preserve pinned Phase B research inputs and correct the affected league-constrained experiments.
8. Implement and execute AUD-06.
9. Complete AUD-07.
10. Implement research eligibility metadata and appropriate safeguards.
11. Resolve PB-AUD-08 through the comprehensive remediation 7 audit.
12. Execute final verification and reproduction.
13. Complete the governed repository merge and verify main.
14. Produce the final completion report and durable handoff.

The upcoming prospective forecast windows take priority over non-time-sensitive research work.

Do not wait for the entire M3-3 development phase to finish before securing prospective collection.

---

# 16. Final completion report

Provide a comprehensive final report with the following sections.

## 16.1 Executive conclusion

State whether all currently achievable development and research requirements have been completed.

Separate:

- Development completion.
- Historical research completion.
- Prospective infrastructure readiness.
- Independent prospective confirmation.
- Production eligibility.

## 16.2 Independent audit reconciliation

For every external audit finding, report:

- Finding ID.
- Agreement or disagreement disposition.
- Evidence.
- Reasoning.
- Remediation.
- Verification.
- Final completion status.

Explicitly identify findings where you disagreed with the external reviewer and explain why.

## 16.3 Owner decisions

Confirm the disposition of every owner decision established by this directive.

Identify any genuinely unresolved new owner decisions.

Do not ask the owner again about matters already resolved here.

## 16.4 Prospective operations

Provide evidence of:

- Timer installation.
- Service configuration.
- Host persistence.
- Data readiness.
- Archive integrity.
- External publication.
- Retry and recovery behavior.
- Completion-gate verification.
- Future scheduled research responsibilities.

## 16.5 Corrected Phase B research

Report:

- Verified data coverage.
- Live-versus-stored reconciliation.
- Ownership replay findings.
- Availability validation findings.
- Corrected decision eligibility.
- Original and corrected sample sizes.
- Original and corrected experimental outcomes.
- Uncertainty.
- Changes to earlier conclusions.
- Remaining historical limitations.

## 16.6 AUD-06 findings

Explain:

- Simulation design.
- Known underlying signals.
- Estimator recovery.
- False-positive behavior.
- Candidate-selection reliability.
- Uncertainty coverage.
- Robustness.
- Discovered defects or limitations.
- Implications for M3-3 and subsequent model slices.

## 16.7 AUD-07 findings

Explain:

- Original threshold derivation.
- Corrected interpretation.
- Sensitivity results.
- Robustness of existing classifications.
- Implications for future research governance.

## 16.8 Final audit

Provide:

- Comprehensive requirement inventory.
- Completion classifications.
- Fresh audit receipt.
- Audit self-validation results.
- Test results.
- Reproduction evidence.
- Remaining blockers.
- Pending future-data requirements.
- Deferred owner approvals.

## 16.9 Repository delivery

Provide:

- Relevant PRs.
- Commit identifiers.
- Merge status.
- Main branch state.
- CI results.
- Important file locations.
- Reproduction instructions.
- Final handoff location.

---

# 17. Definition of done

M3-3's development phase may be classified as complete only when:

- Every external audit finding has been independently reconciled.
- Every currently achievable mandatory remediation has been implemented and verified.
- Any rejected audit finding has an evidence-supported explanation.
- Outstanding statistical experiments have actually been executed.
- Corrected Phase B findings are reproducible from pinned research inputs.
- Prospective collection infrastructure is operational and verified.
- The forecast timer is installed or a genuine blocker and verified alternative are documented.
- Frozen methodology and original prospective evidence remain intact.
- Research eligibility metadata prevents unsupported activation.
- The comprehensive plan audit covers the actual final implementation.
- Audit negative controls demonstrate meaningful failure detection.
- No prohibited provider projection dependencies exist.
- No unauthorized production changes have occurred.
- Remaining incomplete requirements are genuinely external blockers, future-data dependencies, not applicable, or awaiting owner approval.
- The persistent knowledge base provides a complete, reproducible handoff.

Do not classify M3-3 as production-ready merely because its development phase is complete.

Do not classify independent 2026 confirmation as complete before the required eligible games, archived forecasts and evaluation outcomes exist.

Do not unnecessarily keep M3-3's development phase open solely because those future games have not occurred.

Begin by recovering the current project state, creating the independent audit reconciliation register, and verifying the time-sensitive prospective requirements. Then carry out the authorized implementation, statistical research, verification and completion work.