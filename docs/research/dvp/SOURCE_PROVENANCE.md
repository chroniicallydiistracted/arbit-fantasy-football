# M3-3 DvP source provenance and the projection firewall

Specification §2.1, §3.1, T30–T33, T37, T40. Receipt: [PROJECTION_EXCLUSION_AUDIT.json](PROJECTION_EXCLUSION_AUDIT.json). Code: `arbit_model.dvp.provenance`.

**Result:**
- `forbidden_vendor_projection_dependencies = 0` for v0 and for the extension. Status PASSED.
- No ESPN or other provider's projected fantasy points are read, joined, used as priors or used as fallbacks anywhere in the DvP data path.
- Every fantasy point in it is Arbit's own FFA actual, computed from completed-game nflverse statistics under the league's rules.

## The allowlist

A table enters the DvP pipeline only through `admit()`, which fails closed:

| Code | Raised when |
| --- | --- |
| `UNKNOWN_SOURCE` | The source isn't on the allowlist |
| `FORBIDDEN_SOURCE_TYPE` | The source type isn't an input type |
| `MISSING_ANCESTRY` | The source names no ancestry |
| `SCORING_HASH_MISMATCH` | FFA actuals carry rules other than the configured league rules |
| `UNKNOWN_COLUMN` | The source holds any column it isn't known to hold, even one outside the columns read |
| `UNKNOWN_VALUE` | A row has an unexpected basis or season type |

Admission follows lineage, not names. A projection renamed `opponent_expected` is still an unknown column and stops the run (T32).

| Source | Type | Provider | Used columns | Known schema | Ancestry recorded |
| --- | --- | --- | --- | --- | --- |
| `ffa_targets.athlete` | FFA_ACTUAL_FINAL | Arbit | season, week, season_type, game_id, team, opponent (compared only), player_id, position, basis, points, refusal | Format `arbit-ffa-targets-v1` (13 keys, 26 statistic components, unknown, overrides, contributions) | Targets index, season manifest, Parquet digest, rules hash |
| `ffa_targets.defense` | FFA_ACTUAL_FINAL | Arbit | season, week, season_type, game_id, team, opponent, basis, points, refusal | The same plus 7 D/ST statistics | The same |
| `ffa_targets.athlete_contributions`, `ffa_targets.defense_contributions` (Phase 2, A09) | FFA_ACTUAL_FINAL | Arbit | The same keys plus `contributions` (each rule's points) | The same target formats | The same, under the same rules hash |
| `gamebook.position_points`, `gamebook.dst_points` (Phase 2, A12) | FFA_ACTUAL_AS_OF | Arbit | game_id, team, opponent, position, points, refused | The gamebook's fixed columns | The decision time, the point-in-time reader's file versions, the rules hash |
| `nflverse.schedules` | SCHEDULE | nflverse | game_id, season, week, game_type, gameday, gametime, home/away team and score | The nflverse field catalog (`arbit_model.fields`); excluded fields are dropped and recorded | The schedule manifest the targets were built from |

**Dropped on admission:** the schedule's betting-line columns (catalog rule `betting-lines`, OWN-067). A market forecast is not a fantasy projection, but it is gated out of this slice.

**Scoring authority (T30, T37):**
- The targets carry athlete rules `10e938eb…` and D/ST rules `16885a80…`, the rule set in the league's current ESPN settings. The audit re-derives both hashes from the stored rule version.
- Each line's points equal the sum of its per-rule contributions (257,914 lines on the repaired index).
- Separately, slice 2 compared stored 2026 lines with ESPN's actual applied totals: 10,734 of 10,771 agree ([ffa-targets-check-2026-11-10.json](../ffa-targets-check-2026-11-10.json)). That comparison used ESPN's actual blocks only. It is an audit and was never an input.

**What made the targets:**
- **Inputs:** each season's manifest names its nflverse inputs, all from seven families: pbp, players, schedules, snap_counts, stats_player, stats_team and weekly_rosters. None is outside the allowlist.
- **Scoring rules:** the stored league rule version.
- **Builds:**
  - The current index `6ffb62fb…` is the R-072 repair, built on 2026-11-24 from clean commit `9504631`, on exactly the nflverse inputs of `4afbd836…` ([repair](../targets-repair-r072.md)).
  - `4afbd836…`, which v0 ran on, was built on 2026-11-10 from code `de72924` with uncommitted changes.
  - Slice 2's comparison ran on a pinned build of that code, index `994b3018…`.
  - The uncommitted builds are recorded as lineage limitations, not as contamination.

## Code scan (T31)

The scan reads every file that produces or consumes DvP inputs: the DvP package and script, v0 and the signal study, the targets builder, scorer, rules, stat-line adapter, inputs, storage and gamebook. It looks for:
- projection field tokens: `projected_`, `fantasy_points`, ESPN's projection source flag, ffopportunity, DynastyProcess, FantasyPros, expected fantasy points and ECR;
- imports of ESPN or Sleeper readers.

It found nothing. The receipt holds each scanned file's hash. `provenance.py` names those tokens in order to forbid them, so it is the one file left out. T31 also plants a projection and an ESPN import in a scratch file to show the scan catches both.

## Known projections in Arbit, all rejected

| Source | Where | Guard | Decision |
| --- | --- | --- | --- |
| ESPN projected stat blocks | Raw ESPN responses Arbit stores | ESPN readers keep actual blocks only; no DvP source reads ESPN | OWN-061 |
| ESPN draft probabilities and analyst ranks | nflverse misc/espn_draft_* | Catalog rule espn-draft-projections | OWN-061 |
| ffopportunity expected fantasy points | nflverse ff_opportunity | Catalog rule ffopportunity | OWN-061 |
| DynastyProcess and FantasyPros values, ranks and projections | nflverse dynastyprocess | Catalog rule dynastyprocess-values | OWN-061 |
| Generic fantasy points | nflverse weekly statistics | Catalog rule generic-fantasy-points, dropped on admission | OWN-061 |
| Sleeper projections and rankings | arbit_data.sleeper | Not a DvP source; import scan | OWN-061 |
| Betting lines | nflverse schedules and play-by-play | Catalog rule betting-lines, dropped on admission | OWN-067 |

**Results (T40):** every experiment record carries `forbidden_vendor_projection_dependencies`. A nonzero value turns the record `INVALID` and withdraws its decision. The registry check (T40) fails on any such record.
