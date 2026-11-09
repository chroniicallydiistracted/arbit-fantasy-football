# Handoff — 2026-11-08 — ESPN league facts as members see them, and league history

## Current state

The owner asked to confirm that ESPN league data is both pulled and shown where it belongs before Model/Scout (M3) starts, then to fix everything the audit found. The audit and the fixes (R-054 to R-058, ENG-050) are done and verified on a restored copy of the database against ESPN.

**Released at the owner's request** ("Commit everything, push to main, and update the webstack, including the worker").
- Commits `a2ebb5e` (this work, built on branch `claude/league-surfacing`) and `486d431` (the Nov 8 restart record and `.github/skills/anti-ui-slop`) are on `main` and pushed.
- At 18:49 (UTC−7), during Sunday Night Football:
  - Database backup `data/backups/2026-11-08/before-upgrade-184906.dump` (82 MB).
  - Migration `0010_league_history` applied.
  - The API switched to release `.superpowers/releases/league-surfacing-2026-11-08/` (source from `486d431`, web built from it). The drop-in `30-release.conf` replaced `30-live-animation-preview.conf`, whose copy is kept in the release folder as `previous-api-dropin.conf` for rollback.
  - `arbit-api` and `arbit-worker` restarted together.
- After the restart, `/health/ready` reported ready, and `:8000` served the release's bundle byte for byte. The worker's live and NFL lanes resumed on the night game (401873050). The league lane republished with the new fields and began backfilling weeks and transactions.
- No tests were rerun for the release, by owner instruction; the verification below is from before it.

## Completed work

**Audit** (before the fixes, against the running app at 01:01 UTC on 2026-11-09): 1,437 served facts matched ESPN with 0 mismatches, and Live's "yours" lists matched in 120 team–game pairs. The defects were presentation and missing history, recorded as R-054 to R-058.

**Fixes** (plan: [league surfacing](../../superpowers/plans/2026-11-08-league-surfacing.md); decision ENG-050):
- **ESPN contract** (`espn/contracts.py`): `totalPointsLive`, `winner`, `playoffTierType`, team `transactionCounter`, and `Transaction`/`TransactionPage`.
- **ESPN client** (`espn/client.py`): a period's transaction page may also carry `FUTURE_ROSTER` entries for later periods and a period-0 `ROSTER` entry, both observed. Any other period is still `SCOPE_MISMATCH`.
- **Canonical document** (`league.py`, `espn/normalize.py`):
  - Matchups: `winner` and `playoff_tier`. `official_points` is set only once ESPN decides the matchup, and `live_points` until then. The live total is unknown before any of that team's starters has a stat line.
  - Players: `official_season_points` and a canonical `injury`.
  - Teams: `transactions` counts.
  - All new fields default to unknown, so stored documents still load.
  - `league_store._changes`: ESPN deciding a matchup is an update, not a correction.
- **Rules reader** (`league_policy.py`): `read_policy(rules)` for lineup slots, waiver type, hold and days, bidding, trade deadline, veto votes, review hours and playoff format.
- **History** (`league_history.py`, migration `0010_league_history`, `schema.py`):
  - Weekly lineup capture, reconciled by `reconcile_period` and append-only.
  - Due-week detection, including moved official totals.
  - Transaction fetch, store and upsert, the backfill schedule and recent moves.
- **Worker** (`daemon.py`): `LeagueLane` runs the lineup and transaction steps after each league read, 20 s apart while catching up. A week that doesn't reconcile waits an hour. Freshness sources `espn.league.lineups` and `espn.league.transactions`. Changes emit `league.updated`.
- **API** (`member_contracts.py`, `member_routes.py`, `fixture.py`):
  - Front Office: `roster_state`, `lineup`, `lineup_captured_at`, `league` and `recent_moves`. `playoff_team_count` and `historical_roster_unavailable` are removed, now carried by `league` and `roster_state`.
  - `Team.managers` and `Team.transactions`. `PlayerFacts.owner`.
  - Eligible slots are limited to the league's. The season strip uses ESPN's `winner`.
  - OpenAPI and generated client types were regenerated.
- **Web** (`FrontOffice.tsx`, `PlayerDrawer.tsx`, `format.ts`, `styles.css`, `api.ts`):
  - Scoreboard: Official versus Live chip with a note, dashes for unknown, a final or awaiting state, and manager names.
  - Lineup table for past weeks. Not-stored and not-played states.
  - Season points column, which hides at phone width.
  - League and recent-moves panels. Manager names in the league table.
  - Drawer: owning team and season points.
  - Plain injury labels. "1 day ago" fixed.

