# Catch-up after downtime (ENG-052)

When the PC sleeps, shuts down or loses its database, nothing is read. The owner asked for a way to "pull all outstanding data when/if my local machine has been down for some time" (OWN-066, 2026-11-22). This guide covers what comes back by itself, what the catch-up recovers, and what can't be recovered.

The worker does this automatically once it runs again. Nothing needs to be started by hand.

## What each source does after a gap

| Source | After a gap | How |
| --- | --- | --- |
| FFA league: rosters, matchups, settings | Current state only | League lane, first read |
| FFA weekly lineups | Every finished week without a stored lineup | League lane (`league_history.due_lineup_periods`), one week per step |
| FFA transactions | Every period once, then current and previous | League lane (`due_transaction_periods`) |
| NFL teams and schedule | Whole season | League lane, daily |
| nflverse statistics | Current revision of every changed file | Statistics lane, when 24 h have passed |
| NFL injury reports | Whole season on every read, with practice dates | Availability lane, at the next 12:00 or 19:15 Eastern slot |
| ESPN games: scoreboard, summary, plays | Current week only, by the live lane. **Earlier weeks: the catch-up lane** | `catchup` lane |
| NFL API game records | Current week only, by the NFL lane. **Earlier weeks: the catch-up lane** | `catchup` lane |

**Not recoverable** (ADR-007 A4). These stay unknown for the gap, never assumed:
- ESPN's fantasy injury status as it was at the time;
- live play timing;
- nflverse revisions replaced during the gap.

The catch-up recovers what the sources still serve. Keeping the PC awake when data is published (OWN-065) remains the main protection.

## The catch-up lane

The `catchup` lane is in the worker's default lanes.

- **Outstanding games:** regular-season games that kicked off more than 5 hours ago and have no complete stored record. That means unstored, stored before they finished, or missing a summary or plays.
- **Which weeks:** only weeks from the first one Arbit captured. Weeks the live lanes still follow are skipped.
- **One week per step, oldest first:**
  1. ESPN's scoreboard for that week;
  2. the NFL API's full record for each game, which owns the plays when it passes the usual final checks;
  3. ESPN's summary for each game, and ESPN's plays where no NFL record exists.
- **NFL records:** they are added only from the first week the NFL lane read (week 9 of 2026). Earlier weeks keep the ESPN record they were reviewed with.
- **Waits while a slate is active,** checking again every 10 minutes, so it never competes with live reads. Otherwise it checks every 30 minutes, and 30 seconds after a week when more remain.
- **Stops early** when a source asks Arbit to wait (`RATE_LIMITED`, `SOURCE_COOLDOWN`), and retries later.
- **Schedule safety:** a recovered week never becomes the live schedule. `store.game_timings` follows the season's latest week, not the most recently stored one.

Log lines are `"lane": "catchup"` with `week_recovered` or `gaps_recorded`, giving counts and codes only.

## Receipts and the Model's timing rule

Each run appends one JSON line to `receipts.jsonl` under `ARBIT_CATCHUP_PATH` (default `data/catchup`, private, mode 600). A line holds:
- the sources past their stale window when the worker started (from source health, taken before the other lanes refresh it);
- for each recovered game, its kickoff, when Arbit read it, the outcome and which source owns its plays;
- what could not be recovered.

It contains no response bodies or paths.

ADR-007 A1 uses these: a value Arbit fetched late counts from when the source published it, never from the late read, and never from before the gap began. Under A3, gaps come from these receipts, source health, nflverse import history and the injury report capture index.

## Running it yourself

```sh
uv run --env-file .env.local arbit-worker catchup --dry-run    # what is outstanding; reads nothing
uv run --env-file .env.local arbit-worker catchup              # recover outstanding games now
uv run --env-file .env.local arbit-worker catchup --from-period 1   # include weeks before capture began
uv run --env-file .env.local arbit-worker catchup --with-lanes # also the statistics and injury-report steps
```

- **Output:** each command prints counts and periods as JSON. A run that a source stopped exits 1.
- **`--with-lanes`:** runs the same steps as the statistics and availability lanes. Use it only while the worker is stopped, so two imports never overlap.
- **The worker running:** the lane does the same work, so the command is for inspection or for forcing a run.

## Limits

- **Regular season only, periods 1–18.** ESPN numbers playoff games as later scoring periods, and catch-up skips them until a playoff week's shapes are observed (R-059). The live lanes still follow a current postseason week.
- **Weeks before capture began.** In 2026 that is weeks 1–7. They are pulled only with `--from-period`.
- **Stored but never final.** A game ESPN still lists as not final, such as one postponed, is reported as `not_final` and tried again on the next worker start.
- **Database down.** The lane can't do anything until the database is reachable. The container restarts with Docker (`restart: unless-stopped`, R-029, R-068). After a Windows restart, Docker and WSL must still start.
