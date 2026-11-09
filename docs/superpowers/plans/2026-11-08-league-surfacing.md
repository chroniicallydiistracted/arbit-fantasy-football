# Task: show ESPN league facts correctly and store the league history ESPN offers

Status: verified on a restored copy; release to the running app awaits the owner's approval

- **Requirement IDs:** FO-001, CTX-002, DATA-001, DATA-005, DATA-006, DATA-008, UX-003, ENG-005; groundwork for SC-001, WA-001, TR-001, AR-001/002. Resolves R-054 to R-058 and the transaction part of R-027.
- **Specifications:** [feature experiences](../../product/feature-experiences.md) (Front Office content: team and manager identity, record, opponent, official points with anything else labeled separately, roster and locks); AGENTS.md invariants (unknown is not zero; official ESPN totals and live estimates visibly distinct; one ESPN-to-canonical boundary; every changing source has a supervised lane with cadence and stale limit; open clients refresh without reload).
- **Baseline:** the [surfacing audit](../../project/known-issues.md#espn-league-surfacing-audit-2026-11-08) matched 1,437 served facts with ESPN and found the defects below.
- **Work happens in a separate worktree** (`claude/league-surfacing`). The running worker loads `main`'s tree and the running API rejects unknown document fields, so a half-built change must never reach either before an approved upgrade.

## Scope

1. **Matchup scores (R-054).** ESPN contract keeps `totalPointsLive`, `winner` and `playoffTierType`. The canonical matchup keeps `winner` (`home`/`away`/`tie`/unknown) and `playoff_tier`; each side keeps `official_points` only once ESPN has decided the matchup, and `live_points` from `totalPointsLive`. Before any starter's game has begun the live total is unknown, not zero. A matchup becoming final is not a correction. Front Office shows the official total labeled Official, otherwise the live total labeled Live, otherwise a dash.
2. **Weekly lineups (R-055).** One ESPN read per completed scoring period (`mSettings`, `mStatus`, `mRoster`, `mBoxscore`, `mMatchupScore`) is reconciled with the existing M1c `reconcile_period` and stored only when every lineup matches ESPN's official total. Captures are append-only per period, so a stat correction adds a new capture and keeps the old one. The league lane captures each finished week and re-captures when ESPN's official totals move. Past weeks show that week's lineup and points; unplayed weeks say so.
3. **Plain labels (R-056).** The normalizer maps ESPN injury codes to a canonical designation (`questionable`, `doubtful`, `out`, `injured_reserve`, `suspended`, `probable`, `day_to_day`, `other`), keeping the raw code. The API serves only eligible slots the league uses, in lineup order.
4. **Served but unseen facts (R-057).** Teams carry manager first names and ESPN's transaction counts. The player drawer names the owning team. A league panel shows waiver priority, waiver type and hold, trade deadline, veto votes and playoff format from one shared reader of the stored rules.
5. **League history (R-058, R-027).** Season fantasy points per player in the league document. League transactions are read per scoring period, backfilled once and kept current, stored with canonical team and player identities, and the executed adds, drops and trades appear as recent moves. Proposals, declines and lineup moves are stored but not shown. ESPN projections and ownership stay out (benchmark-only, MD-001).

**Exclusions:** opponent lineups, a team page, any advice, and ESPN projections. Waiver processing hour is not shown, since its time zone is unverified.

## Interfaces

- `arbit_data.espn.contracts`: `MatchupSide.total_points_live`, `Matchup.winner`, `Matchup.playoff_tier_type`, `Team.transaction_counter`, `Transaction`, `TransactionItem`.
- `arbit_data.league`: `MatchupSide.live_points`, `Matchup.winner`, `Matchup.playoff_tier`, `Player.official_season_points`, `Player.injury`, `FantasyTeam.transactions`. All new fields default to unknown, so stored documents still load.
- `arbit_data.league_policy.read_policy(rules)`: lineup slots, waiver, trade and playoff settings from a stored rule version.
- `arbit_data.league_history`: period lineup capture, due-period selection, reads; transaction parse, store and reads.
- Migration `0010_league_history`: `fantasy_lineup_capture`, `fantasy_lineup_entry`, `fantasy_transaction`, `fantasy_transaction_read`.
- `arbit_data.freshness`: `espn.league.lineups` ("FFA weekly lineups") and `espn.league.transactions` ("FFA transactions").
- Worker `LeagueLane`: lineup and transaction steps after the league read, through the shared ESPN pacing gate.
- Member API: `Team.managers`, `Team.transactions`; `FrontOffice.roster_state`, `lineup`, `league`, `recent_moves`; `PlayerFacts.owner`; season strip from ESPN's `winner`.
- Web: Front Office scoreboard, past-week lineup, league panel, recent moves, injury labels, season points; player drawer.

## Acceptance

- Normalizer: undecided matchups have no official total; live total present and labeled; a side with no started game has no live total; decided matchups keep ESPN's total; winner mapping; season points; injury designation; transaction counts. A matchup becoming final is classified as an update, not a correction.
- History: a reconciled period stores one capture; a mismatched period stores nothing and reports a code; an unchanged re-read adds nothing; a moved official total makes the period due again and keeps both captures. Transactions upsert by ESPN ID and only executed adds, drops and trades are listed.
- API: live versus official labeling, null future scores, captured past lineup, `not_captured` and `not_played` states, league policy, owner in the drawer, filtered slots, manager names, recent moves.
- Real data on a restored database copy: backfill weeks 1–8 lineups and every period's transactions from ESPN; every stored week reproduces ESPN's official totals; the surfacing comparison passes again with the new fields; screenshots of the current week, a past week, a future week and the drawer.
- Gates: `make runtime-check`, client lint/typecheck/tests, design lint, generated contracts current, isolated browser scenarios.

## Migration and rollout

Additive migration; downgrade drops the four tables. The first league read after the upgrade republishes once with the new fields. Deployment needs the owner's approval: back up, migrate, publish the API release, restart the worker, outside a game window.

## Evidence and outcome

Implemented as planned, with two changes found on real data. A period's transaction page also lists lineups set for later weeks and a period-0 entry, so the shared client's scope check allows exactly those. A past lineup no longer shows an NFL team, because ESPN's period read gives the player's team at read time. Results and commands are in the [handoff](../../project/handoffs/2026-11-08-league-surfacing.md).
