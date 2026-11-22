# ADR-007: What the Model may know before each game

Status: Proposed · 2026-11-09 · Awaiting owner acceptance. Settles the M3 part of Q-005. Under [ADR-006](006-model-architecture.md) (accepted, OWN-062), this is adopted before any feature is used in a backtest.

## Context

A backtest is honest only if every input is something the Model could have read before the game it projects. nflverse files are current revisions: a file's timestamp describes when it was rebuilt, not when each row was first published ([nflverse audit](../../research/nflverse-data-audit-2026-10-31.md)). True vintages exist only for what Arbit has observed itself. The worker has imported changed nflverse files every 24 hours since 2026-10-31, and every version is kept.

Evidence:

- **nflverse's published cadence** ([schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html), SRC-03):
  - Play-by-play, player and team statistics: nightly after game days; stat corrections through Thursday.
  - Next Gen Stats: nightly, about 03:00–05:00 ET. Per-season files stop at 2024; the combined file carries 2025 and 2026.
  - Snap counts, PFR advanced stats and FTN charting: checked at 00, 06, 12 and 18 UTC, but their availability depends on the upstream source.
  - Rosters and injuries: daily at 07:00 UTC.
  - Depth charts: daily at 07:00 UTC, timestamped from 2025.
  - Schedules: every five minutes.
  - Participation: after the postseason, from 2023.
- **Measured from Arbit's own imports**, 2026-10-31 to 2026-11-10 ([receipt](../../research/nflverse-vintages-2026-11-10.json), `scripts/model/nflverse_vintages.py`). Imports happen about once a day, recently between 02:00 and 04:00 UTC (none on 2 November), so each lag is bounded by a day.

| Data | When week 8 or 9 first appeared |
| --- | --- |
| Play-by-play, player and team stats, scores | First import after the game: the week 9 Thursday game by the next night; Sunday's early games the same night; Sunday night's game the next night |
| Snap counts, Next Gen Stats | Thursday's game within a day; Sunday's games about a day and a half later |
| FTN charting | Two to three days after the games; Sunday 8 November's games not yet by 10 November |
| PFR advanced stats | Two to four days after the games |
| ESPN QBR | Within a day or two |
| Injury reports | Week 9 rows from Wednesday evening of game week, growing daily through the weekend |
| Expected starting QBs in schedules | Week 10's appeared 5 November, a week before its games |
| Weekly roster rows | Week 9's appeared Thursday evening. Status `INA` came only after each game: 0 at first, 10 after Thursday's game, 171 after Sunday's |
| Depth charts | A new timestamped observation every day |
| Officials | The 2026 file stops at week 1 |

## Decision

1. **One decision time per game: its kickoff.** A projection for a game uses only what nflverse had published, and Arbit had imported, before that kickoff. ESPN locks each player at his game's kickoff.

   The plan named a second time, after inactives. nflverse can't support it: inactive status reaches nflverse only after the game. Inactives come from ESPN's fantasy injury status (OWN-064), which the league lane reads every one to five minutes and stores on every change. In week 9 it switched 39 of 41 inactives to `OUT` 62–86 minutes before kickoff (SRC-33). A status counts for a game only if Arbit read ESPN within 15 minutes before kickoff. Otherwise game-day availability is unknown, never assumed active (R-066). NFL's injury report is read directly at 12:00 and 19:15 Eastern (OWN-063).
2. **Rows have a publication time.** Each family below gets a rule for the earliest time a value counts as known. A value is usable at a decision time only if its publication time is earlier.
3. **Observed vintages win.** From 2026-10-31, the publication time is the first import whose file contains the value. The rules below are the retrospective stand-in for earlier seasons, and each is labeled as such in every backtest report.
4. **Rules by family.** Each is conservative where nflverse's cadence and the measurements disagree.

