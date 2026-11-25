# M3-3 DvP: plan completion scope and audit

This audit holds every action item of the owner's [DvP specification v1.1](Arbit_FFA_M3_DvP_Plan.md) (OWN-074) against the work in this repository. For each item it gives:
- the status;
- the code and model logic that carries it out;
- the audit check that proves it, with what the check observed.

TASK-20261124-005, 2026-11-24. Rebuilt 2026-11-25 in TASK-20261124-009, after the owner's Phase B audit: C05L is split three ways and the Phase B items are added.

**Result: PASSED.**
- The specification and the owner's Phase B requirements break into **221 action items**:
  - 215 are done;
  - 5 are open, each for a reason this document states;
  - 1 is not applicable: C05L-HIST, because FFA began in 2026 (OWN-076).
- **164 checks** prove them, and every check passed.
- The model suite passed with no failures and nothing skipped: 213 tests, including every one of T01–T40.
- Machine-readable receipt: [plan-audit-receipt.json](plan-audit-receipt.json).
  - It was written by `scripts/model/dvp_plan_audit.py` at commit `1b99375`; the stages reran at `3848cad`.
  - It holds the SHA-256 of the specification it audited (`240a538c…`).

**What "proof" means here:**
- **Reruns, not recited receipts.** Every stage was rerun from scratch copies of the committed audit run and receipts:
  - the audit, the v0 reproduction, the reliability lab, development and 2024 validation, Phase C, verify, report and registry, all from this tree;
  - the 2025 holdout from the frozen commit's tree.
- **Field-by-field comparison.** Each rerun was compared field by field with its committed receipt. The only fields allowed to differ are the run time, the code commit, the run ID and the byte hashes of Parquet files. Fields added to receipts after the original runs were also allowed. The audit fails on any other difference.
- **Untouched evidence.** The committed audit run and `config/dvp` were hashed before and after the reruns, and nothing in them changed.

**Not proved here, because the specification leaves it open:**
- the prospective 2026 confirmation;
- the owner's decision on a D/ST production weight.

