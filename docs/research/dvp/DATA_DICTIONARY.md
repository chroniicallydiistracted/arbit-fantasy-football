# M3-3 DvP data dictionary

## `observations.parquet` (`defense_game_position`)

One row per completed regular-season team-game and position group. That is 5,278 team-games × 6 groups = 31,668 rows for 2016–2025. Built by `arbit_model.dvp.observations`.

| Column | Type | Meaning |
| --- | --- | --- |
| `game_id` | string | nflverse game ID |
| `season`, `week` | int | NFL season and week (regular season only) |
| `kickoff` | datetime UTC | The schedule's kickoff (Eastern time converted) |
| `available_at` | datetime UTC | When the game's FFA actuals count as known: 12:00 UTC the day after the game day (statistics rule, retrospective) |
| `position` | string | QB, RB, WR, TE, K or DST |
| `offense` | string | Franchise code of the team whose players scored, or, for DST, the offense that conceded |
| `defense` | string | Franchise code of the opposing team: the defense that allowed, or, for DST, the D/ST that scored |
| `unit` | string | Whose tendency the row measures: `defense` for QB–K, `offense` for DST |
| `points` | float | FFA points (the canonical actuals, summed unrounded). Null unless `status` is `valid` |
| `points_partial` | float | The sum of the scored lines, kept for inspection when a cell is not valid |
| `status` | string | `valid`, `missing_coverage` (no target rows for the team-game), `invalid_refused_line`, `invalid_duplicate_line` or `missing_dst_line` |
| `lines` | int | Statistics lines in the cell (DST: 1 if the opposing D/ST line exists) |
| `refused_lines` | int | Lines the scorer refused |
| `source_id` | string | `ffa_targets.athlete` or `ffa_targets.defense` |
| `scoring_hash` | string | The rules the points were scored with |
| `source_type` | string | `FFA_ACTUAL_FINAL` |
| `observed_or_generated` | string | `observed` |
| `finality_basis` | string | The availability rule and that values are final revisions |

**Franchise codes:** OAK → LV, SD → LAC, STL → LA, the codes nflverse statistics use. The schedule decides who played whom; a target row's own opponent is only compared.

## `schedule_games.parquet`

Every scheduled 2016–2025 regular-season game:
- `game_id`, `season`, `week`;
- `home`, `away` as franchise codes, and `home_code`, `away_code` as the schedule's codes;
- `home_score`, `away_score`, `kickoff`, `available_at`;
- `status`: `completed`, or `not_completed` when a score is missing.

## Views (`arbit_model.dvp.asof`)

| View | Contents |
| --- | --- |
| `FeatureView(cutoff, mode, frame)` | Observation rows with `available_at ≤ cutoff`, stamped `feature_as_of = cutoff`. `mode` is `pre_first_game_of_nfl_week` (default) or `per_game` |
| `LabelView(frame)` | The target games' rows |
| `FrozenForecasts(frozen_at, frame)` | Keys (`game_id`, `offense`, `position`), `feature_as_of` and forecast columns. Never `points`, `points_partial` or `status` |

`evaluation_join` is the only place forecasts meet labels.

## Receipts in this folder

| File | What it holds |
| --- | --- |
| `audit-receipt.json` | Checks, reconciliation, cell status, anomalies, examples, run manifest |
| `PROJECTION_EXCLUSION_AUDIT.json` | Admitted sources, dropped columns, code scan, forbidden inventory, dependency count |
| `SCORE_FINALITY_AUDIT.json` | Per-season completion, when Arbit first read each input, the availability rule and its limitation |
| `continuity-manifest.json` | v0's files and hashes, commit, constants and consumers |
| `v0-reproduction.json` | Exact rerun diff, independent recompute, k arithmetic, the `v0-validated` results with intervals |
| `experiment-registry.json` | Every M3-3 experiment in the §10 record format |
| `reliability-results.json` | Phase 2 results by experiment (A00, A02–A10, A12) and position group, with seeds, replicate counts, the audit run and the code commit |
| `plots/*.svg` | The reliability plots, written by the lab (deterministic: the same results give the same bytes) |

## Phase 2 run artifacts (`artifacts/dvp/<audit run>/reliability/`, ignored by git)

| File | Contents |
| --- | --- |
| `null-<group>-<raw or adjusted>.parquet` | The 1,000 permutation-null correlations behind A08 |

## Phase 3 outputs

| File | Contents |
| --- | --- |
| `backtest-development.json`, `backtest-validation.json` | Per position: every variant's RMSE, MAE, mean error, Spearman, and change against B00 with a block-bootstrap interval; calibration deciles; the focus variant by season, week bin and opponent games; per-game and slower-availability sensitivity; each fold's parameters; the forecasts' hash |
| `config/dvp/frozen-candidates.json` | The development selection (tuned k and half-life, best DvP variant, candidate per position), frozen before validation |
| `artifacts/dvp/<audit run>/backtest-<stage>/forecasts.parquet` (ignored by git) | Every frozen forecast beside its label: keys, `feature_as_of`, `n_d` (the opponent's games before the cutoff), `b00` … `b09_*`, `points` |
| `plots/backtest-delta.svg` | The best DvP variant against B00 by position and stage |

## Sources added in Phase 2 ([provenance](SOURCE_PROVENANCE.md))

| Source | Type | Use |
| --- | --- | --- |
| `ffa_targets.athlete_contributions`, `ffa_targets.defense_contributions` | FFA_ACTUAL_FINAL | The same target lines with each rule's contribution, for A09 |
| `gamebook.position_points`, `gamebook.dst_points` | FFA_ACTUAL_AS_OF | FFA points by team-game as Arbit held them at a decision time, for A12's correction check |

## Configuration

`config/dvp/base.json` holds the specification's §10 keys, plus:
- `targets_index`: the pinned FFA targets;
- `expected_scoring`: the rule hashes the targets must carry;
- `position_groups`.

Seeds and replicate counts live there: 2,000 replicates, seed 1729.

`config/dvp/reliability.json` holds Phase 2's settings:
- the adjusted measure (`loo_mean`);
- 1,000 random splits and 1,000 permutations;
- the minimum-game, rolling-window and carryover settings;
- the eras and the excluded seasons;
- the vintage season for A12.

It points to `base.json` for the seed, the bootstrap replicates and the targets.