| Family | Known from (retrospective rule) | Notes |
| --- | --- | --- |
| Schedule context: date, time, home, rest, roof, surface, division, coaches | Before the season | Weather is never an input (R-063) |
| Expected starting QBs | Observed vintages only | Past games show the actual starter. Retrospectively, the expected QB is the previous game's starter, adjusted by the injury report |
| Final scores, play-by-play, player and team statistics, nflfastR outputs | 12:00 UTC the day after the game | Files hold final revisions, so earlier seasons include later stat corrections (small; labeled) |
| Snap counts, Next Gen Stats | 12:00 UTC two days after the game | Measured up to about a day and a half; nflverse describes NGS as nightly |
| PFR advanced stats, ESPN QBR | 00:00 UTC four days after the game | Measured two to four days |
| FTN charting | 00:00 UTC four days after the game | Measured two to three days; Sunday games may miss the following Thursday |
| Injury and practice reports | The first 07:00 UTC publication after the row's `date_modified` | From the first NFL availability capture: when the capture that first holds the value finished (OWN-063) |
| NFL injury report captures: game status and practice | When the capture finished (`observedAt`) | Read at 12:00 and 19:15 Eastern; no history before the first capture |
| ESPN fantasy injury status (OWN-064) | The stored league document's `published_at`; current only within 15 minutes of a read | From 2026-10-31. Earlier seasons have no game-day status; backtests use the injury report and train availability on nflverse's `INA` and snap counts |
| Weekly rosters | Earlier weeks' statuses only; `INA` only after the game | Retrospectively, week *w* uses week *w*−1 statuses. Observed vintages show week *w* rows by Thursday |
| Depth charts from 2025 | The first 07:00 UTC publication after the row's `dt` | |
| Depth charts before 2025 | Before the week's first game | Publication unknown, so labeled. A sensitivity backtest uses the previous week's chart |
| Trades | The day after `trade_date` | |
| Combine; draft picks and capital | The draft (late April) of that year | Career totals in draft picks are excluded (field catalog) |
| Contracts | Seasons after `year_signed`; the signing season only from observed vintages | The table has no signing date |
| Player directory facts: birth date, size, college, draft | Always | Current-snapshot fields are excluded (field catalog) |
| Participation | Seasons after the one it describes | Published after the postseason |
| Officials | Earlier games only | The 2026 file is stale; the current game's crew is not used |

5. **nflfastR model outputs** (EP, EPA, WP, CP, CPOE, xYAC, xpass) come from models fitted on earlier seasons: 2006–2019 as documented, re-released as fastrmodels 2.1.0 in February 2026.
   - **What could leak:** their values in those seasons carry in-sample fit, but it describes play context (down, distance, field position, air yards), not the player outcomes the Model predicts.
   - **Decision:** they are allowed.
   - **Check:** every backtest also reports results without them for seasons inside the fitting window. A large difference blocks their use there.
6. **Stat corrections.** FFA's official points use ESPN's corrections. Targets for earlier seasons use nflverse's final revisions, which already include corrections. From 2026 the observed vintages also record pre-correction values. Live projections use whatever is published at the decision time.
7. **Worker cadence.** The once-a-day import, recently between 02:00 and 04:00 UTC, misses nflverse's 07:00 UTC roster, injury and depth chart update on game days. M3 slice 5 adds an import after 07:00 UTC on game days, so Sunday projections see Saturday's final reports. Until then, a projection records the import it used.
8. **Enforcement.** Feature code receives a decision time and a reader that applies these rules. It never reads a whole current file. The slice 3 test changes every row published after the decision time and requires an identical feature.

## Alternatives

- **Every current file as if it had always been there.** Simple, but it leaks stat corrections, inactives, late depth chart changes and participation, and it would overstate backtest accuracy.
- **Two decision times, before and after inactives.** Not supportable from nflverse alone (see 1).
- **Drop sources without vintages from backtests.** Safe, but it discards injuries, depth charts and rosters before 2026, which are the main availability evidence.

## Consequences

- Backtests are pessimistic where rules are conservative: lagged charting, previous-week roster status, previous-game QB. Reports state the assumption behind each.
- Availability before kickoff rests on injury and practice reports, depth charts and roster moves, not on game-day inactives. Late scratches are a known error source, and backtests report them as a subgroup.
- From 2026 the worker's daily versions are the real record. Slice 5 must keep them, record the import used by every projection, and add the game-day import.

## Validation and adoption

- **Evidence:** the vintage measurement above, recorded in the [slice 2 handoff](../../project/handoffs/2026-11-09-m3-slice2-catalog-targets.md); slice 3's mutation test; and slice 4's sensitivity reports.
- **Adoption:** only by the owner.
- **Related:** Q-005, R-063, R-064, MD-002, MD-004, DATA-002; [ADR-002](002-data-and-identity.md), [ADR-006](006-model-architecture.md).
