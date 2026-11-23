# Point-in-time reader audit, 2026-11-23

M3 slice 3a (TASK-20261123-001, ENG-053). The reader returns only what was known before a decision time, under [ADR-007](../architecture/decisions/007-model-availability.md) as amended by the owner (OWN-066). This note records its first run against Arbit's real nflverse history. Receipt: [point-in-time-audit-2026-11-23.json](point-in-time-audit-2026-11-23.json), written by `scripts/model/point_in_time_audit.py`. The run read `arbit_local` and the object store and wrote nothing to either.

## What the reader does

For a file and a decision time T:

- **Held rows.** The version Arbit held just before T supplies its rows, because Arbit had them.
- **Gap rows.** If T falls in a capture gap, or before Arbit's first read, the version read after T can add units it did not hold before. A unit counts only if its known-from time is before T.
- **Known-from.** Say a unit was first held by a version read at t1, and Arbit's previous read was at p:
  - If p is within the 36-hour stale window, known-from is t1, labeled `observed`.
  - Otherwise it is the earlier of t1 and the later of (the unit's own timestamp or its family rule) and p, labeled `source-timestamp` or `retrospective-rule` (A1).
  - `observed` therefore always means a time Arbit read the value. That time is exact while reads were continuous, and an upper bound after a gap.
- **Units** are the rows that move between versions together, so each comes whole from one version:
  - a game's plays or statistics;
  - one player-week's injury report;
  - one team's depth chart snapshot;
  - one trade;
  - a whole season file.
- **Refusals.** The reader refuses:
  - tables without a registered timing rule (for example QBR);
  - fields the catalog doesn't list;
  - fields excluded by policy, unless the read names their gate. Betting lines open only for the Q-014 study (OWN-067).

**Reads and gaps (A3)** come from `dataset_import` (successful checks only) and `dataset_manifest.observed_at`. Every daily run registers its own catalog, so each run leaves one check per file.

## Capture gaps

Every registered 2026 file shows the same gaps under the 36-hour window:

| Gap | Span (UTC) | Cause |
| --- | --- | --- |
| Before the first read | until 2026-10-31 09:14–09:30 | Imports began on 31 October; everything earlier is retrospective |
| 2 November | 2026-11-01 09:58 to 2026-11-03 02:11 (40 h) | No import that day, as ADR-007 recorded |
| R-068 outage | 2026-11-10 03:59 to 2026-11-22 22:45 | The database was down |

## Decision times tested

Four decision times, each the earliest Sunday kickoff of its week:
- 2025 week 11: 14:30 UTC on 2025-11-16;
- 2026 week 9: 14:30 UTC on 2026-11-08;
- 2026 week 10: 14:30 UTC on 2026-11-15;
- 2026 week 11: 18:00 UTC on 2026-11-22.

At all four, 56 table reads returned **no row whose known-from time was at or after its decision time**.

| Decision | What it shows |
| --- | --- |
| 2025 week 11 (before any read) | Everything is timed by rule or the row's own timestamp. Statistics and play-by-play are known through 12:00 UTC on 14 November (Thursday's game). Snaps and Next Gen Stats run through the 15th, and PFR and FTN through 00:00 UTC on the 14th. Depth charts, from their `dt` snapshots, run through 07:00 UTC on game day. Injury reports, which have no `date_modified` in 2025, also run through 07:00 UTC on game day. The 2025 season roster file isn't used until after the season |
| 2026 week 9 (continuous reads) | No gap. Two games' statistics were first held by a read a day after the previous one (`observed`). Weeks 1–8 arrived in the first import and are timed by rule. 663 injury report units and 448 depth chart snapshots are `observed` |
| 2026 week 10 (inside the outage) | The reader admits what nflverse would have published before kickoff although Arbit fetched it 12 days later: Thursday's game statistics (known from 12:00 UTC on 13 November), FTN and PFR for week 9 (00:00 UTC on the 13th), week 10 injury reports (07:00 UTC on the 15th) and depth chart snapshots through the morning of the 15th. Week 10 weekly roster statuses aren't admitted: ADR-007 counts them only after the week's games |
| 2026 week 11 (still inside the outage until 22:45) | 136 of 151 statistics units are timed by rule. The latest is Thursday's game, known from 12:00 UTC on 20 November |

No unit was bounded by a gap's start: nflverse didn't publish any of these rows later than its rule says.

## Findings

1. **Injury reports from 2025 on have no `date_modified`.** The 2020 and 2023 files have it; the 2025 and 2026 files don't. ADR-007's source-timestamp rule therefore covers 2024 and earlier. A newer row holds the week's final report, which comes out by the day before the game, so the reader counts it from 07:00 UTC on game day (`retrospective-rule`). Arbit's own daily vintages give the earlier intra-week reports since 2026-10-31.
2. **Next Gen Stats uses today's team codes for earlier seasons:** `LV` for Oakland, `LAC` for San Diego in 2016, and `LAR` where the schedule has `LA`. The calendar now falls back to the code of the season, and all 15,532 rows are placed. NGS postseason weeks are numbered differently from the schedule (18–23), so those rows, like week 0 season totals, count only after the season.
3. **Four games of officials can't be placed.** The officials file uses old GSIS IDs the schedule doesn't list for the three rescheduled 2021 week 15 games and the cancelled 2022 Buffalo–Cincinnati game. Those 28 rows are never admitted by rule, only from a version Arbit held. Officials are only a candidate input.
4. **Catalog re-review (A2).**
   - Current snapshot values (15 fields) and draft-pick career totals (23) move from `excluded` to the new use `as_imported`: they apply from the import that held them and never to an earlier game.
   - Observed weather (5 fields) moves from `outcome` to `history`.
   - Betting lines stay excluded, now under OWN-067, and the reader opens them only for that study.
   - The other exclusions are policy: OWN-061, the legacy duplicate of the statistics release, play description text, and release tests. A test pins that set.
   - Regenerating the catalog also picked up upstream type changes since 2026-11-10: seven contract text and history columns are now `large_string`, and QBR's `game_week` is now `int32`.
   - The catalog still lists 1,827 fields: 148 pre-game, 722 history, 18 earlier seasons only, 38 as imported, 411 identity, 490 excluded.
5. **Cost.** The whole audit took 34 seconds and peaked at 2.2 GB of memory. Most of both went to the 2026 depth chart file: 827,000 rows in each of 11 versions, placed row by row in Python on first use. Features that read many decision times across many seasons will need placement done in columns rather than per row (slice 3 feature work).

## Tests

- **Model tests,** 20 in `libs/arbit-model/tests/test_point_in_time.py`, on a synthetic daily history with a 12-day gap:
  - held versus gap units;
  - the gap-start bound;
  - labels, refusals, timing for schedules, weather, lines and injuries;
  - franchise codes.
- **Mutation test.** Changing every row published after the decision, adding units and adding a later version leaves the reading identical at five decision times. A companion test shows that changing a unit published before the decision does change the reading.
- **The test catches real mistakes.** Three deliberate breaks each failed tests:
  - dropping the gap-start bound: 1 failure;
  - admitting every row fetched after the decision: 9;
  - ignoring gaps: 6.
- **Integration,** 2 tests in `tests/integration/test_model_point_in_time.py`:
  - versions and reads from PostgreSQL;
  - failed checks are not reads;
  - a column missing from an older version reads as unknown;
  - a decision inside a gap.