**External state changed:** none on the running app. Read-only ESPN GETs during the audit and verification. Two scratch databases (`arbit_staging_test`, `arbit_browser_fixture`) were created and dropped. Two dev-account sessions were opened and ended (`make dev-account-end` ended the running app's).

## Verification

All commands ran in the worktree.

| Check | Result |
| --- | --- |
| `python3 scripts/validate_foundation.py` | passed |
| `uv run ruff check .` / `uv run ruff format --check .` | passed; 199 files formatted |
| `uv run mypy` | no issues, 107 source files |
| `uv run pytest -q -p no:cacheprovider` | 1,276 passed (includes `test_foundation_references`) |
| `node scripts/validate-contracts.mjs`, `node scripts/web/check-generated.mjs` | passed; OpenAPI and generated TypeScript current |
| `node scripts/web/design-lint.mjs` | passed |
| `node --test scripts/web/static-worker.test.mjs`, `tokens.mjs --check` | 1 passed; tokens current |
| `pnpm --filter @arbit/web lint`, `tsc -b --noEmit`, `vitest run` | 3 known reduced-motion warnings; typecheck passed; 32 passed |
| Playwright, isolated fixture app on :8011 (`arbit_browser_fixture`, scratch build) | 16 passed, including 320–1600 px reflow and reload-free updates |

New tests:
- `tests/integration/test_league_history.py` (15): live versus official, the winner rule, update versus correction, season points and injury, old documents loading, the rules reader, lineup reconcile/store/refuse/re-capture, transactions, the period schedule, the observed future-lineup page, and the lane's backfill, freshness and retry wait.
- One added Front Office test in `test_member_api.py`, plus updated assertions in three existing tests.
- One client scope test in `test_espn_client.py`.
- `apps/web/src/FrontOffice.test.tsx` (3).
- The member browser scenario was updated for the new copy.

**Real data** (restored copy `arbit_staging_test`, migrated to 0010, `arbit-worker run --lanes league` against ESPN during Sunday Night Football):
- Weeks 1–8 lineups stored (129–133 players each). **64 of 64 team-weeks reproduce ESPN's official totals.** No week was left due.
- 435 transactions across all 9 periods (44, 28, 53, 35, 51, 64, 54, 66, 40). The first run exposed the `FUTURE_ROSTER`/period-0 page shape (`SCOPE_MISMATCH` on period 8). After the fix, all sources were healthy.
- Fresh ESPN read versus the new API on :8010: **1,344 facts, 0 mismatches**. That covers records, seeds, waiver order, managers, move counts, ESPN's decision and official totals for every matchup from every team, week 9's live totals and the started-player rule, future weeks with no total, season strip, roster state, past-lineup starter sums, injury designation, season points, slot filtering, league rules and drawer owners.
- Screenshots at 1440 and 390 px: no console errors, no horizontal scroll at 390 px.

**Not run:** `make runtime-check` as one command (its parts ran separately above); remote CI.

## Decisions, issues and limitations

- ENG-050 records the semantics. R-054 to R-058 are fixed in code, pending release. R-027 now covers only player news and positional ratings.
- **R-059:** no executed trade, playoff week or multi-week matchup has happened in FFA yet. Trade display and playoff lineup reads are unproven. A multi-week matchup stops the lineup step with a code instead of guessing.
- A past lineup shows no NFL team. ESPN's period read gives the player's team at read time, which isn't verified as that week's (the column is stored, documented as read-time).
- Per-week ESPN points for unrostered players are not stored. M3 computes weekly FFA points from nflverse through the shared scoring service.
- The memory note that FFA "seeds by total points" was wrong: seeding is by record, and total points only breaks ties. The app always used ESPN's seed.

## Resume here

1. **Rollback, if ever needed:** restore `previous-api-dropin.conf` in place of `30-release.conf`, run `systemctl --user daemon-reload`, and restore the backup dump. Migration 0010 only adds tables.
2. Check that the running app's Front Office shows week 9 as Live during Monday night, and as Official once ESPN closes the week. Week 9's lineup should be captured once the week is decided.
3. Then M3 Model/Scout, which can use `fantasy_lineup_entry` and `fantasy_transaction` as point-in-time FFA history.

[Status](../status.md) · [Decisions](../decision-register.md) · [Known issues](../known-issues.md)
