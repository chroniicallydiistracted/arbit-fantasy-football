## 6. Phase B — FFA historical data coverage and league-constrained evaluation

### B0. Authoritative owner clarification

The owner has confirmed that **2026 is the inaugural season of the FFA Family Fantasy Football League.**

This is an authoritative project fact, not an assumption requiring investigation.

- Do not investigate previous FFA league seasons.
- Do not search for previous league identifiers.
- Do not attempt to retrieve pre-2026 FFA league records.
- Do not request historical league IDs from the owner.
- Do not classify the absence of pre-2026 FFA records as a data retrieval failure or external blocker.

Actual FFA league history begins in 2026.

This does not restrict the use of historical NFL statistics from 2016–2025 or the application of the current FFA scoring configuration to those historical NFL performances.

Record this clarification in the project's authoritative owner decisions, data-source documentation, persistent knowledge base, and research audit.

### B1. Eligible ESPN data capabilities

The owner has confirmed that Arbit should leverage the eligible historical information available through its existing ESPN API integration.

This includes:

- Previous weekly starting lineups.
- Previous weekly bench lineups.
- Historical team rosters.
- Individual weekly actual fantasy points.
- Individual weekly realized NFL statistics.
- Historical matchup results.
- League schedules.
- Completed trades.
- Free-agent acquisitions.
- Player drops.
- Successful waiver claims.

All historical FFA league coverage investigations must be restricted to the 2026 season and subsequent seasons as they occur.

The prohibition against provider projections does not prohibit legitimate ESPN actuals or league-management information.

Continue using nflverse as the primary raw NFL statistical foundation and Arbit's canonical FFA scoring implementation as the authoritative source of model scoring targets.

### B2. Inspect and reuse existing infrastructure

Inspect:

- `docs/research/espn-public-api-audit-2026-10-30.md`
- `docs/research/espn-endpoint-coverage-2026-10-30.md`
- Existing machine-readable ESPN API audit evidence.
- `libs/arbit-data/src/arbit_data/espn/`
- `libs/arbit-data/src/arbit_data/league_history.py`
- Existing league snapshot and normalization infrastructure.
- Historical lineup capture and reconciliation.
- Transaction retrieval and persistence.
- Existing worker synchronization processes.
- Provider identity mappings.
- Point-in-time dataset infrastructure.

Reuse established functionality.

Do not implement a redundant ESPN client or unnecessarily duplicate existing ingestion systems.

### B3. Verify 2026 data coverage

Create a machine-readable and human-readable inventory of the available 2026 FFA datasets.

For each relevant data category, establish:

- Endpoint and retrieval implementation.
- Verified API response coverage.
- Available completed scoring periods.
- Existing ingestion and persistence status.
- Missing records and whether they can be retrieved.
- Completeness and reconciliation status.
- Historical and point-in-time limitations.
- Eligibility as predictive inputs, evaluation labels, decision constraints, or reconciliation evidence.

Where appropriate, retrieve missing completed 2026 periods through the existing guarded ESPN integration.

Do not treat HTTP 200 alone as evidence of complete data retrieval.

Respect existing request budgets, source contracts, credential handling, and read-only research requirements.

### B4. Historical data validation

For lineups and rosters:

- Validate season and scoring-period identity.
- Distinguish starters, bench, IR and flex eligibility.
- Distinguish finalized historical lineups from archived pregame lineups.
- Reconcile actual fantasy points against completed league matchup results.
- Account for stat corrections and unsupported matchup structures.

For individual player statistics:

- Distinguish weekly actuals, cumulative actuals and projections.
- Validate source and split identifiers.
- Exclude projected or ambiguous statistics from predictive inputs.
- Preserve Arbit's canonical scoring authority.

For transactions:

- Distinguish completed trades from proposals, declines and vetoes.
- Distinguish successful waiver claims from failed or unresolved claims.
- Validate execution status, ownership changes, acquisitions and drops.
- Preserve proposed, processed and observed timestamps where available.
- Deduplicate repeated records.
- Assess whether transaction revisions require version-preserved historical storage.

Do not assume that a record retrieved today represents exactly what was known at an earlier decision cutoff.

### B5. Historical ownership and availability reconstruction

Investigate whether realistic 2026 historical decision sets can be established using:

- Archived roster snapshots.
- Historical weekly lineups.
- Draft results.
- Completed transactions.
- Free-agent acquisitions and drops.
- Successful waiver claims.
- FFA roster, waiver and individual-game lock rules.

The existing ESPN reader explicitly warns that current ownership may be returned even when a historical scoring period is requested.

Never use current ownership as evidence of historical ownership.

Distinguish verified historical ownership, reconstructed ownership, verified availability, reconstructed availability and unknown availability.

Do not assume every unowned player was immediately claimable.

### B6. Reassess C05L — League-constrained Sit/Start evaluation

Split the original C05L requirement into appropriately scoped subrequirements.

**C05L-HIST — Pre-2026 historical FFA evaluation**

Disposition: `NOT_APPLICABLE`.

The FFA league did not exist during the 2016–2025 historical NFL research window.

Retain the existing unrestricted historical D/ST pairwise evaluation as a legitimate research method for those seasons.

**C05L-2026-EXP — Completed 2026 historical evaluation**

Investigate and execute an exploratory league-constrained D/ST evaluation wherever eligible 2026 historical records support it.

Compare B00 and B06 using identical, realistically available decision sets.

Evaluate:

- Roster-constrained Start/Sit decisions.
- Free-agent streaming decisions, separately.
- Actual fantasy points gained or lost.
- Changed recommendations.
- Decision accuracy.
- Decision regret.
- Actionable choice coverage.
- Historical matchup-result implications, where valid.

Where transaction timing and availability cannot be reconstructed reliably, limit the analysis to supported decision sets and explicitly document the limitation.

Weeks 1–11 were already observed before the prospective freeze. Results from those weeks must remain exploratory and must not be classified as independent prospective confirmation.

**C05L-2026-PRO — Prospective league-constrained evaluation**

Preserve and continue the existing prospective league-constrained evaluation for Weeks 12–18.

Capture actual decision-time roster and availability information.

Maintain its separately declared descriptive classification.

Do not alter frozen Phase B or Phase C confirmation rules based on exploratory league-constrained results.

### B7. Deliverables

Provide:

- A verified ESPN data capability inventory.
- A 2026 season and scoring-period coverage matrix.
- Data eligibility and temporal-integrity classifications.
- A report of existing and newly retrieved historical records.
- Results of achievable exploratory league-constrained experiments.
- Updated C05L subrequirement dispositions.
- Evidence of any genuine remaining retrieval or reconstruction limitations.
- Persistent documentation supporting subsequent Arbit model slices.

Where additional ESPN historical information could support future waiver, trade, roster-management or player-level research, document those capabilities as downstream work items.

Do not unnecessarily expand M3-3 into implementation of those future model slices.

### B8. Completion requirements

This phase is complete when the existing ESPN capabilities and completed 2026 historical coverage have been verified, all achievable M3-3-specific league-constrained experiments have been executed, and remaining limitations are accurately documented.

The absence of pre-2026 FFA league history must never prevent M3-3 development completion.

No provider projections, unauthorized production migrations, live roster changes, transactions, league-setting changes, or production weight modifications are permitted.