The [open items](#open-items) section lists all five.

## How to read the tables

| Column | Meaning |
| --- | --- |
| ID | The item's ID in the audit receipt (`items[].id`). R = §0 rule, RQ = research question, D = definition, H = §2.1 boundary, E = §2.2 eligibility, S = dataset, Q = reconciliation, V = v0, X/A/B/C = experiments, M = statistics, K = metrics and decisions, T = tests, P = phase, G = CLI and modes, F = config, O = deliverable, Z = before completion, L = §12 decision logic, W = §13 caveat |
| Status | The final directive's completion statuses (§12 F2), separate from research outcomes: an experiment that found NOT_USEFUL is COMPLETE_VERIFIED.<br>- **COMPLETE_VERIFIED:** implemented, executed, and every check passed.<br>- **PENDING_FUTURE_DATA:** infrastructure in place; the observations don't exist yet.<br>- **DEFERRED_APPROVAL:** awaiting the owner's decision.<br>- **NOT_APPLICABLE:** the requirement has no meaning here.<br>- **PARTIAL, BLOCKED_EXTERNAL, NOT_IMPLEMENTED:** used for none.<br>- **FAILED:** a check failed, or a claim short of completion lacks evidence |
| Logic | Where the code is and what it computes. Module paths are under `libs/arbit-model/src/arbit_model/`; `dvp.py` is `scripts/model/dvp.py` |
| Proof | The audit checks (receipt key `checks`), with what they observed |

Check names:
- `test:Txx`: every test function tagged Txx ran and passed.
- `rerun:*`: a fresh rerun matched its committed receipt.
- `registry:*`: the experiment registry's status.
- Others read committed receipts, configs or git history.

## How the slice fits together

The study runs as one chain. Each step reads only the output of the step before it, after checking that output's hash:

1. **FFA actuals** (Arbit's canonical target store, index `6ffb62fb…`, after the R-072 franchise-code repair).
2. **`dvp.py audit`:**
   - admits sources through the lineage allowlist (`dvp/provenance.py`);
   - builds one observation per completed team-game and position group (`dvp/observations.py`);
   - writes `artifacts/dvp/phase1-audit-20261124T024442Z/` and its receipts.
3. **`dvp.py reproduce-v0`:** reruns v0 unchanged and recomputes it independently (`dvp/reliability.py`).
4. **`dvp.py reliability`:** Phase A, descriptive only (`dvp/lab.py`).
5. **`dvp.py backtest`:**
   - Phase B walk-forward forecasts (`dvp/walkforward.py`, with `dvp/asof.py` for cutoffs);
   - development, then candidates frozen, then validation;
   - **`dvp.py freeze`** writes `config/dvp/frozen.json`;
   - then the holdout, which runs only when every frozen hash matches.
6. **`dvp.py sitstart`:** Phase C on the frozen forecasts (`dvp/decisions.py`), under the rule committed first in `config/dvp/sitstart.json`. Then `config/dvp/frozen-phase-c.json` freezes it for 2026.
7. **`dvp.py verify`, `report`, `registry`:**
   - recompute every metric from the stored forecasts;
   - draw the plots and write `METRICS.csv`;
   - write the experiment records (`dvp/results.py`).
8. **`scripts/model/dvp_plan_audit.py`:** this audit.

**Nothing connects to production.**
- No app, API, worker or advisor reads these outputs.
- Every database connection the research opens is read-only (T26).
- `feature_specs` still holds v0's constants, byte for byte (`open:owner-weight`).

## The reruns behind this audit

From `plan-audit-receipt.json` → `reruns`. Run on 2026-11-25 with `POLARS_MAX_THREADS=2`.

| Step | Tree | Exit (expected) | Seconds | Compared with the committed receipt |
| --- | --- | --- | --- | --- |
| audit | this tree (`3848cad`) | 0 (0) | 1.6 | Equal except code, time and run ID. The observation table is identical: 31,668 rows and 19 columns (`rerun:audit`, `rerun:observations`). The projection audit now scans 30 files, up from 19, because later DvP modules joined the scan list. It still finds 0 projections (`rerun:projection-audit`) |
| reproduce-v0 | this tree | 0 (0) | 6.9 | Equal except code and time (`rerun:v0`) |
| reliability | this tree | 0 (0) | 73.9 | Equal except code and time, apart from A12's live vintage diagnostic. That diagnostic reads Arbit's growing 2026 capture history and is allowed to grow (`rerun:reliability`) |
| backtest development | this tree | 0 (0) | 25.9 | Results, selection, sensitivity and folds equal. The forecasts matched within 10⁻⁹, so the file was left byte-identical (`rerun:development`, `rerun:forecasts-development`) |
| backtest validation | this tree | 0 (0) | 6.7 | The same (`rerun:validation`, `rerun:forecasts-validation`) |
| backtest holdout | frozen tree `165d140` | 0 (0) | 5.8 | Equal except time and the Parquet byte hash. The forecasts match within 7.1×10⁻¹⁵ points: 32 values differ in the last bit; the count varies from run to run (`rerun:holdout-frozen-tree`, `rerun:forecasts-holdout`) |
| backtest holdout | this tree | **1 (1)** | 0.5 | Refused: "frozen manifest does not match: scripts/model/dvp.py changed". Receipt untouched (`rerun:holdout-refused-here`) |
| sitstart | this tree | 0 (0) | 0.8 | Equal except code and time (`rerun:sitstart`) |
| verify | this tree | 0 (0) | 10.2 | Equal except code and time; PASSED (`rerun:verify`, `verify:passed`) |
| report | this tree | 0 (0) | 0.5 | `METRICS.csv` and all 15 plots byte-identical (`rerun:report-files`) |
| registry | this tree | 0 (0) | 0.5 | `experiment-registry.json` identical (`rerun:registry`) |
| model tests | this tree | 0 (0) | 13.5 | 213 passed, 0 failed, 0 skipped. The real-artifact tests ran against the audit run |

Why some fields may differ:
- **Byte hashes.** polars' parallel group-by returns rows in varying order, and its parallel sums move the last bit of some floats. Every metric is order-free and rounded far above that noise. The receipts written since TASK-20261124-004 also carry a content hash.
- **Development and validation configs.** Their receipts name the `backtest.json` from before the freeze. The freeze added the holdout stage and a `frozen` key and changed no development or validation setting (`rerun:config-freeze-only-added`).

## §0 Operating rules

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| R01 | Resume M3-3 from v0: inventory, verify and continue it | COMPLETE_VERIFIED | `continuity-manifest.json` pins v0's four files and its consumer by SHA-256; [M3-3_CONTINUITY.md](M3-3_CONTINUITY.md) maps origin, stages and decisions; every extension writes new runs and receipts | `test:T29` (3 tests), `v0:bytes` (5 of 5 files match), `v0:reproduced` (REPRODUCED, 12 of 12 measures), `registry:v0` |
| R02 | Read AGENTS.md; inspect scoring, contracts, tests and v0 before changing anything | COMPLETE_VERIFIED | [M3-3_CONTINUITY.md](M3-3_CONTINUITY.md) maps v0's script, receipt, write-up, consumer (`feature_specs`) and decisions (OWN-068, ENG-056). The audit's scoring checks run against the actual scoring layer (`arbit_core.scoring`, `arbit_core.rules`) | `deliverable:4`, `test:T29` |
| R03 | Use Arbit's canonical FFA actuals under the league's rules only | COMPLETE_VERIFIED | `dvp.py audit` checks the targets' scoring hashes (athlete `10e938eb…`, D/ST `16885a80…`) against the league's current rules. It recomputes every line's points from its rule contributions | `test:T30`, `test:T37`, `audit:checks` (10 of 10 PASSED; 257,914 lines, 0 mismatched) |
| R04 | Exclude every provider projection by schema, lineage and executable tests | COMPLETE_VERIFIED | `provenance.admit` takes only allowlisted sources with known columns. `provenance.scan_code` searches code for projection tokens and provider imports. `walkforward.prepare` refuses unknown columns. `results.enforce` invalidates any record with a dependency | `test:T31`–`T33`, `test:T40`, `provenance:passed` (PASSED, 0), `receipts:no-projection` (every receipt 0) |
| R05 | B00 and every variant forecast only from eligible completed-game actuals | COMPLETE_VERIFIED | `walkforward._b00` uses the side's own history from the feature view. Variants add terms from the opposing unit's residuals in the same view. `asof.league_prior` uses observed actuals only | `test:T38`, `test:B11`, `backtest:variants` (23 variants, 6 groups, 3 stages) |
| R06 | Realized data counts only once completed and available by the cutoff | COMPLETE_VERIFIED | `asof.features_as_of` keeps rows with `available_at` ≤ cutoff. A game's actuals count from 12:00 UTC the day after its game day. Unfinished games have no row | `test:T15`, `test:T34`, `test:T35`, `test:T39` |
| R07 | Isolated branch; no production write, weight change or canonical-table replacement | COMPLETE_VERIFIED | Work runs on branches with PRs. Engines are created with `postgresql_readonly`. There are no write statements or commits, and no `feature_specs` import | `test:T26` (15 tests), `config:no-production` (3 of 3 false), `open:owner-weight` (feature_specs unchanged) |
| R08 | Preserve v0 untouched; extend through versioned experiments | COMPLETE_VERIFIED | v0 files are never written. Extensions are `M3-3-*` records and new receipts | `v0:bytes`, `test:T29`, `rerun:continuity` |
| R09 | nflverse is the statistical foundation; no paid, opaque or projected inputs | COMPLETE_VERIFIED | Target input families are allowlisted (pbp, players, schedules, snap_counts, stats_player, stats_team, weekly_rosters). Every reachable forbidden source is inventoried as REJECT | `provenance:passed` (no unlisted family, 21 admitted sources), `provenance:forbidden-inventory` (7 REJECT, OWN-061/OWN-067) |
| R10 | Report repeatability, forecasting, player-level impact and shrinkage separately | COMPLETE_VERIFIED | Separate phases, receipts and reports (RELIABILITY / BACKTEST / PLAYER_LEVEL). The model card's conclusions table has separate columns | `docs:conclusions`, `registry:A05`, `registry:B06`, `registry:C05` |
| R11 | Every forecast uses inputs and parameters available at its cutoff; vintage limits documented | COMPLETE_VERIFIED | `walkforward.fit_fold` fits on seasons before s. `check_stage` refuses the holdout outside a verified holdout stage. The score finality audit states the final-revision limitation | `test:T16`–`T18`, `finality:recorded` (PASSED_WITH_LIMITATION) |
| R12 | No fabrication; unavailable inputs disable experiments, recorded as BLOCKED | COMPLETE_VERIFIED | C03 and league-lineup evaluation are BLOCKED with reasons. Each stage's exit code is recorded | `registry:C03` (BLOCKED), `phasec:not-available`, `rerun:steps` |
| R13 | Durable documentation so a fresh agent can resume | COMPLETE_VERIFIED | Runbook, reports, decision register, changelog, handoffs, and the prospective procedure | `deliverable:1`, `deliverable:9`, `docs:prospective` |
| R14 | Use the status vocabulary; never claim unrun tests; never promote without approval | COMPLETE_VERIFIED | `results.STATUSES` holds the specification's words. The model card says "Not eligible yet" | `registry:complete`, `test:dvp-all` (147 passed, 0 skipped), `docs:status-vocabulary` |

## §1 Research questions

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| RQ1 | Is there a repeatable, position-specific defensive tendency? | COMPLETE_VERIFIED | Split-half (A01) and REML variance components (A05). For QB–K the unit is the defense; for D/ST it is the offense. Answer: yes for every group, strong only for D/ST | `registry:A01`, `registry:A05`, `v0:validated` (320 units), `reliability:a05` (REML k: D/ST 7.2, RB 19.5, QB 24.2, WR 26.7, TE 37.4, K 50.5) |
| RQ2 | How much is trait vs schedule, offense, randomness and transient conditions? | COMPLETE_VERIFIED | A03 adjustments (none, season, leave-one-out mean and median, shrunk), A05 season-wide variance, A06 within-season drift, A08 nulls, A09 components | `registry:A03`, `registry:A05`, `registry:A06`, `registry:A08`, `registry:A09` |
| RQ3 | Evidence strength by position and sample; v0's conversion vs variance models | COMPLETE_VERIFIED | A04 eras and half sizes. A05 REML uses each unit's own game count; its implied odd/even r is set against the observed one. v0's k uses the mean half size of 8.25 | `registry:A04`, `registry:A05`, `v0:wr-k` (44.1 at m = 8.2469; 42.74 at m = 8), `test:T12` |
| RQ4 | Does pre-week defensive information improve next-game forecasts? | COMPLETE_VERIFIED | B00 against B01–B07 on identical rows, for every group, from the walk-forward engine | `registry:B00`, `registry:B03`, `registry:B06`, `backtest:variants` |
| RQ5 | Does it add value over the offense-only baseline, consistently? | COMPLETE_VERIFIED | The predeclared rule over development, 2024 and 2025: D/ST PROMISING; QB INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL | `backtest:decisions`, `backtest:dev-folds` (7 rolling folds, none leaky), `registry:HOLDOUT-2025` |
| RQ6 | (Conditional) player-level forecasts and pairwise start/sit | COMPLETE_VERIFIED | Phase C for D/ST, the only group past the gate: pairwise accuracy of B06 vs B00 | `phasec:decision` (+4.45 / +8.55 / +6.62 points), `registry:C04`, `registry:C05` |
| RQ7 | (Conditional) operationalize: estimator, shrinkage, freshness, fallback; approval-gated | COMPLETE_VERIFIED | The model card states the estimator (B06, k ≈ 8, last-season prior), the fallback to B00, fail-closed behavior, eligibility for promotion and the prospective gate. The production weight itself is item P5W | `docs:conclusions`, `docs:prospective`, `open:owner-weight` |

## §2 Definitions and scoring contract

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| D01 | position: groups from the league's configuration; FB as RB; K and D/ST in scope; negatives kept | COMPLETE_VERIFIED | The groups come from the league's lineup slots (QB, RB, WR, TE, FLEX, DST, K). Mapping: FB and HB to RB, PK to K. `observations.position_cells` sums without clamping | `audit:positions` (groups DST, K, QB, RB, TE, WR), `test:T02`, `test:T04` |
| D02 | game and team_game: completed regular-season games, exactly two team-games each | COMPLETE_VERIFIED | `observations.games` reads the schedule. `team_games` emits each team as the offense, mirrored | `audit:reconciliation` (2,639 games, 5,278 team-games, 0 unmirrored), `test:T06` |
| D03 | offense and defense: the offense's points by group are the opposing defense's points allowed | COMPLETE_VERIFIED | The opponent always comes from the schedule, never from the target row (`observations.position_cells`) | `test:T07`, `test:T01` |
| D04 | D/ST special case: the opposing D/ST's points against the offense (offense vulnerability) | COMPLETE_VERIFIED | `observations.dst_cells`: the row's `unit` is the offense, `defense` is the scoring D/ST. Hand-checked: CAR at JAX, 2025 week 1, JAX D/ST 12.0 | `test:T07`, `audit:examples` |
| D05 | true zero vs missing or invalid | COMPLETE_VERIFIED | A cell is a true zero only if the team-game has target rows. Otherwise it is `missing_coverage`, `invalid_refused_line` or `invalid_duplicate_line`, with no points | `test:T03`, `audit:cells` (58 refused-line cells; true zeros: TE 109, K 162, D/ST 266) |
| D06 | delta: points less a stated offense expectation; positive means the defense allowed more | COMPLETE_VERIFIED | `lab.adjust` (none / season / loo_mean / loo_median / loo_shrunk). Forecast residuals: `points − b00_pit` | `test:T08`, `registry:A03` |
| D07 | defense-season: no presumption that a trait survives seasons | COMPLETE_VERIFIED | The unit-season is the unit of analysis. Carryover is measured, not assumed (A07, r 0.14–0.40) | `registry:A07`, `reliability:experiments` |
| D08 | forecast cutoff: pre-week by default; per-game is a separate experiment; never mixed | COMPLETE_VERIFIED | `asof.Cutoff.PREWEEK` (first kickoff of the week) is the default. `PER_GAME` exists only in B10's sensitivity run | `test:T15`, `test:T35`, `registry:B10` |
| D09 | game count n: eligible games, not calendar weeks; byes and cancellations add no exposure | COMPLETE_VERIFIED | n counts valid observation rows. Byes and the canceled 2022 BUF–CIN game have no row | `test:T10`, `test:T34` |

## §2.1 Hard data boundary

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| H01 | Scoring truth: FFA rules, Arbit's canonical actuals, nflverse raw stats for reconciliation | COMPLETE_VERIFIED | The scoring hash is checked against the league document. Lines are recomputed from rule contributions | `test:T30`, `audit:checks` |
| H02 | Pregame features: only previously completed actuals and realized stats; priors from actuals | COMPLETE_VERIFIED | The feature view and `asof.league_prior` use observed rows available by the cutoff | `test:T38`, `test:T15` |
| H03 | Prohibited everywhere: ESPN and vendor projections, rankings, forecasts, copied points-allowed tables | COMPLETE_VERIFIED | Forbidden inventory, lineage allowlist, and a code scan for projection tokens and provider imports (`arbit_data.espn`, `arbit_data.sleeper`) | `test:T31`, `test:T32`, `provenance:forbidden-inventory` |
| H04 | Arbit forecasts are outputs with traceable ancestry, never fed back as actuals | COMPLETE_VERIFIED | `FrozenForecasts` carry no label column. `evaluation_join` adds labels only after freezing, one to one | `test:T36`, `test:T20` |
| H05 | Mandatory row metadata: source, type, lineage, IDs, status, finality, scoring hash, feature_as_of | COMPLETE_VERIFIED | Observation columns: `source_id`, `source_type`, `scoring_hash`, `observed_or_generated`, `finality_basis`, `available_at`, plus IDs and status. Forecasts carry `feature_as_of` | `audit:observation-lineage` (31,668 rows, no nulls; only FFA_ACTUAL_FINAL, observed), `test:T36` |
| H06 | Enforcement by allowlist and typed schemas; unknowns fail closed; machine-readable exclusion audit | COMPLETE_VERIFIED | `provenance.admit` raises `LineageError` (UNKNOWN_COLUMN, UNKNOWN_SOURCE…). [PROJECTION_EXCLUSION_AUDIT.json](PROJECTION_EXCLUSION_AUDIT.json) | `test:T33`, `test:T32`, `provenance:passed` |

## §2.2 Time eligibility

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| E01 | Prior-week completed FFA points: eligible | COMPLETE_VERIFIED | Available from 12:00 UTC the day after the game, so before the next week's cutoff | `test:T34`, `test:T25` |
| E02 | Prior completed-game nflverse stats used to validate actuals: eligible under the as-of rule | COMPLETE_VERIFIED | Used only to recompute and reconcile actuals, never as features | `test:T30`, `finality:recorded` |
| E03 | This week's Thursday result: only under a per-game cutoff | COMPLETE_VERIFIED | The PREWEEK cutoff is the week's first kickoff, so a Thursday result is excluded. PER_GAME includes it, in B10 only | `test:T35`, `test:T15` |
| E04 | Game underway, delayed or unfinished at the cutoff: never | COMPLETE_VERIFIED | Such a game has no observation row and no `available_at` before the cutoff | `test:T34` |
| E05 | Game completed after the cutoff: label only, never a feature | COMPLETE_VERIFIED | Feature views filter by cutoff. Deleting or perturbing future data leaves earlier forecasts identical | `test:T16`, `test:T17`, `test:T39` |
| E06 | ESPN projected points, even pregame: never | COMPLETE_VERIFIED | No DvP source reads ESPN. A planted projection column fails closed | `test:T32`, `test:B11` |
| E07 | Vendor projections renamed `opponent_expected`: never | COMPLETE_VERIFIED | Admission follows lineage, not names, so an unknown column stops the pipeline under any name | `test:T32` (6 cases, including `opponent_expected`), `test:T33` |
| E08 | Arbit B00 from prior actuals: allowed as output and comparator | COMPLETE_VERIFIED | B00 is the comparator of every variant and C00 of Phase C | `test:T38`, `registry:B00` |
| E09 | Two isolated views (features as of T, targets after T), joined only after forecasts are written | COMPLETE_VERIFIED | `asof.FeatureView` and `LabelView` are separate. `evaluation_join` requires `FrozenForecasts` and a 1:1 key | `test:T36`, `test:T20` |

## §3 Data and lineage

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| S01 | canonical_ffa_player_week | COMPLETE_VERIFIED | Arbit's FFA target store (index `6ffb62fb…`), read by `dvp.read_targets` | `audit:checks`, `test:T30`, `test:T05` |
| S02 | canonical_ffa_dst_week: one D/ST line per completed team-game | COMPLETE_VERIFIED | The target store's D/ST lines, through `observations.dst_cells`. All 5,278 team-games are scored | `audit:cells` (D/ST 5,278 valid), `test:T07` |
| S03 | nfl_schedule | COMPLETE_VERIFIED | `schedule_games.parquet` holds completed regular-season games. Its hash is pinned in `frozen.json` | `audit:seasons` (512 per season 2016–2020, 544 for 2021 and 2023–2025, 542 in 2022), `test:T06` |
| S04 | team_game_position and defense_game_position | COMPLETE_VERIFIED | `observations.parquet` (`observations.observations`) | `audit:observation-lineage`, `rerun:observations` (identical), `test:T01` |
| S05 | historical_cutoff_index | COMPLETE_VERIFIED | `asof.cutoffs` gives each game's cutoff under its mode; forecasts record `feature_as_of` | `test:T15`, `test:T35` |
| S06 | experiment_registry | COMPLETE_VERIFIED | `experiment-registry.json`, 34 records written by `dvp.py registry` from the receipts | `registry:complete` (no missing experiments or fields), `rerun:registry` |
| S07 | source_provenance_allowlist | COMPLETE_VERIFIED | `provenance.SourceSpec` allowlist; the admitted sources are listed in the exclusion audit | `provenance:passed` (21 admitted), `test:T33` |
| S08 | prohibited_source_audit | COMPLETE_VERIFIED | `provenance.Forbidden` inventory with action, decision and guard | `provenance:forbidden-inventory`, `test:T31` |
| S09 | No new scoring engine: reuse stored FFA actuals; recompute only to audit | COMPLETE_VERIFIED | Points come from the target store. The audit recomputes only to compare | `audit:checks`, `test:T30` |
| S10 | Supplementary sources only with lineage; component stats for A09 and B07 | COMPLETE_VERIFIED | A09 and B07 split points by the scorer's own rule contributions, which sum back exactly | `provenance:passed`, `registry:A09`, `registry:B07` |
| Q01 | 5,278 completed team-games verified against the schedule (canceled BUF–CIN excluded) | COMPLETE_VERIFIED | `observations.reconcile` counts per season from the schedule rather than forcing the number | `audit:reconciliation`, `audit:seasons`, `test:T06` |
| Q02 | 320 defense-seasons audited per filter | COMPLETE_VERIFIED | v0-validated covers 320 units in every group (315 for D/ST before the R-072 repair) | `v0:validated`, `audit:seasons` |
| Q03 | Two team-games per game, offense–defense symmetry, D/ST reverse orientation; no postseason or phantom zeros | COMPLETE_VERIFIED | Mirror check, schedule-derived opponents, REG games only, canceled games absent | `audit:reconciliation`, `test:T06`, `test:T07`, `test:T34` |
| Q04 | Renames and relocations, trades, duplicates, multi-position mapping, negatives, corrections | COMPLETE_VERIFIED | Franchise codes (OAK→LV, SD→LAC, STL→LA). 645 traded player-seasons kept in their own games. Duplicate lines are invalid. Negatives kept | `audit:checks`, `test:T05`, `test:T02`, `test:T04` |
| Q05 | Hand-checked samples: zero TE, multi-WR, traded player, D/ST turnover, canceled game | COMPLETE_VERIFIED | Examples stored in the audit receipt, set out in [DATA_QUALITY.md](DATA_QUALITY.md) | `audit:examples`, `audit:checks` |
| Q06 | Data quality report and machine-readable anomalies; invalid rows blocked | COMPLETE_VERIFIED | DATA_QUALITY.md and `audit-receipt.json → anomalies`. Invalid cells carry no points and are excluded downstream | `deliverable:2`, `audit:cells` |
| Q07 | Finality and availability at every cutoff; conservative fallback declared | COMPLETE_VERIFIED | [SCORE_FINALITY_AUDIT.json](SCORE_FINALITY_AUDIT.json): final revisions only, available at 12:00 UTC the next day. A12 measures corrections; B12 tests a 48-hour delay | `finality:recorded`, `rerun:finality-audit`, `registry:A12`, `registry:B12` |
| Q08 | Full projection-lineage scan over v0 and every new input | COMPLETE_VERIFIED | The code scan covers the scoring path, v0's scripts and every DvP module (`dvp.SCANNED`) | `provenance:passed`, `rerun:projection-audit` (21 files, 0 findings), `test:T31` |

## §4 v0: audit, reproduce, freeze

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| V01 | Position sums per complete team-game; FB as RB; valid zeros | COMPLETE_VERIFIED | `observations.position_cells` | `test:T01`, `test:T02`, `test:T03` |
| V02 | Defense inversion with the separate D/ST interpretation | COMPLETE_VERIFIED | The opponent comes from the schedule; for D/ST the unit is the offense | `test:T07` |
| V03 | Same-season leave-one-game-out offense adjustment; singletons handled | COMPLETE_VERIFIED | `reliability.leave_one_out` gives the mean of the group's other rows, or null for a single row (no NaN or infinite weight) | `test:T08` |
| V04 | Odd vs even NFL calendar weeks; at least 4 games per half; unequal halves recorded | COMPLETE_VERIFIED | `reliability.halves` splits by week parity, not row order, and records each unit's half sizes | `test:T09`, `test:T10` |
| V05 | Split-half Pearson and Spearman, raw and adjusted, counts, intervals, scatter plots | COMPLETE_VERIFIED | `reliability.split_half`, `fisher_interval`, and `bootstrap` resampling units and seasons. Plots `split-scatter-*.svg` | `v0:validated` (12 measures, 2,000 reps, seed 1729), `deliverable:10` |
| V06 | Reproduce v0 r, single-game reliability, k and w(n); explain WR 44.1 vs 42.63 | COMPLETE_VERIFIED | v0's own script is rerun on its index, and `reliability.*` recomputes it independently. k = m(1 − r)/r with m = 8.2469, the mean half size, because 17-game seasons split 8/9 | `v0:reproduced`, `v0:wr-k` (r 0.15766, k 44.1; 42.74 at m = 8), `rerun:v0`, `test:T11` |
| V07 | Freeze v0: outputs, hashes, config and a discrepancy report; lineage audited | COMPLETE_VERIFIED | `continuity-manifest.json`. [V0_REPRODUCTION.md](V0_REPRODUCTION.md) gives five discrepancies and their dispositions; no contamination found. A11 is PASSED | `v0:bytes`, `rerun:continuity`, `registry:A11`, `deliverable:4` |

## §5 Experiment program

**Logic of the walk-forward models** (`dvp/walkforward.py`). Season s, position p, cutoff T. Each forecast uses only rows available by T, with parameters fit on seasons before s (`fit_fold`).

**B00, the offense-only comparator.**
- `prior = L(s−1) + b·(own(s−1) − L(s−1))`, where:
  - `L(s−1)` is the league mean last season;
  - `own(s−1)` is the scoring side's own mean last season;
  - `b` is the carryover slope fit on training seasons (0 if fewer than 20 pairs, never negative).
- `B00 = (n·mean_own + k_own·prior) / (n + k_own)`. Here `k_own` is the REML k of the side's own season-centered record, fit on training seasons.

**DvP terms.**
- **Residuals:** `r_pit` is the opposing unit's mean residual, `points − B00_pit`. `B00_pit` is the B00 frozen for each of its earlier games, so these residuals are point-in-time. `r_rec` recomputes those baselines with what is known at T.
- **The variants:**
  - **B01:** raw points against the league mean.
  - **B02:** the residual, unshrunk.
  - **B03:** `n/(n + k_dvp)·r_pit`, with `k_dvp` from REML on training seasons.
  - **B04:** a grid of k from 1 to 256.
  - **B05:** recency weights `0.5^((age − 1)/h)`, h = 2, 4 or 8, shrunk by `n_eff/(n_eff + k)` with `n_eff = (Σw)²/Σw²`.
  - **B06:** `(n·r_pit + k_dvp·slope·prev_resid)/(n + k_dvp)`, the residual shrunk toward last season's.
  - **B07:** B03 on non-touchdown points.
- **Controls (B09):**
  - shuffled opponents within position;
  - Gaussian noise with r_pit's spread;
  - last week's opponent.

**Phase 4 rule** (`walkforward.decide`, in `config/dvp/frozen.json`):
- **PROMISING:** the frozen candidate is a DvP variant and cuts RMSE by at least 1% in development, 2024 and 2025.
- **NOT_USEFUL:** the best variant misses 1% in all three periods.
- **INCONCLUSIVE:** anything between.
- **BLOCKED:** an integrity failure.

**Phase C** (`dvp/decisions.py`, rule in `config/dvp/sitstart.json`, committed in `317361f` before any result):
- **Pairs:** every unordered pair of D/STs playing in the same week. Each model starts the unit with the higher forecast.
- **Scoring:** credit is 1, 0.5 for a forecast tie, or 0. Pairs whose units scored the same are excluded.
- **Measures:** accuracy change in percentage points; points from changed choices; within-week Spearman; top 8; close-call pairs (forecasts within 1 point); waiver-pool pairs (ranks 9–24).
- **Uncertainty:** week-block bootstrap, 2,000 replicates, seed 1729.
- **Rule:** PROMISING if every period gains at least 1.8 points and net points are positive.
- **Where 1.8 comes from:**
  - accuracy = 0.5 + asin(ρ)/π;
  - B00's development Spearman of 0.1448 gives 54.63%;
  - Phase B's 1% RMSE cut moves ρ to 0.2011, which gives 56.45%.

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| X00 | Every experiment states hypothesis, estimator, data, cutoff, ancestry, comparator, metric, interval and conclusion | COMPLETE_VERIFIED | `results.record` requires all 30 §10 fields. `dvp.py registry` builds them from the receipts | `registry:complete` (34 records, none missing a field) |
| A00 | Raw DvP landscape | COMPLETE_VERIFIED | `lab.landscape` gives distribution, skew, SD and unit-season spread; `lab.rank_agreement` compares raw with adjusted ranks | `registry:A00`, `reliability:experiments` |
| A01 | v0 odd/even exact replication, raw and adjusted, with intervals | COMPLETE_VERIFIED | `dvp.py reproduce-v0`: v0-validated with Fisher, unit and season intervals | `registry:A01`, `rerun:v0` |
| A02 | Split-method sensitivity | COMPLETE_VERIFIED | `lab.assignment` covers calendar, alternating, chronological, first 6 vs next 6, and home/away. `lab.random_splits` runs 1,000 seeded balanced splits. The minimum game count varies from 2 to 7 | `registry:A02`, `reliability:experiments` |
| A03 | Opponent-adjustment sensitivity | COMPLETE_VERIFIED | `lab.adjust` with none, season, loo_mean, loo_median and loo_shrunk | `registry:A03`, `reliability:experiments` |
| A04 | Position-specific sample stability by era and game counts | COMPLETE_VERIFIED | Era split (2016–2020 vs 2021–2025), half-size strata, weight curves, and `lab.joint_orderings` for the order among positions | `registry:A04`, `reliability:experiments` |
| A05 | Variance decomposition | COMPLETE_VERIFIED | `lab.anova_components` (method of moments, n0 for unequal sizes) and `lab.reml_components` (profile REML, each unit's own size, convergence and boundary flags). `season_component`. `bootstrap_components` resamples seasons | `registry:A05`, `reliability:a05` (all converged; D/ST k 7.2, 6.0–8.6) |
| A06 | Temporal stability | COMPLETE_VERIFIED | `lab.lag_profile` (covariance by weeks apart), `rolling_window` against `implied_window_r`, and the first-vs-second-half difference | `registry:A06`, `reliability:experiments` |
| A07 | Between-season carryover | COMPLETE_VERIFIED | `lab.carryover` and `carryover_summary`, with franchise continuity; decayed prior vs reset, left out one season at a time | `registry:A07`, `reliability:experiments` |
| A08 | Noise, placebo and null | COMPLETE_VERIFIED | `lab.permutation_null` shuffles within week (1,000 shuffles). `cluster_bootstrap` resamples seasons vs units. Holm correction across 12 tests | `registry:A08`, `reliability:experiments` (Holm present) |
| A09 | Signal decomposition | COMPLETE_VERIFIED | Points split into the scorer's rule components, each with its own REML k | `registry:A09`, `reliability:experiments` |
| A10 | Data and era robustness | COMPLETE_VERIFIED | Leave one season out, exclude 2020 or 2022, winsorize 1–99%, trim at 3 SD; `lab.influence` (jackknife), the largest single cell, and after-bye | `registry:A10`, `reliability:experiments` |
| A11 | v0 source and score audit | COMPLETE_VERIFIED | Scoring hash, completion status and lineage of v0's inputs; no projection found | `registry:A11` (PASSED), `rerun:v0` |
| A12 | Completion and correction sensitivity | COMPLETE_VERIFIED | Refused-line inclusion vs exclusion. 2026 first-held vs latest values for 158 games: 2 of 1,896 cells moved | `registry:A12`, `reliability:experiments` |
| B00 | Offense-only null | COMPLETE_VERIFIED | `walkforward._b00` (formula above) | `registry:B00`, `backtest:variants` |
| B01 | Raw DvP naive | COMPLETE_VERIFIED | `b00 + r_raw` | `registry:B01`, `backtest:variants` |
| B02 | Adjusted DvP, unshrunk | COMPLETE_VERIFIED | `b00 + r_pit` (B02r: `r_rec`) | `registry:B02`, `backtest:variants` |
| B03 | k-shrunk adjusted DvP | COMPLETE_VERIFIED | `b00 + n/(n + k_dvp)·r_pit` (B03r: `r_rec`). Gains are reported by opponent games: none, 1–3, 4–7 and 8 or more | `registry:B03`, `backtest:variants` |
| B04 | Empirically tuned k | COMPLETE_VERIFIED | Grid {1, 2, 4, …, 256}, selected on development only. The tuned k matches REML (D/ST 8 vs 7) | `registry:B04`, `backtest:variants` |
| B05 | Recency DvP | COMPLETE_VERIFIED | Half-lives 2, 4 and 8, using n_eff | `registry:B05`, `backtest:variants` |
| B06 | Temporal or hierarchical DvP | COMPLETE_VERIFIED | Partial pooling toward last season's residual × slope, compared against B03 | `registry:B06`, `backtest:variants` |
| B07 | Opportunity and efficiency alternative | COMPLETE_VERIFIED | Non-touchdown residuals. True target and carry counts need a realized-stat source not yet admitted, as recorded in the registry and RELIABILITY_REPORT A09 | `registry:B07`, `backtest:variants` |
| B08 | Context-stratified diagnostic | COMPLETE_VERIFIED | `walkforward.breakdown` by opponent games, week bin and season, plus `calibration` deciles (`results.*.focus`) | `registry:B08`, `backtest:b08-focus` |
| B09 | Adversarial negative controls | COMPLETE_VERIFIED | Shuffled opponents, noise, last week's opponent. None improves on B00 meaningfully | `registry:B09`, `backtest:variants` (b09 family present) |
| B10 | Cutoff-policy sensitivity | COMPLETE_VERIFIED | `Cutoff.PER_GAME` against PREWEEK: no B00 or B03 forecast changed, since each team plays once a week | `registry:B10`, `backtest:sensitivity` |
| B11 | Projection-contamination resistance | COMPLETE_VERIFIED | Planted projection rows or a renamed column raise `UNKNOWN_COLUMN` in `walkforward.prepare` | `registry:B11` (PASSED), `test:B11` |
| B12 | Actual-score as-of robustness | COMPLETE_VERIFIED | `Settings.availability_delay` = 48 h: 6 B00 and 26 B03 development forecasts changed; RMSE moved by less than 0.001 | `registry:B12`, `backtest:sensitivity` |
| C00 | Arbit-computed player baseline, no DvP | COMPLETE_VERIFIED | C00 = B00. Arbit has no other player projection, and no provider projection exists in this path | `registry:C00`, `phasec:decision` |
| C01 | Conservative group adjustment by player share | COMPLETE_VERIFIED | One D/ST per team means share 1: the group forecast is the player forecast. `decisions.units` maps each forecast row to the D/ST that faced the offense and fails closed on any mismatch | `registry:C01`, `test:phase-c` (10 tests) |
| C02 | Compare additive, proportional and opportunity × efficiency allocation | COMPLETE_VERIFIED | Identical by construction at share 1; nothing to choose between | `registry:C02`, `test:phase-c` |
| C03 | Route, slot and target-share interactions | NOT_APPLICABLE | Phase C is D/ST-only: D/ST is the only group past Phase B, and route, slot and target-share roles have no meaning for a D/ST. Recorded, not run (final directive F2) | `registry:C03` (BLOCKED, with reason) |
| C04 | Historical same-position start/sit pairs; close-call subgroup separate | COMPLETE_VERIFIED | `decisions.pairs` covers every same-week pair (`metrics … close`, `pool`). The primary metric uses all pairs, not only close calls | `registry:C04`, `phasec:decision`, `test:phase-c` |
| C05 | Decisions and errors: accuracy, ties, points, changes, regret | COMPLETE_VERIFIED | `decisions.metrics`: accuracy, changed choices, points from changes (total, per change, per week with interval), worst single choice and worst week | `registry:C05`, `phasec:decision`, `rerun:sitstart` |
| C05L-HIST | C05L on 2016–2025: lineups under the league's roster rules | NOT_APPLICABLE | FFA began in 2026 (OWN-076, the owner's Phase B clarification). The unrestricted D/ST pairwise evaluation stands for those seasons | `owner:inaugural-season` |
| C05L-2026-EXP | C05L on completed 2026 weeks 1–11, exploratory | COMPLETE_VERIFIED | `arbit_model.ffa_history` replays the draft and executed moves to each preweek cutoff: who held and who could claim each D/ST. `arbit_model.dvp.league` scores the frozen B00 and B06 start and stream picks; the rule was committed first (`07505d9`). Start (28 decisions): −6 points (−90 to +80); stream (88): +46 (−280 to +360). Too few decisions to measure ([LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md)) | `league2026:exploratory`, `ffa2026:ownership-replay` (11 periods, 14 daily snapshots) |
| C05L-2026-PRO | C05L on weeks 12–18, prospective | PENDING_FUTURE_DATA | Each prospective archive captures the D/ST rosters at forecast time, and from week 13 each unit's availability. Evaluated descriptively after the games | `prospective:league-capture`, `open:prospective` |

Phase C results (`phasec:decision`, `sitstart.json`):

| Period | Accuracy change (95%) | Net points from changed choices |
| --- | --- | --- |
| Development 2017–2023 | +4.45 points (3.27 to 5.64) | +27,362.5 |
| Validation 2024 | +8.55 points (4.13 to 12.55) | +7,978.0 |
| Holdout 2025 | +6.62 points (2.56 to 10.49) | +5,617.5 |

## §6 Statistical estimation

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| M01 | Research estimator: residuals, odd/even means, correlations with intervals; hierarchical form | COMPLETE_VERIFIED | `R = Y − mean(other games)`. The one-way model `y = μ + a + e` is fit by REML (`lab.reml_components`) | `registry:A01`, `registry:A05`, `test:T14` |
| M02 | Forecast estimator `O_hat + w·R_hist`; point-in-time vs recomputed residuals both tested | COMPLETE_VERIFIED | B03 vs B03r and B02 vs B02r. Recomputing did no better | `registry:B02`, `registry:B03`, `test:T25` |
| M03 | Unequal split sizes: expected correlation from each unit's half sizes; no negative k | COMPLETE_VERIFIED | `reliability.expected_split_r` = √(mA/(mA + k)·mB/(mB + k)). `k_from_r` returns None for r ≤ 0 | `test:T11`, `test:T12` |
| M04 | Clustered resampling, at least 1,000 seeded replicates, multiple comparisons | COMPLETE_VERIFIED | Seasons, unit-seasons and franchises compared as blocks; 2,000 replicates, seed 1729; Holm | `test:T13`, `reliability:experiments`, `registry:A08` |
| M05 | w(n) is credibility inside DvP, not a Sit/Start weight | COMPLETE_VERIFIED | Stated in the model card and its "not intended" list | `docs:conclusions`, `registry:A05` |
| M06 | Distribution: means vs robust estimates; RMSE beside MAE; winsorizing and trimming | COMPLETE_VERIFIED | Median adjustment (A03), winsorize and trim (A10), MAE and bias beside RMSE in every backtest result | `registry:A10`, `backtest:variants` |
| M07 | Conditional dependence between groups examined, not assumed independent | COMPLETE_VERIFIED | `lab.joint_orderings` resamples seasons once for every position together | `registry:A04`, `reliability:experiments` |

## §7 Metrics and decision rules

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| K01 | Phase A metrics | COMPLETE_VERIFIED | Split-half r, variance components, k, w(n), intervals and lag decay | `reliability:experiments`, `reliability:a05` |
| K02 | Phase B metrics: per-position RMSE and paired delta vs B00 on matching rows; MAE, bias, calibration, rank | COMPLETE_VERIFIED | `walkforward.metrics` (block bootstrap of ΔRMSE), `calibration`, `breakdown` | `backtest:variants`, `verify:passed` (468 metrics recomputed, 0 mismatched), `test:T19` |
| K03 | Phase C metrics | COMPLETE_VERIFIED | Pairwise accuracy, points from changed choices, number of changes, regret | `phasec:decision` |
| K04 | Baseline parity: common eligible rows; coverage differences surfaced | COMPLETE_VERIFIED | Every variant is scored on the same rows. Phase C uses common rows only | `test:T19`, `verify:passed` |
| K05 | Predeclared decision rule | COMPLETE_VERIFIED | `walkforward.decide` (frozen.json) and `decisions.decide` (sitstart.json) | `backtest:decisions`, `test:phase4-rule`, `phasec:rule-first` |
| K06 | Practical minimum from development data only | COMPLETE_VERIFIED | 1% relative RMSE, fixed in config before any forecast. 1.8 points for Phase C, from B00 development data only | `backtest:practical-minimum`, `phasec:rule-first` |
| K07 | 2025 conditionally confirmatory at best; no retuning to 2025 | COMPLETE_VERIFIED | CONDITIONALLY_HELD_OUT. Candidates frozen 03:05, validation 03:06, method frozen 03:16:19, holdout 03:16:31 UTC | `backtest:holdout-status`, `backtest:timeline`, `test:T18` |

## §8 Test catalog

Every test runs in CI without paid APIs. The audit ran them against the real audit run, so the two tests that skip without it ran too. Each test's tag is in its name (`test_tNN_…`).

| ID | Plan action | Status | Logic (test functions) | Proof |
| --- | --- | --- | --- | --- |
| T01 | Deterministic player-point sums | COMPLETE_VERIFIED | `test_t01_position_points_are_sums_of_canonical_lines` | `test:T01` (1) |
| T02 | FB→RB only; exact whitelist | COMPLETE_VERIFIED | `test_t02_fb_counts_as_rb_and_only_ffa_groups_are_summed` | `test:T02` (1) |
| T03 | True zero vs missing | COMPLETE_VERIFIED | `test_t03_true_zero_is_distinct_from_missing_and_invalid` | `test:T03` (1) |
| T04 | Negatives and decimals preserved | COMPLETE_VERIFIED | `test_t04_negative_and_decimal_points_are_preserved` | `test:T04` (1) |
| T05 | Multi-player, traded, duplicate, two-team cases | COMPLETE_VERIFIED | `test_t05_traded_player_duplicates_and_coverage` | `test:T05` (1) |
| T06 | Two team-games per finished game; per-year reconciliation | COMPLETE_VERIFIED | `test_t06_two_team_games_per_completed_regular_season_game` | `test:T06` (1) |
| T07 | Side reversal and D/ST orientation | COMPLETE_VERIFIED | `test_t07_defense_comes_from_the_schedule_and_dst_is_the_offense_vulnerability` | `test:T07` (1) |
| T08 | Leave-one-out matches by hand; singletons | COMPLETE_VERIFIED | `test_t08_leave_one_out_matches_a_hand_calculation` | `test:T08` (1) |
| T09 | Odd/even by NFL week, not index | COMPLETE_VERIFIED | `test_t09_halves_follow_nfl_week_parity_not_game_order` | `test:T09` (1) |
| T10 | At least 4 real games per half | COMPLETE_VERIFIED | `test_t10_each_half_needs_four_real_games` | `test:T10` (1) |
| T11 | Known r_m, k, r1, w(n); bounds; r ≤ 0; invalid inputs | COMPLETE_VERIFIED | `test_t11_known_values_bounds_and_invalid_inputs` | `test:T11` (1) |
| T12 | Unequal halves follow the variance model | COMPLETE_VERIFIED | `test_t12_unequal_halves_follow_the_variance_model`, `test_t12_reml_uses_each_units_own_game_count` | `test:T12` (2) |
| T13 | Fixed seed gives the same draws; a new seed changes only the draws | COMPLETE_VERIFIED | Four tests across reliability, lab and walk-forward | `test:T13` (4) |
| T14 | Non-convergence and boundary cases recognized | COMPLETE_VERIFIED | Boundary estimate, pure noise, grid-edge maximum | `test:T14` (3) |
| T15 | No outcome after the cutoff in features | COMPLETE_VERIFIED | `test_t15_a_thursday_result_reaches_sunday_only_under_per_game_cutoffs` | `test:T15` (1) |
| T16 | Future data deleted or perturbed: earlier forecasts identical | COMPLETE_VERIFIED | `test_t16_t17_future_and_own_results_never_change_a_forecast`; with schedule targets, `test_t16_t17_t20_outcomes_after_a_cutoff_change_neither_targets_nor_forecasts` (AUD-05) | `test:T16` (2) |
| T17 | No target result, season-end mean or holdout outcome in training | COMPLETE_VERIFIED | The same two tests as T16 | `test:T17` (2) |
| T18 | Split integrity; no tuning on 2025 | COMPLETE_VERIFIED | `test_t18_fold_parameters_come_from_earlier_seasons_only`, `test_t18_the_holdout_runs_only_as_a_verified_holdout_stage` | `test:T18` (2) |
| T19 | Identical eligible rows for every variant | COMPLETE_VERIFIED | `test_t19_t20_every_variant_covers_the_same_rows_and_labels_join_only_once_frozen` | `test:T19` (1) |
| T20 | Forecasts stored before outcomes merge; 1:1 join | COMPLETE_VERIFIED | The T19 test, and the AUD-05 test above | `test:T20` (2) |
| T21 | Synthetic stable effect recovered | COMPLETE_VERIFIED | Walk-forward and reliability versions | `test:T21` (2) |
| T22 | Pure-noise defenses give no systematic gain | COMPLETE_VERIFIED | Walk-forward and reliability versions | `test:T22` (2) |
| T23 | Mid-season trait shift detected by temporal methods | COMPLETE_VERIFIED | `test_t23_a_mid_season_shift_is_seen_by_halves_and_lags_not_by_odd_even` | `test:T23` (1) |
| T24 | Permutations and placebos give no stable uplift | COMPLETE_VERIFIED | Lab nulls and walk-forward placebos | `test:T24` (2) |
| T25 | Cold starts, no-history weeks, season boundary | COMPLETE_VERIFIED | `test_t25_week_one_is_the_prior_and_nothing_is_missing` | `test:T25` (1) |
| T26 | ID compatibility; no writing to prediction weights | COMPLETE_VERIFIED | Franchise codes and FFA groups on real forecasts; D/ST unit mapping fails closed; every engine read-only; no write statement, commit or `feature_specs` import | `test:T26` (20, including parametrized cases) |
| T27 | Artifacts, hashes, manifests and metrics read back and reproduce | COMPLETE_VERIFIED | Content hash ignores order and noise; reruns never overwrite; round trip; receipt schemas; verify coverage; real holdout reproduces | `test:T27` (8) |
| T28 | Single outlier game or season omitted: effect quantified | COMPLETE_VERIFIED | `test_t28_one_extreme_unit_season_is_found_and_its_effect_measured` | `test:T28` (1) |
| T29 | Continuity manifest | COMPLETE_VERIFIED | v0 byte identity; exact and independent reproduction; every experiment registered | `test:T29` (3) |
| T30 | Finalized FFA actuals under the league scoring | COMPLETE_VERIFIED | `test_t30_ffa_actuals_enter_only_under_the_league_scoring_hash_and_unchanged` | `test:T30` (1) |
| T31 | Projection scan with a reject/quarantine manifest | COMPLETE_VERIFIED | Scoring path and DvP code clean; every DvP module scanned; a planted projection is found | `test:T31` (3) |
| T32 | Injected ESPN and vendor projections, including `opponent_expected`, cannot influence outputs | COMPLETE_VERIFIED | Planted columns under any name, planted rows, projection source type | `test:T32` (6) |
| T33 | Unknown category or missing ancestry fails closed | COMPLETE_VERIFIED | `test_t33_unknown_category_or_missing_ancestry_fails_closed` | `test:T33` (1) |
| T34 | Unstarted, in-progress, canceled, unfinalized or later games are never features | COMPLETE_VERIFIED | `test_t34_unfinished_in_progress_and_later_games_are_never_features` | `test:T34` (1) |
| T35 | Thursday result: per-game refresh only; in-progress games never | COMPLETE_VERIFIED | `test_t35_a_thursday_result_reaches_only_the_per_game_forecast` | `test:T35` (1) |
| T36 | Labels are actuals; forecasts in distinct columns; joining labels into features impossible | COMPLETE_VERIFIED | `test_t36_features_and_labels_stay_apart_until_forecasts_are_frozen` | `test:T36` (1) |
| T37 | Scoring hash change invalidates | COMPLETE_VERIFIED | `test_t37_a_changed_scoring_hash_stops_the_pipeline` | `test:T37` (1) |
| T38 | B00 prior rebuilt from final FFA scores only | COMPLETE_VERIFIED | `test_t38_a_prior_comes_only_from_observed_ffa_actuals` | `test:T38` (1) |
| T39 | Late corrections and future values never change an earlier forecast | COMPLETE_VERIFIED | `test_t39_later_corrections_and_results_never_change_an_earlier_view` | `test:T39` (1) |
| T40 | `forbidden_vendor_projection_dependencies == 0`, or results invalid | COMPLETE_VERIFIED | `results.enforce` invalidates; the committed registry has 0 | `test:T40` (2) |
| T00 | T29–T40 executed as gates; the full suite passes with nothing skipped | COMPLETE_VERIFIED | All 147 DvP tests and 213 model tests ran | `test:dvp-all` (147 / 0 / 0), `test:model-suite` (213 / 0 / 0) |

## §9 Execution sequence, structure and CLI

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| P0 | Phase 0 gate: continuity, audit, v0 reproduced, no projection dependency | COMPLETE_VERIFIED | `dvp.py audit` and `reproduce-v0` | `rerun:audit`, `rerun:v0`, `test:T29`, `test:T33`, `test:T38` |
| P1 | Phase 1 gate: projection-free completed-game pipeline; T01–T07 and T30–T40 | COMPLETE_VERIFIED | `observations.*`, `provenance.*`, `asof.*` | `rerun:observations`, `audit:checks`, `test:T07`, `test:T40` |
| P2 | Phase 2 gate: reliability lab A00–A12 reproducible | COMPLETE_VERIFIED | `dvp.py reliability` over `lab.*` | `rerun:reliability`, `reliability:experiments` |
| P3 | Phase 3 gate: walk-forward B00–B12, development folds, 2024 validation, candidates committed | COMPLETE_VERIFIED | `dvp.py backtest --stage development` and `validation`. Candidates are frozen in `config/dvp/frozen-candidates.json` | `rerun:development`, `rerun:validation`, `rerun:forecasts-development`, `rerun:forecasts-validation`, `backtest:dev-folds` |
| P4 | Phase 4 gate: frozen manifest, 2025 conditional holdout, labels per position | COMPLETE_VERIFIED | `dvp.py freeze` pins method, config, candidate, audit-output and receipt hashes. `_verify_frozen` checks them all before `--stage holdout` runs | `rerun:holdout-frozen-tree`, `rerun:forecasts-holdout`, `rerun:frozen-tree`, `audit:frozen-outputs`, `frozen:commit-matches` (11 of 11 files), `backtest:decisions` |
| P4P | Phase 4 prospective: 2026 weeks 12–18, frozen before kickoff, scored after the season | PENDING_FUTURE_DATA | Frozen at both levels before the first kickoff (2026-11-26 01:00 UTC): group level in `frozen.json`, Phase C in `frozen-phase-c.json` (06:57 UTC on 11-24). The games haven't been played. Procedure: [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md) | `open:prospective`, `backtest:timeline` |
| P5 | Phase 5: C00–C05 where justified; promotion only with approval | COMPLETE_VERIFIED | `dvp.py sitstart` on hash-checked frozen forecasts, frozen for 2026 | `rerun:sitstart`, `phasec:decision`, `phasec:frozen` |
| P5W | Promotion: the owner's decision on a D/ST production weight (OWN-074) | DEFERRED_APPROVAL | The owner decides, after the prospective window. Nothing is wired: `feature_specs` is byte-identical to v0's pin | `open:owner-weight` |
| G01 | Repository structure, adapted | COMPLETE_VERIFIED | `scripts/model/dvp.py` (CLI), `config/dvp/` (configs and freezes), `arbit_model/dvp/` (pure functions), `libs/arbit-model/tests/test_dvp_*.py`, `docs/research/dvp/`, `artifacts/dvp/<run>/` (git-ignored) | `cli:commands`, `deliverable:5` |
| G02 | CLI contracts: audit, reproduce-v0, reliability, backtest × 3, report; pytest | COMPLETE_VERIFIED | Plus freeze, registry, sitstart and verify. JSON configs in place of YAML | `cli:commands`, `rerun:steps` |
| G03 | The holdout requires a frozen, verified manifest | COMPLETE_VERIFIED | `walkforward.check_stage` and `dvp._verify_frozen`. From any tree whose files differ from the frozen hashes, the holdout refuses | `rerun:holdout-refused-here` (exit 1, receipt untouched), `test:T18`, `config:spec-keys` |
| G04 | Verify-only mode | COMPLETE_VERIFIED | `dvp.py verify` writes nothing but its receipt | `verify:passed`, `rerun:verify` |
| G05 | Atomic writes and idempotent reruns | COMPLETE_VERIFIED | `write_json` and `write_forecasts` write a temporary file, then replace. Reruns within 10⁻⁹ leave the file alone; different forecasts refuse; development never rewrites frozen candidates (R-075) | `rerun:forecasts-development`, `rerun:forecasts-validation`, `rerun:committed-run-unchanged`, `test:T27` |
| G06 | Dry-run and resume modes | COMPLETE_VERIFIED | The specification asks for dry-run, verify-only and resume modes "when appropriate". Verify-only modes exist (`dvp.py verify`, `dvp_prospective.py verify`, this audit's `check`). Long runs resume: the simulation suite skips recorded repetitions, and the prospective sweep recovers interrupted archives. The historical stages take 0.5–75 seconds and write idempotently, and this audit reruns them on scratch copies, which is the dry run they need. Dry-run flags on those stages would add nothing, so that is the judgement recorded (final directive F2) | `open:modes` (no `--dry-run` or `--resume`; stage times recorded) |

## §10 Config and result schema

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| F01 | Explicit config with the specification's keys | COMPLETE_VERIFIED | `config/dvp/base.json` has the specification's keys and values: lineage policy, as-of policy, split, seeds, `holdout_requires_frozen_manifest: true`, `write_to_production: false` | `config:spec-keys` (no wrong values) |
| F02 | Every experiment record carries the §10 fields | COMPLETE_VERIFIED | `results.FIELDS`, written by `dvp.py registry` | `registry:complete` |
| F03 | Assertions fail if an external projected-point dependency is detected | COMPLETE_VERIFIED | `results.enforce` sets INVALID and withdraws the decision | `test:T40`, `receipts:no-projection` |

## §11 Reports, visuals and handoff

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| O01 | README / RUNBOOK | COMPLETE_VERIFIED | [README.md](README.md): setup, provenance, commands, runtime, offline behavior | `deliverable:1` |
| O02 | DATA_DICTIONARY, DATA_QUALITY, SOURCE_PROVENANCE | COMPLETE_VERIFIED | Three documents | `deliverable:2` |
| O03 | METHODOLOGY | COMPLETE_VERIFIED | Hypotheses, formulas and predeclared metrics | `deliverable:3` |
| O04 | M3-3_CONTINUITY and V0_REPRODUCTION | COMPLETE_VERIFIED | Plus `continuity-manifest.json` and `v0-reproduction.json` | `deliverable:4` |
| O05 | EXPERIMENT_REGISTRY and machine-readable config and results | COMPLETE_VERIFIED | `experiment-registry.json` (the specification's RESULTS.json) and `config/dvp/*.json` | `deliverable:5` |
| O06 | RELIABILITY_REPORT | COMPLETE_VERIFIED | With `reliability-results.json` | `deliverable:6` |
| O07 | BACKTEST_REPORT | COMPLETE_VERIFIED | With the three stage receipts | `deliverable:7` |
| O08 | MODEL_CARD | COMPLETE_VERIFIED | Scope, uses, limits, fallback, eligibility | `deliverable:8` |
| O09 | DECISIONS, CHANGELOG, HANDOFF | COMPLETE_VERIFIED | The project's decision register, changelog and dated handoffs | `deliverable:9` |
| O10 | FORECASTS, METRICS.csv, RESULTS.json, manifest and plots | COMPLETE_VERIFIED | METRICS.csv; the run manifest; plots for split scatter, k with intervals, lag decay, weight curves, error by season, paired improvement and calibration | `deliverable:10`, `rerun:report-files` (16 files byte-identical) |
| O10F | FORECASTS.parquet per stage, hashed in its receipt | COMPLETE_VERIFIED | `artifacts/dvp/phase1-audit-20261124T024442Z/backtest-<stage>/forecasts.parquet`, git-ignored | `deliverable:forecasts` (3 of 3 match their receipts) |
| O11 | PROJECTION_EXCLUSION_AUDIT and SCORE_FINALITY_AUDIT | COMPLETE_VERIFIED | Both JSON audits | `deliverable:11` |
| Z01 | Before completion: the whole relevant suite, including T29–T40 | COMPLETE_VERIFIED | Ran in this audit | `test:dvp-all`, `test:model-suite` |
| Z02 | Before completion: original M3-3 artifacts unchanged | COMPLETE_VERIFIED | Hashes against the continuity manifest | `v0:bytes`, `verify:passed` |
| Z03 | Before completion: reproduce from the pinned configuration | COMPLETE_VERIFIED | Every stage rerun, with the report and registry regenerated | `rerun:steps`, `rerun:report-files`, `rerun:registry`, `rerun:config-freeze-only-added` |
| Z04 | Before completion: inspect an independently drawn sample for sign, units and joins | COMPLETE_VERIFIED | `verify` draws six joined forecasts per stage. BACKTEST_REPORT reads them out | `verify:sample` (6 per stage), `verify:passed` |
| Z05 | Before completion: per-position conclusion table with the specified columns | COMPLETE_VERIFIED | [MODEL_CARD.md](MODEL_CARD.md#conclusions-by-position) | `docs:conclusions` (6 rows) |
| Z06 | Before completion: report provenance, finality, zero projections and holdout status | COMPLETE_VERIFIED | The model card's integrity flags | `docs:conclusions`, `provenance:passed`, `finality:recorded`, `backtest:holdout-status` |

## §12 Final decision logic

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| L01 | v0 discovered and preserved? Yes | COMPLETE_VERIFIED | Continuity manifest | `v0:bytes`, `test:T29` |
| L02 | Inputs canonical, completed, point-in-time, projection-free? Yes | COMPLETE_VERIFIED | Audit, finality and provenance | `provenance:passed`, `finality:recorded`, `audit:checks` |
| L03 | v0 reproducible? Yes | COMPLETE_VERIFIED | Exact and independent | `v0:reproduced`, `rerun:v0` |
| L04 | Reliability and uncertainty estimated; forward test run even where the signal is weak | COMPLETE_VERIFIED | Every group went forward, not only D/ST | `reliability:a05`, `backtest:variants` |
| L05 | Does the forward comparison help? NOT_USEFUL / INCONCLUSIVE → production effect 0 | COMPLETE_VERIFIED | QB INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL; their DvP influence stays 0 | `backtest:decisions`, `open:owner-weight` |
| L06 | Robust to eras, perturbations, coverage, leakage? → PROMISING at team-position level | COMPLETE_VERIFIED | D/ST: A10 robustness, T28, common rows, leakage tests | `registry:A10`, `test:T28`, `test:T19`, `backtest:decisions` |
| L07 | Player A/B improves start/sit? → recommend controlled integration after approval | COMPLETE_VERIFIED | Phase C PROMISING. The recommendation goes to the owner as P4P then P5W | `phasec:decision`, `open:owner-weight` |
| L08 | 2025 status labeled accurately | COMPLETE_VERIFIED | CONDITIONALLY_HELD_OUT, with its exposure stated | `backtest:holdout-status` |

## §13 Caveats

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| W01 | 32 teams × 10 seasons are not 320 independent units | COMPLETE_VERIFIED | Season-cluster intervals are the ones reported; they are wider than unit intervals | `test:T13`, `v0:validated` |
| W02 | v0 used 2025: never called untouched; no 2025-derived parameters | COMPLETE_VERIFIED | Fold parameters come only from seasons before the one forecast | `backtest:holdout-status`, `test:T18` |
| W03 | v0's same-season adjustment is retrospective only | COMPLETE_VERIFIED | Backtests use point-in-time residuals (B02, B03) | `test:T17`, `registry:B02` |
| W04 | Only actuals available by each cutoff inform forecasts; labels are separate | COMPLETE_VERIFIED | Feature and label views | `test:T36`, `test:T15` |
| W05 | Odd/even can hide a midseason change | COMPLETE_VERIFIED | A06 chronological tests: QB drifts | `test:T23`, `registry:A06` |
| W06 | w(8) is within-DvP shrinkage, not a model weight | COMPLETE_VERIFIED | Model card | `docs:conclusions` |
| W07 | Group totals measure matchup context, not a player's share | COMPLETE_VERIFIED | C01 allocates by share; for D/ST the share is 1 | `registry:C01` |
| W08 | A null group result doesn't exclude player-level signals; repeatability isn't usefulness | COMPLETE_VERIFIED | Phase A and Phase B are reported apart; the model card says not running Phase C for QB–K is the gate, not a finding about players | `docs:conclusions`, `registry:A05`, `backtest:decisions` |
| W09 | Each position evaluated independently; WR k never reused | COMPLETE_VERIFIED | Every k is fit per position and per fold | `reliability:a05`, `backtest:dev-folds` |
| W10 | Source availability through 2025 verified; canonical data take precedence | COMPLETE_VERIFIED | All 10 seasons reconcile from the canonical store | `audit:seasons`, `finality:recorded` |
| W11 | Stat corrections: final revisions only, limitation reported | COMPLETE_VERIFIED | SCORE_FINALITY_AUDIT and A12 | `finality:recorded`, `registry:A12` |
| W12 | No production merge from correlations; only confirmatory incremental value | COMPLETE_VERIFIED | Nothing is promoted; eligibility needs P4P and P5W | `open:owner-weight`, `docs:status-vocabulary` |

## Open items

None counts as complete. Each one's state is proven by an evidence check (the audit's evidence rule): an item claimed short of completion without such a check is FAILED.

| Item | Status | Why | What closes it |
| --- | --- | --- | --- |
| P4P prospective 2026 weeks 12–18 | PENDING_FUTURE_DATA | The games haven't been played. Collection is operational and verified (P4P-INFRA): timer, gate, archive, external commitments | After the regular season: the frozen rules on a COMPLETE window (amendment 1) |
| C05L-2026-PRO league-constrained weeks 12–18 | PENDING_FUTURE_DATA | Captured at each forecast with observed availability (C05L-2026-PRO-INFRA) | Descriptive evaluation after the season |
| P5W D/ST production weight | DEFERRED_APPROVAL | Approval is the owner's (OWN-074), after P4P and an integrated-model test (research eligibility registry) | The owner's decision |
| C05L-HIST, C03 | NOT_APPLICABLE | FFA began in 2026 (OWN-076); Phase C is D/ST-only | — |

## Owner audit Phase B: FFA 2026 data and league-constrained evaluation

The owner's Phase B requirements ([AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md](AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md)), TASK-20261124-009. Details: [FFA 2026 data inventory](../FFA_2026_DATA_INVENTORY.md) and [C05L](LEAGUE_CONSTRAINED_2026.md).

| ID | Plan action | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| PB0 | B0: 2026 is FFA's inaugural season, recorded in the owner decisions, source docs, knowledge base and research audit | COMPLETE_VERIFIED | OWN-076 in the decision register, SRC-39 in the source register, the inventory's clarification, and the agent knowledge base | `owner:inaugural-season` |
| PB3 | B1–B3: verified ESPN capability inventory and 2026 coverage, reusing the existing integration | COMPLETE_VERIFIED | `scripts/model/ffa_2026_inventory.py` reads Arbit's stored league records read-only. With `--live` it re-verifies through `scoring_audit.audit_scoring` and `league_history.fetch_transactions` (`EspnClient(EspnTransport())`; nothing stored). Periods 1–11: lineups reconciled 8/8 each; transactions equal to ESPN's (4 next-week lineup moves paged with period 8 explained) | `ffa2026:inventory`, `ffa2026:live-verification` (88/88 lineups, 0 missing, 0 status changes) |
| PB4 | B4: lineups, rosters, statistics and transactions validated | COMPLETE_VERIFIED | Slots, FLEX eligibility and IR within limits; starter totals equal the official matchup totals. Only weekly actual stat blocks are stored, never projections. Trades, waiver outcomes and timestamps classified; IDs unique; no duplicates; 0 revisions observed | `ffa2026:validation` |
| PB5 | B5: 2026 ownership and availability reconstructed and verified, never from current ownership | COMPLETE_VERIFIED | `arbit_model.ffa_history.replay` (draft + 260 executed adds and drops) equals every captured period roster (11/11) and every daily snapshot (14/14). Availability classes from drops and the 24-hour waiver hold | `ffa2026:ownership-replay` |
| PB7 | B7: deliverables | COMPLETE_VERIFIED | Inventory, coverage matrix, eligibility and temporal classes, retrieval report, exploratory results, C05L dispositions, limitations, downstream capabilities | `ffa2026:deliverables` |

B6 (C05L) is in the §5 table: C05L-HIST, C05L-2026-EXP and C05L-2026-PRO. B8's completion condition is met: the capabilities and coverage are verified, the achievable league-constrained experiment ran, and the limitations are documented.

## Final directive: reconciled requirements (remediation 7)

The owner's [final directive](M3-3_AUDIT_REMEDIATION_AND_COMPLETION_DIRECTIVE_FINAL.md) adds these requirements to the inventory above. They keep their directive IDs. Each is proven by behaviour: a rerun from pinned inputs compared with its receipt, the real function called on constructed cases, or the live archive and timer inspected. A flag or file's existence is never enough. The checks are in [`dvp_plan_audit_directive.py`](../../../scripts/model/dvp_plan_audit_directive.py).

| ID | Requirement | Status | Logic | Proof |
| --- | --- | --- | --- | --- |
| AUD-01 | The 2026 confirmation is truly prospective | COMPLETE_VERIFIED | Archive before kickoff, external commitment, completion gate, frozen method verified by hash | `aud01c:gate`, `aud01a:evidence`, `dec:frozen-unchanged` |
| AUD-01a | External archival evidence | COMPLETE_VERIFIED | Every prospective archive has a verified commitment on `research-evidence/dvp-prospective` timestamped by GitHub before its cutoff; `dvp_prospective.py verify` finds no problem | `aud01a:evidence` |
| AUD-01b | Data readiness per game | COMPLETE_VERIFIED | `window.game_readiness` on week 12's archived inputs is ready at its forecast time; removing a game's cells blocks with DATA_INTEGRITY_FAILURE | `aud01b:readiness` |
| AUD-01c | Complete prospective window | COMPLETE_VERIFIED | Eight cases on the real gate: complete; first game only; labels missing; a missed week; a retrospective for a missed week; a commitment after the cutoff; an integrity failure; a subset | `aud01c:gate` |
| AUD-01d | Archival transaction integrity | COMPLETE_VERIFIED | Crashes before and after the rename recover (staging removed; archive recovered); after the cutoff, missed-unproven; a concurrent run refused | `aud01d:archive` |
| AUD-02 | Opportunity volume and efficiency | COMPLETE_VERIFIED | Exploratory v3 rerun from scratch equals its receipt (Parquet byte hashes and later-added fields allowed) | `rerun:explore-v3` |
| AUD-03 | Rolling windows and split-half k | COMPLETE_VERIFIED | Exploratory v2 rerun equals its receipt, no committed value removed or changed | `rerun:explore-v2` |
| AUD-05 | Decoupled stages reproduce v1 on valid rows | COMPLETE_VERIFIED | The same rerun: v1 reproduced on valid rows | `rerun:explore-v2` |
| AUD-04 | Row contract and provenance | COMPLETE_VERIFIED | Projection exclusion audit; the code scan over every DvP file finds no projection or provider-league reader | `provenance:passed`, `code:no-projection` |
| AUD-06 | Simulation suite | COMPLETE_VERIFIED | Every declared scenario ran with no failure; a deterministic sample of every experiment and scenario reruns identically; the receipt regenerates from raw results | `aud06:acceptance`, `rerun:simulation-sample`, `rerun:simulation-summary` |
| AUD-07 | Threshold interpretation and sensitivity | COMPLETE_VERIFIED | The 1% grid row reproduces every frozen label; thresholds unchanged; the analysis reruns identically | `aud07:frozen-thresholds`, `rerun:thresholds` |
| PB-AUD-01 | Live content reconciliation | COMPLETE_VERIFIED | Re-read through the guarded client: every stored transaction content-equal and located; lineups equal in their historical fields. New live records are reported as current-source changes | `pb01:content` |
| PB-AUD-02 | Fail-closed ownership replay | COMPLETE_VERIFIED | An executed trade and a waiver without a processing time are refused; the replay equals every archived snapshot | `pb02:fail-closed` |
| PB-AUD-03 | Availability validated | COMPLETE_VERIFIED | Rule v2 passed its predeclared holdout test; cutoff classes VERIFIED or RECONSTRUCTED | `pb03:availability` |
| PB-AUD-04 | All-week bootstrap | COMPLETE_VERIFIED | Every evaluated week is a block, zero-change weeks 7 and 8 included | `pb04:all-weeks` |
| PB-AUD-05 | Feasibility and collisions | COMPLETE_VERIFIED | Every streaming decision has a feasibility class; collisions recorded | `pb05:feasibility` |
| PB-AUD-06 | Exact eligible sets | COMPLETE_VERIFIED | Every claimable option was held or a free agent; managers split | `pb06:eligible-options` |
| PB-AUD-07 | Observed availability at decision time | COMPLETE_VERIFIED | Captures chained, with 32 units, 8 teams and ESPN's states; week 12's supplement | `pb07:capture` |
| PB-AUD-08 | Immutable league inputs | COMPLETE_VERIFIED | The bundle matches its manifest file by file; the corrected evaluation reruns from it to an identical receipt without the live database | `pb08:pinned`, `rerun:league-v2` |
| PB-B1B2 | Eligible ESPN data through the existing integration | COMPLETE_VERIFIED | Content-level re-read through the existing guarded client; no projection import | `pb01:content`, `code:no-projection` |
| PB-B6 | C05L split | COMPLETE_VERIFIED | HIST not applicable (OWN-076); 2026 v2 reproduces | `rerun:league-v2`, `owner:inaugural-season` |
| PB-B8 | Prohibitions | COMPLETE_VERIFIED | No projection dependency; nothing production-eligible; every receipt records 0 forbidden dependencies | `code:no-projection`, `elig:registry`, `receipts:no-projection` |
| P4P-INFRA | Prospective collection operational | COMPLETE_VERIFIED | Timer enabled, bounded, last run OK within 13 hours, retires only when done; gate, archive and evidence verified | `timer:operational`, `timer:retires`, `aud01a:evidence`, `aud01c:gate`, `aud01d:archive` |
| C05L-2026-PRO-INFRA | League collection for weeks 12–18 | COMPLETE_VERIFIED | Decision-time captures with observed availability | `pb07:capture` |
| DEC-01 | Inaugural season | COMPLETE_VERIFIED | OWN-076 recorded | `owner:inaugural-season` |
| DEC-02 | Research timer | COMPLETE_VERIFIED | Installed, bounded, retiring | `timer:operational`, `timer:retires` |
| DEC-03 | Frozen methodology preserved | COMPLETE_VERIFIED | Frozen hashes verified; original prospective declaration unchanged; week-12 archive intact; thresholds unchanged | `dec:frozen-unchanged`, `aud07:frozen-thresholds` |
| DEC-04 | Research inputs preserved; versioning deferred | COMPLETE_VERIFIED | Pinned bundle verified | `pb08:pinned` |
| DEC-05 | Unsupported ownership changes refused | COMPLETE_VERIFIED | Fail closed | `pb02:fail-closed` |
| DEC-06 | Realistic decision sets | COMPLETE_VERIFIED | Validated availability; only held or free-agent options | `pb03:availability`, `pb06:eligible-options` |
| DEC-07 | B06 kept as a candidate; no production influence | COMPLETE_VERIFIED | Registry: PROMISING_HISTORICAL_CANDIDATE, not production-eligible; the gate refuses it | `elig:registry` |
| DEC-08 | AUD-06 and AUD-07 executed | COMPLETE_VERIFIED | As above | `aud06:acceptance`, `rerun:thresholds` |
| DEC-09 | Remediation 7 and eligibility | COMPLETE_VERIFIED | This audit, its negative controls, the registry and every finding closed | `elig:registry`, `findings:reconciled` |
| DEC-10 | Scope control | COMPLETE_VERIFIED | Leads recorded as exploratory entries, not expanded | `elig:registry` |
| ELIG | Research eligibility registry and gate | COMPLETE_VERIFIED | Loads, classifies as directed, nothing production-eligible, production refusals | `elig:registry` |
| FINDINGS | Every external finding reconciled | COMPLETE_VERIFIED | Every finding has disposition, reasoning, evidence and closure ([register](audit-findings.json)) | `findings:reconciled` |

## Negative controls (§12 F5)

The audit is only as good as its ability to fail. Each control plants one defect, in a scratch copy, a patched function, or a constructed item, and runs the check that should catch it. The audit PASSES only if every control is detected (receipt `negativeControls`).

| Planted defect | Caught by |
| --- | --- |
| A required estimator variant removed from the development receipt | `backtest:variants` |
| A position removed from a stage | `backtest:variants` |
| An experiment marked not executed | `registry:complete` |
| A required test skipped | `test:T26` |
| A stale receipt (a reliability value changed) | `rerun:reliability` |
| A frozen artifact modified (its hash differs) | `audit:frozen-outputs` |
| A file importing a provider projection added to the scan | `code:no-projection` |
| An observation row with a provider source type | `audit:observation-lineage` |
| Historical ownership disagreeing with snapshots | `pb02:fail-closed` |
| An availability state reclassified | `rerun:league-v2` |
| A waiver unit offered as a claimable option | `pb06:eligible-options` |
| Zero-change weeks dropped from the bootstrap | `pb04:all-weeks` |
| A pinned league input file missing | `pb08:pinned` |
| A week marked complete when only one game is final | `aud01c:gate` |
| A missed forecast treated as prospective | `aud01c:gate` |
| An executed trade silently ignored by the replay | `pb02:fail-closed` |
| A blocked requirement with no evidence check | the evidence rule in `evaluate` |
| A research factor marked production-eligible without approvals | `elig:registry` |

## Corrections made by this audit

- **Stale audit run IDs.** [DATA_QUALITY.md](DATA_QUALITY.md) and [V0_REPRODUCTION.md](V0_REPRODUCTION.md) named audit run `phase1-audit-20261124T021910Z` (code `bc414a0`), but their receipts come from `phase1-audit-20261124T024442Z` (code `3a1fe11`). Every later stage reads that run. The two runs built identical observation tables (31,668 rows, compared after sorting), so no number changes. Both documents now name the right run.
- **The project's next action** still said to merge PR #12, which is merged. It is now current ([status](../../project/status.md)).

## Reproduce this audit

From a worktree of this repository, with the main checkout's data and database:

```bash
git worktree add --detach <frozen-tree> 165d140      # the holdout's code
uv run python scripts/model/dvp_plan_audit.py rerun \
  --main <main checkout> --run <main checkout>/artifacts/dvp/phase1-audit-20261124T024442Z \
  --frozen-tree <frozen-tree> --scratch <empty directory>
uv run python scripts/model/dvp_plan_audit.py check --scratch <same directory>
# writes docs/research/dvp/plan-audit-receipt.json; exits 1 if any check fails
```

`rerun` takes about 2.5 minutes. It writes only inside the scratch directory, and it proves that by hashing the committed run and `config/dvp` before and after. `libs/arbit-model/tests/test_dvp_plan_audit.py` keeps the catalog complete and this document consistent with the receipt.
