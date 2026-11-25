# FFA 2026 data inventory: ESPN capabilities, coverage, validation and ownership

Owner audit Phase B (B1–B5, B7; [requirements](dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md)). TASK-20261124-009, 2026-11-25. Receipt: [ffa-2026-inventory.json](ffa-2026-inventory.json), written by `scripts/model/ffa_2026_inventory.py` at commit `e57ebc4`, including a live re-verification.

**2026 is FFA's inaugural season** (OWN-076, the owner's authoritative clarification):
- FFA league history begins with the 2026 draft. No earlier FFA seasons exist to retrieve, and their absence is not a data gap or a blocker.
- Historical NFL seasons 2016–2025 remain fully usable under the current FFA scoring rules.

## Result

- **Every finished 2026 scoring period (1–11) is held in full:**
  - weekly lineups for all 8 teams, reconciled to the official matchup totals;
  - every transaction;
  - the draft, the matchup results and the schedule.
  Nothing completed is missing, so nothing had to be retrieved.
- **A live re-read through Arbit's existing guarded ESPN integration** (no new client, nothing stored) confirmed this on 2026-11-25:
  - all 88 lineups reconcile, with 0 mismatches over 1,221 player-games;
  - ESPN returns exactly the stored transactions for every period, with no status changes. The one exception, period 9, is explained below.
- **2026 ownership at any moment can be rebuilt** from the draft and the executed moves. The replay matches every captured period roster (11 of 11) and every daily archived snapshot (14 of 14), with zero disagreements. Current ownership is never used as history.
- **Availability** (free agent or waivers) is reconstructed from drops and the 24-hour waiver hold. It is directly observed only in archived snapshots (2026-10-31 to 11-10 and from 11-22).

**Corrections under the owner's final directive** (TASK-20261124-011; receipts [ffa-2026-inventory-v2.json](ffa-2026-inventory-v2.json), [league inputs](ffa-2026-league-inputs-v1.json), [league-2026-exploratory-v2.json](dvp/league-2026-exploratory-v2.json)). They qualify the claims above:
- **Content-level live reconciliation (PB-AUD-01):**
  - **Transactions:** all 536 stored transactions are content-equal to ESPN's on 2026-11-25. The comparison covers each record's normalized type, status, period, team, proposed and processed times, related id, and every item's player, teams and slots; it recomputes the same content hash Arbit stored. The union of the 12 pages equals the stored set, and the four FUTURE_ROSTER records are positively located on period 8's page.
  - **Lineups:** all 11 finalized lineups have identical membership, slots, points and positions. The only differences are 1–2 players per period whose NFL team changed after the capture: ESPN reports a player's current team even for a past period (read-time representation, not a revision).
- **Ownership at every snapshot (PB-AUD-02):**
  - The replay equals all 1,522 archived snapshots at each one's own observation time, not only one per day.
  - It now stops on any ownership change it doesn't support, or on a waiver without a processing time; none exists.
  - The draft is validated: 128 picks, no player twice, every team in the league.
- **Availability validated (PB-AUD-03):**
  - The 24/48-hour rule agrees with ESPN's reported states in only 22–29% of unit-moments, because it ignores game locks.
  - Rule v2 agrees in 99.3% of held-out moments (see [ownership and availability](#ownership-and-availability-b5)).
- **Pinned inputs (PB-AUD-08):** the normalized league inputs are pinned as a hashed local bundle. The corrected experiment runs from it alone.

## Capability inventory

Each capability is reached through Arbit's existing integration: `arbit_data.espn` (guarded client, endpoint contracts, transport pacing), the worker's league lanes, and `arbit_data.league_history`. All reads are cookie-free public reads ([API audit](espn-public-api-audit-2026-10-30.md), [endpoint coverage](espn-endpoint-coverage-2026-10-30.md)).

**Eligibility classes:**
- **INPUT:** may feed a model.
- **LABEL:** may be an evaluation outcome.
- **CONSTRAINT:** defines a realistic decision set.
- **RECONCILIATION:** may only be compared against Arbit's own data.
- **FORBIDDEN:** never used.

| Data | ESPN source | Arbit implementation and storage | 2026 coverage | Completeness and reconciliation | Point-in-time limits | Eligibility |
| --- | --- | --- | --- | --- | --- | --- |
| League settings and scoring rules | `mSettings` | League lane → `rule_version` (versioned by hash) | Season | 46 scoring items normalized; scorer proof reconciles every lineup | A rule change creates a new version | CONSTRAINT (roster slots, locks, waivers); scoring config for Arbit's own scorer |
| Teams and members | `mTeam` | League document `teams`, `managers` | 8 teams | Complete | Current state per snapshot | Identity only |
| Current rosters | `mRoster` | `roster_entry` per snapshot; 1,520 snapshots since 2026-10-31 | 2026-10-31 to 11-10, 11-22 onward | Every daily snapshot agrees with the ownership replay | **Current ownership only**, even for a historical period (`HISTORICAL_AVAILABILITY_UNSUPPORTED`). No snapshots 2026-11-11 to 11-21 (database outage, R-068) | CONSTRAINT at the snapshot's time |
| Weekly lineups: starters, bench, IR | `mMatchupScore` / `mBoxscore` `rosterForCurrentScoringPeriod` | `league_history.capture_lineups` → `fantasy_lineup_capture` / `_entry`, stored only if every team reproduces ESPN's official total | Periods 1–11 | 8 of 8 teams per period. Starter totals equal the official matchup totals. Slots, FLEX eligibility and IR are valid | **Finalized** period lineups, captured after the period. Not pregame lineups: those exist only in snapshots from 2026-10-31 | CONSTRAINT (historical rosters); context |
| Weekly actual fantasy points per player | Player stat block `statSourceId 0`, `statSplitTypeId 1` (`appliedTotal`) | `fantasy_lineup_entry.official_points` for rostered players | Periods 1–11 | For D/ST, equal to Arbit's canonical FFA points for all 116 labelled lineup units (9 more were byes) | Read after the period; corrections would add a new capture (none so far) | RECONCILIATION and context. Arbit's canonical scoring stays the label authority |
| Weekly realized NFL statistics per player | Player stat blocks, source 0 | Read by `scoring_audit` to prove the scorer; not stored | Periods 1–11 (live) | 1,221 player-games reconcile | Final values at read time | RECONCILIATION. nflverse stays the statistical source (OWN-061) |
| ESPN projections | Stat blocks with `statSourceId 1` | **Never stored.** Readers keep actual blocks only | — | — | — | **FORBIDDEN** (OWN-061) |
| Matchup results | `mMatchupScore` | League document `matchups` (official points, winner) | 56 scheduled; 44 decided (periods 1–11) | Equal to the lineup starter totals | Final after the period | LABEL context (matchup implications); RECONCILIATION |
| League schedule | Matchup schedule | League document `matchups` | Periods 1–14 regular season | 4 matchups a period, one scoring period each | — | CONSTRAINT |
| Draft results | `mDraftDetail` | League document `draft_picks`; `DRAFT` transactions | 128 picks, 2026-08-30 | Picks equal the draft transactions' players | Fixed | Ownership reconstruction |
| Completed trades | `mTransactions2` | `fantasy_transaction` | Periods 1–12 | **None completed** (2 proposals canceled, 7 declines). Trading is open in season: deadline 2026-12-02, 3 veto votes | Proposals and declines kept separately from execution | CONSTRAINT (none yet) |
| Free-agent adds and drops | `mTransactions2` | `fantasy_transaction` (adds, drops, time made) | Periods 1–12 | 80 executed free-agent adds; drops counted per move | Effective when made | CONSTRAINT; ownership reconstruction |
| Waiver claims | `mTransactions2` | `fantasy_transaction` (status, processed time) | Periods 1–12 | 52 executed, 14 failed (12 invalid player source, 2 roster limit), 7 canceled. Processing time exactly on decided claims | Effective when processed | CONSTRAINT; future waiver research |
| Free-agent and waiver pool | `kona_player_info` (FREEAGENT, WAIVERS), paginated | League reader → snapshot `available` and player `availability` | Snapshots only | Current state only | **Not retrievable historically.** Reconstructed from drops and the waiver hold | CONSTRAINT (reconstructed or snapshot) |
| Positional ratings | `mPositionalRatings` | Wired; not stored | — | — | — | **FORBIDDEN** as a model input: ESPN's own matchup ratings, a provider ranking (DvP specification §2.1) |
| Player news | Site news routes | Wired; not stored | — | — | — | Not a model input |
| NFL schedule and byes | Season pro-team schedules | `nfl_team` bye weeks; the DvP schedule comes from nflverse | Season | — | — | CONSTRAINT context |

## Coverage by scoring period

Weeks are NFL weeks; FFA scoring period p is NFL week p, one week per matchup period (verified: every capture's matchup period equals its scoring period). The preweek cutoff is the week's first kickoff, the DvP forecasts' decision time.

| Period | Lineups (captured; reconciled) | Transactions (records; last read) | D/STs at the preweek cutoff: owned / free agent / waivers or uncertain | Ownership at the cutoff | Replay matches the period roster |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-09; 8/8 (129 entries) | 44; 2026-11-09 | 11 / 20 / 1 | Reconstructed | Yes |
| 2 | 2026-11-09; 8/8 | 28; 2026-11-09 | 11 / 20 / 1 | Reconstructed | Yes |
| 3 | 2026-11-09; 8/8 | 53; 2026-11-09 | 11 / 21 / 0 | Reconstructed | Yes |
| 4 | 2026-11-09; 8/8 | 35; 2026-11-09 | 11 / 20 / 1 | Reconstructed | Yes |
| 5 | 2026-11-09; 8/8 | 51; 2026-11-09 | 12 / 18 / 2 | Reconstructed | Yes |
| 6 | 2026-11-09; 8/8 | 64; 2026-11-09 | 11 / 19 / 2 | Reconstructed | Yes |
| 7 | 2026-11-09; 8/8 | 54; 2026-11-09 | 11 / 20 / 1 | Reconstructed | Yes |
| 8 | 2026-11-09; 8/8 | 66; 2026-11-10 | 11 / 20 / 1 | Reconstructed | Yes |
| 9 | 2026-11-10; 8/8 | 40; 2026-11-10 | 12 / 18 / 2 | **Verified by snapshot** (34 minutes before the cutoff; 32 of 32 D/STs, 132 of 132 players) | Yes |
| 10 | 2026-11-22; 8/8 | 61; 2026-11-24 | 11 / 19 / 2 | Reconstructed (snapshot gap) | Yes |
| 11 | 2026-11-24; 8/8 | 39; 2026-11-25 | 12 / 20 / 0 | Reconstructed (snapshot gap) | Yes |
| 12 | In progress | 1 so far | 13 / 19 / 0 at the prospective capture | **Captured** at forecast time (prospective archive) | — |
| 13–14, playoffs | Future | — | — | Captured prospectively for weeks 13–18 | — |

"Reconstructed" ownership is bracketed by verified states: the replay matches the captured roster at the end of every period, and every archived snapshot it can be compared with.

## Validation (B4)

**Lineups and rosters:**
- **Identity:** each capture's season, scoring period and matchup period agree, one scoring period per matchup period. Multi-week matchups are refused at capture (`MULTIWEEK_MATCHUPS_UNSUPPORTED`).
- **Slots:** starters, bench and IR are kept apart. Every period stays within the slot limits (QB 1, RB 2, WR 2, TE 1, FLEX 1, D/ST 1, K 1, bench 7, IR 1). Every FLEX holds an RB, WR or TE.
- **Finalized versus pregame:** the captures are finalized lineups, read after the period. Pregame lineups exist only in snapshots from 2026-10-31.
- **Against matchup results:** each team's starter total equals its official matchup score in all 88 team-periods.
- **Stat corrections:** a changed official total triggers a new, append-only capture (`due_lineup_periods`). None has been needed: one capture per period.

**Player statistics:**
- Only weekly actuals are stored: `statSourceId 0` (actual) with `statSplitTypeId 1` (the scoring period). The season total is a separate league-document field (`official_season_points`), not mixed with weekly points.
- Projections (source 1) are never stored.
- An ambiguous block (two weekly actuals) is refused (`AMBIGUOUS_ACTUAL_POINTS`).
- Arbit's canonical scoring stays authoritative. ESPN's points are reconciliation evidence and are equal wherever compared.

**Transactions:**
- **Trades:** proposals, declines and cancellations are distinct types and statuses, and no trade executed.
- **Waivers:** successful claims (`EXECUTED`) are distinct from failed (`FAILED_*`) and canceled claims.
- **Ownership:** only executed adds and drops change it, and replaying them reproduces every period's roster.
- **Timestamps:** the proposed time is on all 536 records, the first-observed time on all, and the processed time exactly on the 66 decided waiver claims.
- **Duplicates:** none. 536 records have 536 unique ESPN IDs, and no content repeats under another ID.
- **Revisions:** 0 of 536 records changed after Arbit first stored them. But the store updates a changed record in place (content hash and `last_changed_at`), so an earlier version would not be kept. Periods 1–7 were first read on 2026-11-09, so any earlier revision would not have been seen. A version-preserving transaction store is listed below as downstream work. M3-3 doesn't need it: the replay verifies against independent per-period rosters.

**The live re-read's one difference:**
- **What:** four stored period-9 records are not on ESPN's period-9 page today.
- **Why:** they are `FUTURE_ROSTER` lineup moves set on 2026-11-03 for period 9, which ESPN returned on period 8's page (a page carries the next week's lineup moves).
- **Effect:** none on ownership; nothing is missing.

## Ownership and availability (B5)

**Method** (`arbit_model.ffa_history`):
- **The replay:** start from the 128 draft picks and apply the 260 executed adds and drops in effective-time order: 80 free-agent adds, 63 free-agent drops, 52 waiver adds, 43 waiver drops, 22 roster drops.
- **Effective time:** free-agent moves and roster drops take effect when made; waiver claims when processed.
- **Inconsistencies:** a move that contradicts the state (dropping a player not held, adding one already held) is reported. There were none.

**Verification:**
- **Captured rosters:** in all 11 periods, every player and team equals ESPN's captured roster.
- **Every snapshot (final directive):** at each of the 1,522 archived snapshots' own times, the replay equals the snapshot's owners for every rostered player. This replaces the earlier daily check of 14.
- **Week 9:** a snapshot 34 minutes before the cutoff agrees for all 32 D/STs. No D/ST move and no waiver run fall between it and the cutoff, so its states are VERIFIED for that cutoff.
- **Fail closed:** an executed ownership change outside free-agent, waiver and roster adds and drops stops the replay, as does an executed waiver without its processing time. Trades: none executed, so no contract exists to replay them; this is downstream work (DEC-05).

**Classes:**
- **Ownership:**
  - VERIFIED: matches a captured period roster or a snapshot at that moment;
  - RECONSTRUCTED: replayed between verified states;
  - UNKNOWN: there are none.
- **Availability (v1, superseded):** an unrostered player at time T, with the league's 24-hour waiver hold:
  - WAIVERS: dropped less than 24 hours before T;
  - WAIVERS_OR_FREE_AGENT: dropped 24–48 hours before;
  - FREE_AGENT: otherwise.
- **Availability (rule v2, validated):**
  - **Observed timing:** ESPN processes waivers at midnight Pacific on the league's processing days, never Tuesday. All 74 decided claims were processed at 07:00 UTC before the 2026-11-01 clock change and 08:00 UTC after it. The setting's `waiverProcessHour` of 11 is contradicted by every observation.
  - **The rule:**
    - a dropped player is on waivers until the first run at or after the drop plus 24 hours;
    - an unowned player whose game has kicked off is on waivers until the next Wednesday run;
    - otherwise the player is a free agent.
  - **Validated against ESPN's reported state of every unowned D/ST at every snapshot:**

    | Rule | Holdout agreement (7,904 unit-moments) | Holdout falsely claimable | Design agreement (22,425) |
    | --- | --- | --- | --- |
    | v2 | **99.3%** | 54 (0.68%) | 98.9% |
    | v1 | 22.0% | 6,168 | 29.5% |

  - **Remaining errors:**
    - **All 208 over-restrictive cases:** drops inside a waiver run, which ESPN frees at once.
    - **All 90 falsely claimable cases are on Tuesdays,** when ESPN puts every unowned unit on waivers, bye teams included.
    - A refined rule v3 is proposed for validation on future snapshots, not adopted.
  - **Classes at a cutoff:**
    - VERIFIED: a snapshot within 6 hours before the cutoff, with nothing in between (week 9);
    - RECONSTRUCTED: rule v2, which passed its declared holdout test (weeks 1–8, 10–11);
    - ESTIMATED: if a rule fails its test;
    - UNKNOWN: no inputs.
- **Rules applied:** unrostered is never taken to mean claimable, and current ownership is never used for a past moment.

## Retrieval report

| Data | Before this audit | After |
| --- | --- | --- |
| Lineups, periods 1–11 | 11 captures, all reconciled | Unchanged; live re-verification 88 of 88 |
| Transactions, periods 1–12 | 536 records | Unchanged; live re-read equal |
| Matchups, draft, rules | Current league document | Unchanged |
| Earlier FFA seasons | — | Not applicable (OWN-076) |

No completed 2026 period was missing, so no record was newly retrieved. The live checks used `scoring_audit.audit_scoring` and `league_history.fetch_transactions` through `EspnClient(EspnTransport())`, about 22 paced public reads. Nothing was written.

## Genuine limitations

- **Snapshot gap (2026-11-11 to 11-21):** no archived roster or pool snapshot exists, because the database was down. Ownership in weeks 10–11 is reconstructed (verified at period ends), not observed at the cutoff.
- **Historical availability isn't retrievable from ESPN.** It is reconstructed with rule v2 (validated: 99.3% holdout agreement). Rule v2 is over-restrictive for drops made inside a waiver run, which affects three cutoff states in weeks 1–11, none picked by either model, and too permissive on Tuesdays, which affects no Thursday cutoff.
- **Pregame lineups** exist only from 2026-10-31, in snapshots. Captured lineups are finalized.
- **Transaction revisions** made before Arbit's first read, or between reads, are not version-preserved. A production-grade versioning system is deferred (DEC-04). The exact inputs M3-3 used are preserved as the pinned bundle, and a live content re-read on 2026-11-25 found no stored record differing from ESPN's.
- **Stat corrections after a capture** would add a capture; none has occurred.

## Downstream capabilities (for later Arbit slices, not M3-3)

| Capability | What it would support |
| --- | --- |
| Ownership replay (`arbit_model.ffa_history`) for every player, not only D/ST | Waiver and trade research on realistic decision sets |
| Waiver claims with failure reasons (invalid player source, roster limit) | Demand for players; claim-order behavior |
| Free-agent pool with status, from snapshots (and `kona_player_info` live) | Streaming and waiver advice at decision time |
| Captured weekly lineups with bench points | Managers' start/sit regret; lineup-advice evaluation |
| A version-preserving transaction store | Revisions over time. Deferred by the owner (DEC-04); M3-3's inputs are pinned instead |
| Complete trade replay | Ownership through executed trades. Needs an observed executed-trade contract; the replay stops on one until then (DEC-05) |
| Availability rule v3 | Waiver-run drops as immediate free agents, and Tuesday period locks. To validate on future snapshots before any use |
| A competitive waiver and acquisition simulator | Priority, competing claims, multi-week value and drop costs. Outside M3-3 (DEC-06) |
| ESPN percent-owned and draft ranks | Excluded unless the owner decides otherwise: provider popularity and ranking signals |
| ESPN positional ratings | FORBIDDEN as model inputs |

**Reproduce:**

```sh
uv run --env-file <main>/.env.local python scripts/model/ffa_2026_inventory.py --main <main> [--live]
```
