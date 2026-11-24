# Project Status

**Running now (verified 2026-11-23 18:45 UTC):**
- **Worker:** runs `main` at `e005aa6` (PR #3, merged by the owner at 18:41 UTC) since its restart at about 18:42 UTC. It runs seven lanes: league, live, nfl, nfl_probe, statistics, availability and catchup. Its first NFL discovery linked all 13 week 11 games.
- **Database:** up with `restart: unless-stopped`. 2026 regular-season weeks 1–10 are complete, and week 11 was live.
- **CI on `main`:** green; `main` is protected.
- **On `main` since PR #3:** TASK-20261122-007 to -010 (weather decision and plan, never-captured NFL rule, housekeeping, the Live playback test flake fix). The merged worktree and branches were removed.
- **On `main` since PR #4 (`c41a7d7`, merged 2026-11-23 under the owner's GitHub authorization):** M3 slice 3a, the point-in-time reader (TASK-20261123-001). It runs in no service, so the worker was not restarted.
- **On `main` since PR #5 (`cace69c`):** the columnar reader and timing order (TASK-20261123-002) and game-day availability (TASK-20261123-003).
- **On `main` since PR #6 (`b3c0a9a`, merged 2026-11-23 as the frozen v0 baseline the owner's DvP specification preserves):** M3 slice 3b, team environment and defense against the position (TASK-20261123-004). It runs in no service.
- **On `main` since PR #7 (`9a7c0b1`):** the DvP research, phases 0-1 (TASK-20261123-005 and -006). Offline research; it runs in no service.
- **On `main` since PR #8 (`efff624`):** the R-072 repair and rebuilt FFA targets (TASK-20261123-007). The research store's current pointer names the rebuilt index `6ffb62fb…`; no service reads it.
- **On `main` since PR #9 (`ceba441`):** DvP Phase 2, the reliability lab (TASK-20261124-001).
- **On `main` since PRs #10 and #11 (`cf50b73`):** DvP Phase 3, the walk-forward (TASK-20261124-002), and Phase 4, the holdout and model card (TASK-20261124-003). Offline research.
- **On `main` since PR #12 (`249297c`):** the DvP plan completion (TASK-20261124-004): Phase C for D/ST, T26/T27, verify-only mode and idempotent reruns. Offline research.
- **On `main` since PR #13 (`987212f`):** the DvP plan completion audit and scope document (TASK-20261124-005). Offline research.
- **Stack reloaded 2026-11-24 22:07 UTC** at the owner's request:
  - the worker runs `987212f`;
  - the API serves release `.superpowers/releases/main-2026-11-24` of the same commit;
  - the tunnel was restarted;
  - the database was backed up first, and no migration was pending.
- **Not yet on `main`:** owner audit remediation 1, the DvP prospective harness (TASK-20261124-006, branch `claude/m3-dvp-prospective`). Offline research.

**Owner's independent DvP audit (2026-11-24; [requirements](../research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS.md)):** seven findings, AUD-01 to AUD-07, with remediations 1–7.
- **Remediation 1 (AUD-01), done in TASK-20261124-006 ([procedure](../research/dvp/PROSPECTIVE_2026.md), ENG-063):** the 2026 weeks 12–18 confirmation is now truly prospective. Forecasts are archived before each week's kickoff and evaluated after the games.
  - **The harness:** `scripts/model/dvp_prospective.py`, with the adapter `arbit_model.dvp.shadow`.
  - **Week 12:** archived 2026-11-24 23:12 UTC, 25.8 hours before its cutoff. GitHub recorded the push at 23:13:15.
  - **Weeks 13–18:** they need the six-hourly sweep timer (owner approval to install) or a manual `sweep` in each week's window. The first is week 13, from 2026-12-01 12:00 to 12-04 01:15 UTC.
- **Remediations 2–7 are open:** opportunity and efficiency (A09, B07); rolling windows and split-half k (B05); provenance enforcement; target and label decoupling for the historical engine; the simulation suite; and the rebuilt plan audit.
- **Repaired:** moving the specification into `docs/research/dvp` had broken four links, the audit's path and a task record, so `main` CI was red.

**DvP plan completion audit (2026-11-24, TASK-20261124-005; [scope document](../research/dvp/PLAN_COMPLETION_SCOPE.md)):** every action item of the owner's specification, checked against rerun evidence.
- **Result: PASSED.** 214 items: 209 done and 5 open, each open one with its reason. All 156 checks passed, and 157 model tests passed with none skipped.
- **How it was checked:** `scripts/model/dvp_plan_audit.py` reran every stage on scratch copies, the 2025 holdout from the frozen commit. Each rerun equals its committed receipt apart from run time, code, run ID and Parquet byte order. The receipt is [plan-audit-receipt.json](../research/dvp/plan-audit-receipt.json).
- **Corrected:** two DvP documents named an earlier audit run than their receipts. That run built an identical observation table, so no number changed.
- **Open:**
  - the prospective 2026 weeks 12–18 scoring;
  - the owner's D/ST weight decision;
  - C03 and league-lineup evaluation, both BLOCKED;
  - dry-run and resume modes, not built.

**DvP plan completion (2026-11-24, TASK-20261124-004, ENG-062; [player-level report](../research/dvp/PLAYER_LEVEL_REPORT.md)):** an item-by-item audit of the owner's specification found Phase 5 (C00–C05) unrun though D/ST had passed its gate, T26 and T27 missing, no verify-only mode, and some §11 outputs missing. All are now done.
- **Phase C, D/ST:** the rule was committed before any result. B06 picks the higher-scoring D/ST in 60–62% of weekly pairs, against B00's 54–56%: +4.4, +8.5 and +6.6 points (dev, 2024, 2025) against a 1.8 minimum. **PROMISING.** Frozen for 2026 weeks 12–18 before kickoff.
- **Verified:** all 468 committed backtest metrics recompute exactly from the stored forecasts. The 2025 holdout reran from its frozen commit with forecasts equal to within 7×10⁻¹⁵ points (the last bit of polars' parallel sums) and identical results.
- **R-075 fixed:** reruns can no longer rewrite frozen candidates or forecast evidence.
- **What remains of the plan:** only the prospective 2026 weeks 12–18 scoring, at both levels, after the regular season. Then the owner decides on a D/ST production weight (OWN-074).

**M3 slice 3a, point-in-time reader (2026-11-23, TASK-20261123-001, ENG-053):** every Model feature now has a reader that returns only what was known before its decision time under ADR-007 as amended (OWN-066).
- **What it returns:** the version Arbit held, plus, inside a capture gap, what the source published before the decision (A1). Each value is labeled `observed`, `source-timestamp` or `retrospective-rule`.
- **Proof:** a mutation test passes at five decision times. On the real history, 56 table reads at four decision times, two inside the R-068 outage, returned no row known at or after its decision ([audit](../research/point-in-time-audit-2026-11-23.md)).
- **Catalog re-review (A2):** 38 timing-only exclusions become `as_imported`, observed weather becomes history, betting lines wait behind the OWN-067 gate, and the remaining exclusions are pinned as policy.
- **New risks:**
  - R-070: injury files from 2025 lack `date_modified`, so those rows use a game-day rule.
  - R-071: per-row placement cost 34 s and 2.2 GB on the full history. Resolved by TASK-002.

**Columnar reader and timing order (2026-11-23, TASK-20261123-002, ENG-054, OWN-072):**
- **The data was already local:** a version reads in milliseconds, and per-row Python was the cost.
- **Columns instead of rows:** the reader works on whole columns and caches each version's labeled rows. The audit takes 8.8 s instead of 34 s and 0.83 GB instead of 2.2 GB, with identical results.
- **A season of decision times:** every 2025 kickoff across 5 tables reads in 1.5 s.
- **The owner's timing order is ADR-007 A5:** held data first, then source timestamps and rules only for data refreshed during a gap or not yet fetched.

**Game-day availability (2026-11-23, TASK-20261123-003, ENG-055, OWN-073):** `arbit_model.availability` gives each player's status at a decision time.
- **On game day:** ESPN's status, read within 15 minutes, is final. It carries inactives.
- **Otherwise:** the freshest copy of NFL's injury report, Arbit's own twice-daily capture or nflverse's.
- **No source:** unknown, never assumed active.
- **On real data:** week 11's Sunday kickoff, inside the outage, is correctly flagged game-day unknown. Monday night's game day takes ESPN's final status for 1,026 players.

**M3 slice 3b, team environment and defense against the position (2026-11-23, TASK-20261123-004, ENG-056, OWN-068):** the Model's first features, 65 per team per game as of the decision time.
- **What they cover:** team rates, the opponent's defense, FFA points allowed to each position (raw and adjusted for the offenses faced), D/ST points the opponent's offense gives up, and pre-game context.
- **Measured for the owner's "why":** a defense's record against WRs, TEs and kickers is mostly noise within a season, about 15% weight after eight games. Against RBs and QBs it carries modest signal, about 27–29%. The D/ST points an offense gives up are the strongest matchup signal, 47% after eight games ([note](../research/team-features-2026-11-23.md)).
- **Proof:** a mutation test passes. On real data, every 2025 week 10 and 2026 week 12 game builds with full coverage in about 5 s per week.

**DvP research, phases 0-1 (2026-11-23, TASK-20261123-005, OWN-074, ENG-057; [runbook](../research/dvp/README.md)):** the owner's specification v1.1 now governs defense against the position.
- **v0 reproduced exactly:** the frozen script's rerun equals its receipt, and an independent recompute matches all 12 measures. v0's files are pinned by hash.
- **No provider projection anywhere in the path:** sources enter through a lineage allowlist that fails closed; dependency count 0.
- **Data defects found and dispositioned:**
  - R-072: relocated teams' old codes. 1,327 player lines credited to the team's own defense, and 156 team-games without a D/ST line. Repaired by TASK-20261123-007 (below).
  - R-073: refused lines summed as zero.
- **On validated observations:** D/ST conceded by an offense repeats strongly (k about 9). QB and RB repeat modestly (20-30). WR, TE and K are weak, and their intervals (about 20 to over 140 games) overlap, so v0's order among them isn't established.
- **Tests:** T01-T07 and T29-T40 pass (38), and five deliberate breaks each fail a test.
- **Next (done since):** Phases 2-5 ran on 2026-11-24; see the plan completion above.

**R-072 repair and rebuilt FFA targets (2026-11-24, TASK-20261123-007, ENG-058, OWN-075; [receipt](../research/targets-repair-r072.md)):** the owner ruled that fundamental defects are repairs, not decisions.
- **Fix:** every nflverse team code becomes its franchise code (`arbit_model.teams`) in targets, gamebooks and team features. The survey found more than the DvP audit had: STL 2012-2015 and five roster-only codes. The build now refuses a row whose team didn't play in its game.
- **Rebuild:** index `6ffb62fb…`, built on the exact inputs of `4afbd836…`, twice, with identical results. Every difference is classified, none unexplained:
  - 2020-2026 byte-identical;
  - 4,496 player lines given their real opponent;
  - 526 D/ST lines added;
  - 3,710 participation labels added;
  - no line's points changed.
- **Reruns:**
  - the signal study's team rates now cover 320 team-seasons, and the team shrinkage constants follow (takeaways 54.0 to 62.6);
  - DvP phase 1 has all 5,278 D/ST cells valid, D/ST k 8.9;
  - v0 still reproduces exactly on its own index.
- **R-074 fixed:** gamebooks read regular-season games only.

**DvP Phase 2, the reliability lab (2026-11-24, TASK-20261124-001, ENG-059; [report](../research/dvp/RELIABILITY_REPORT.md)):** A00, A02-A10 and A12 on the repaired observations, reproducible to the byte.
- **D/ST conceded is the one strong, stable tendency:** REML k 7.2 (6.0-8.6). It is flat within seasons and carries into the next.
- **The other groups:** RB 19.5, QB 24.2 (drifts within a season), WR 26.7, TE 37.4, K 50.5.
  - v0's WR 44 was an unlucky odd/even split.
  - The order among WR, TE and K isn't established.
- **The offense dominates:** its own production at a position settles in 4-7 games, so a result says three to seven times more about the offense than about the defense.
- **What repeats:** yards and receptions allowed; touchdowns allowed to WRs and TEs don't.
- **Next:** Phase 3, the walk-forward (done below).

**DvP Phase 3, the walk-forward (2026-11-24, TASK-20261124-002, ENG-060; [report](../research/dvp/BACKTEST_REPORT.md)):** next-game RMSE against the offense-only B00. The minimum was fixed before any forecast, and candidates were frozen before validation.
- **D/ST:** the opponent term (B06) cuts error by 3.0% in development (every season) and 6.4% in 2024. It is the one candidate.
- **QB, RB, WR:** under 1% in development, not replicated in 2024 (WR got worse). **TE, K:** nothing.
- **Unshrunk DvP rankings** make forecasts worse at every position.
- **Next:** Phase 4 (done below).

**DvP Phase 4 (2026-11-24, TASK-20261124-003, ENG-061; [model card](../research/dvp/MODEL_CARD.md)):** the method was frozen before 2025 was forecast, and the holdout verified every hash.
- **2025 conditional holdout:** D/ST B06 −4.1% RMSE, so D/ST is **PROMISING**. QB is INCONCLUSIVE; RB, WR, TE and K are NOT_USEFUL.
- **Research recommendation:** no group-level DvP influence for QB to K. A D/ST opponent term (k ≈ 8, last-season prior) is a candidate.
- **Confirmation:** 2026 weeks 12–18 were frozen in advance and will be scored after the season ([plan](../research/dvp/PROSPECTIVE_2026.md)).
- **Owner decision when confirmed:** whether to give the D/ST term a production weight. Nothing is changed meanwhile.

**Open work, in order** (owner direction 2026-11-22):
1. DvP: score the prospective 2026 window after the season, then Phase C for D/ST if confirmed (OWN-074); M3 slice 3c–3e: availability and role (on `arbit_model.availability`), efficiency and priors, and the Q-014 note; the 3b follow-up for play-by-play rates. Weather W1 (venue table and forecast record) runs beside it.
2. M3 slices 4–6.
3. M4 sit/start (OWN-068), weather W2–W6, the Q-014 study and ablation.

**Waiting on the owner:**
- the NWS User-Agent contact (weather W3);
- a remote 24/7 server for data refresh and outage alerting (OWN-070, R-068).

**Known gaps:**
- live play timing for weeks 1–7 and 10 never existed (ADR-007 A4);
- ESPN point-in-time injury status for 2026-11-10 to 11-22 is unknown.

**Governance system (2026-11-22):** the owner pushed the repository-native Context Governance System to `main` as `ec5682a`. It includes Codex/Claude entry instructions, structured task and handoff records, the authority matrix, the football-operations advisor charter (a requirement, not a shipped feature), the governance CLI and PR traceability. See the [audit](../governance/AUDIT_2026-11-22.md) and [start guide](../governance/START_HERE.md).
- **CI:** that commit failed Runtime validation at `make lint`, with 7 Ruff errors in `tests/governance/test_governance.py`. TASK-20261122-001 fixed it, and Runtime validation has been green on `main` since PR #2 (`d9f95ec`).

**Weather, alerting and history decisions (2026-11-22, TASK-20261122-007):**
- **Weather (OWN-069):** a forecast is a factor for games outside a closed roof. [ADR-008](../architecture/decisions/008-weather-intelligence.md) sets a multi-source system: Open-Meteo, NOAA RRFS, NWS/NBM, ECMWF/AIFS, and GHCNh/Meteostat for what happened. Forecasts are point-in-time records refreshed toward kickoff, and observed weather is used for effects only.
- **Verified:** RRFS went live on 2026-11-03 and NAM is gone; HRRR still runs, contrary to the owner's note.
- **Plan:** [weather intelligence](../superpowers/plans/2026-11-22-weather-intelligence.md), slices W1–W6. Nothing is built yet. The owner still needs to choose the NWS User-Agent contact.
- **Alerting (OWN-070):** waits for a remote 24/7 server; the owner keeps the PC awake meanwhile.
- **History (OWN-071), captured 2026-11-23 (TASK-20261122-008).** `arbit-worker catchup --from-period 1` recovered all 107 games of weeks 1–7 with 0 failures, first on a restored copy (19,780 play records), then on the database.
  - Each game now has a summary, plays owned by the NFL final record and completed correction checks.
  - 2026 weeks 1–10 are complete. Week 8 keeps its ESPN record, and week 11 is the live week.

**Running app repaired (2026-11-22, TASK-20261122-002).** The owner allows restarts at any time while they are the only user.
- **Database:** it was down from 2026-11-10 18:06 to 2026-11-22 22:44 UTC (R-068) and now restarts with Docker (`unless-stopped`).
- **Worker restart (23:43 UTC):** the worker runs `main` (`ec5682a`).
  - The **availability lane is active**, and its first injury-report capture succeeded.
  - All 13 week 11 NFL games are linked (R-069).
- **Week 10 recovered:** all 14 games, using this branch's catch-up command against the database at 23:46 UTC, with the worker stopped for 25 s.
- **Branch protection:** `main` requires the `validate`, `runtime` and `governance` checks.
- **Global guidance:** the Codex and Claude templates are installed.
- **Released 2026-11-22 23:52 UTC:** PR #2 merged (`d9f95ec`), and the worker restarted with the `catchup` lane and the relink and schedule-scope fixes.

**Catch-up after downtime (2026-11-22, ENG-052, TASK-20261122-004), released 2026-11-22 23:52 UTC on `d9f95ec`.** A new `catchup` worker lane recovers finished games the live lanes never read, from weeks that started and ended while the PC or database was down:
- **What it reads:** ESPN's scoreboard, summary and plays, and the NFL API's full record. It waits while a slate is active and records each game's kickoff and read time in a private receipt for ADR-007 A1.
- **Command:** `arbit-worker catchup --dry-run` reports what is outstanding.
- **Already self-recovering:** league lineups and transactions, nflverse and the whole-season injury report.
- **Fixes:** the live schedule now follows the season's latest week, and NFL games unlinked by a startup race relink within minutes (R-069).
- **Why:** the database was down from 2026-11-10 to 2026-11-22 (R-068), leaving week 10 unread. [Guide](../engineering/catch-up.md).
- **Scope:** regular-season weeks 1–18 only (TASK-20261122-005; test corrected in TASK-20261122-006). Postseason games stay with the live lanes.

**Owner decisions (2026-11-22, TASK-20261122-003):**
- **ADR-007 accepted with amendments (OWN-066).** A value fetched late after a capture gap counts from the source's own timestamp or family rule, never before the gap began. Every field states when it applies instead of being barred. Gaps come from Arbit's own read records.
- **Betting lines (Q-014) conditionally approved (OWN-067).** They enter only after a research note and a backtest ablation show they improve FFA-point accuracy.
- **Lineup sit/start is the first advisor (OWN-068).** It starts after M3 slice 6, and its projections must explain their contributions.
- **Reconciled:** Q-012 is superseded by OWN-040/041, which resolves R-067.
- **New question:** Q-016, whether to use a weather forecast for the upcoming game.

**M3 integration (2026-11-22):** PR #1 merged `claude/m3-model` into `main` (`21cb24c`). Its Runtime validation, including the PostgreSQL suite and the browser flow, passed on the PR and again on the merge commit. Activating the new availability lane on the running worker is a separate step; see the [integration handoff](handoffs/2026-11-22-m3-integration.md).

**M3 Model has begun** by owner direction after the 2026-11-09 audit (OWN-060); Live (M6) work is parked, not dropped. Slice 1 is implemented and awaiting runtime release: Arbit turns nflverse statistics and play-by-play into FFA stat lines scored by the shared engine (ENG-051). Against ESPN's raw statistics, 7,171 of 7,202 compared 2025 player-weeks and 3,549 of 3,569 2026 player-weeks match in every category. The 11 remaining decided differences are source-side (R-060), and 37 lines with an unattributed defensive two-point return stay unknown rather than zero (R-061). No projection exists yet. [Plan](../superpowers/plans/2026-11-09-m3-model.md), [research](../research/nflverse-ffa-scoring-2026-11-09.md), [handoff](handoffs/2026-11-09-m3-ffa-points.md).

**Model inputs and architecture (2026-11-09, OWN-061).** The owner directed that the Model use only nflverse data, considering every field, and never another provider's fantasy or projection data, weighed against FFA's scoring. Research reviewed how others project players from nflverse and measured 2016–2025 FFA stat lines. Opportunity carries half its signal within two games; efficiency and touchdowns need dozens. Touchdowns are 30–45% of skill-position variance, and D/ST and kickers follow team and opponent environment. The owner accepted [ADR-006](../architecture/decisions/006-model-architecture.md) (OWN-062): a team-first model that simulates whole stat lines, scored by the shared engine. The interpretable Baseline A comes first; ML candidates follow through the release gate. Betting lines in nflverse schedules (Q-014) are approved only if a study and ablation show they help (OWN-067, 2026-11-22). [Research](../research/ffa-projection-methods-2026-11-09.md), [handoff](handoffs/2026-11-09-m3-model-architecture.md).

**M3 slice 2 (2026-11-10), implemented and awaiting runtime release.**
- **Field catalog:** the new `arbit-model` package records one use for each of the 1,827 imported nflverse fields: pre-game, history, earlier seasons, outcome, identity, or excluded with a reason. A check fails on any field without an entry.
- **Historical targets:** FFA-scored lines for every player-game and D/ST team-game, 2012–2026, plus participation labels, stored as versioned Parquet with manifests.
- **Reproduction:** read with the same pinned nflverse versions, the targets reproduce the slice 1 verification exactly.
- **Two-point returns (R-061):** the snap rule resolves 16 previously unknown lines, and all 16 match ESPN.
- **Inactives (R-064):** nflverse publishes them only after each game. So [ADR-007](../architecture/decisions/007-model-availability.md) sets one decision time per game, at kickoff, with publication rules for each family. The owner accepted it on 2026-11-22 with amendments (OWN-066).

[Handoff](handoffs/2026-11-09-m3-slice2-catalog-targets.md).

**NFL availability twice a day (2026-11-10, OWN-063), implemented and awaiting runtime release.**
- **Injury report:** the new `availability` worker lane reads NFL's injury report (each player's game status and practice) at 12:00 and 19:15 Eastern every day. Each read is kept with the time it finished.
- **Inactives (OWN-064):** these come from ESPN's fantasy injury status, which Arbit already reads. A new reader gives the status as of any moment and marks it unknown if Arbit wasn't reading then.
- **Read gaps (R-066):** caused by the PC being put to sleep most nights. Under OWN-065 a Windows task now wakes the PC before each game window and for the daily reads, then lets it sleep again ([how](../engineering/windows-wake.md)). The first real wake is still to be checked.
- **Release:** the lane reaches the running worker only on the owner's request.

[Handoff](handoffs/2026-11-10-m3-nfl-availability.md).

On 2026-11-08: M2, the accepted design reset, and the real-time platform are integrated into `main` and run on the local app. **Live (M6) is in progress ahead of M3** (OWN-019). After the Jacksonville–Baltimore capture, the local worker now reads active NFL games' full details every two-second round with a fresh cache key (OWN-045). On Sunday, fresh reads saw new plays a median 17.9 s after the whistle, against 39.4 s for ordinary cached reads of the same games (R-042 resolved, [measurement](../research/nfl-fresh-polling-2026-11-08.md)). [Polling handoff](handoffs/2026-11-05-nfl-fresh-polling.md).

**ESPN league facts and history (2026-11-08, ENG-050), released to the running app at 18:49 (UTC−7) by owner request.** An audit matched 1,437 served facts with ESPN but found the current week reading 0.00–0.00 "Official" all week, stored past lineups hidden and raw ESPN codes on the page (R-054 to R-058). The fixes are done and were verified on a restored copy of the database:
- live and official totals labeled apart
- reconciled weekly lineups (64 of 64 team-weeks match)
- league transactions (435 across 9 periods)
- manager names, season points, plain injury labels, league rules, recent moves, and the owning team in the drawer

1,344 served facts match a fresh ESPN read. `main` at `486d431` is pushed; migration 0010 is applied, the API serves release `league-surfacing-2026-11-08`, and the worker runs `main`. [Handoff](handoffs/2026-11-08-league-surfacing.md).

**Public address (2026-11-08, OWN-058).** The app on this PC is now served at `https://ffa.westfam.media` through the Cloudflare Tunnel `arbit`, behind the owner's Cloudflare Access, and that is its only sign-in address. Choosing a hosting platform is still deferred (OWN-014). The owner signed in there from an iPad; a second member is still to be shown (R-053). [Handoff](handoffs/2026-11-08-public-address.md).

The locally running game detail view puts the existing game cards in one scrolling row and gives the field the full content width. The Jumbotron is the main scoreboard when it can draw. In 31 games, the coverage audit found 67 football actions or tries without a clip, plus 328 cancelled entries the browser skips (R-045). [Layout handoff](handoffs/2026-11-05-live-field-layout.md) and [coverage audit](../research/live-play-coverage-2026-11-05.md).

The animation pipeline audit traced 4,919 NFL scripts and reproduced browser failures in reduced-motion following, replay selection and the final ball frame. It also confirmed that the ESPN postgame check displaced the NFL replay for Jacksonville–Baltimore. R-045–048 track the remaining play, source, browser and board work. [Audit](../research/live-animation-pipeline-audit-2026-11-05.md).

The November 6 repairs are active on the local app. Jacksonville–Baltimore was reconciled to 166 current NFL rows, and Week 9 has 15 private art bundles. The November 7 wake check verified the installed release and refreshed Denver's exact B3 kit. All 67 previously missing football actions have full or labeled partial clips on the recorded sample. The verified-final source guard, in-place Jumbotron updates and stable replay selection passed isolated checks. [Repair handoff](handoffs/2026-11-06-live-animation-repairs.md).

The stadium around the live field (OWN-049, ENG-045) is published to all 15 Week 9 games on the local app, on the owner's approval. [Handoff](handoffs/2026-11-07-live-stadium.md). Plays are being rebuilt to their real snap-to-whistle time (OWN-051, OWN-052). Slices 1 and 2 are implemented, but not released: the board clock runs in real time, and runs and scrambles are built to time. Runs with more than 1.5 s of standing time went from 36% to 2% across 31 games. Passes are next. [Handoff](handoffs/2026-11-07-play-timing.md).

The independent Live animation audit is complete. It traced the current NFL-to-browser path and separated action interpretation, phase timing, rendering and review-tool defects. The private comparison evidence stays under ignored data/ (OWN-053). The rebuild is pending its own implementation plan. [Audit handoff](handoffs/2026-11-07-live-animation-rebuild-audit.md).

The owner expanded the offline tracking archive for inference research and clarified role continuity (OWN-054). The archive was surveyed, with whole games reserved for validation. The [rebuild design](../superpowers/specs/2026-11-07-live-animation-rebuild-design.md) is approved (OWN-055). [Calibration handoff](handoffs/2026-11-07-live-animation-calibration.md).

Each home stadium's own design is implemented for the live field's surround (OWN-059, ENG-047). It is not published yet and awaits the owner's review. [Handoff](handoffs/2026-11-08-stadium-venues.md).

The local web stack serves the revised opt-in rebuild preview (OWN-056, OWN-057). It includes shared tackles on runs and passes, earlier receiver release, calibrated ball flight and visible motion beyond scores and inferred uncaught touchbacks. Thirteen Thursday renders were manually reviewed. Family coverage, first-contact and scoring timing, directional art and default activation remain open. [Motion handoff](handoffs/2026-11-08-live-motion-calibration.md).

The owner reaffirmed **M&T Bank first, then the remaining stadiums** on November 8. Its private 3D study now has measured straight upper decks, corrected lower/club tiers, continuous suites, raised entrances and revised corner lights. Fifteen focused tests pass, and both lighting previews preserve all 509,969 field pixels. **Not integrated or published:** likeness review and Live framing remain M6 gates; the current crop hides the upper deck/lights. The owner identified the farther right-wall cutout as the players' tunnel. Both cutouts are clear of seats, and the recessed tunnel appears in the reference and Live views. [Refinement handoff](handoffs/2026-11-08-mt-bank-refinement.md).

## Confirmed context

FFA ESPN league **1729878439**, season **2026**. Owner approved the architecture/stack and additional dependencies, especially UX/UI. Deployment remains portable and local-first. High-quality, deliberate product design and engineering are required. Owner authorized development using the verified public FFA access and excluded message boards from product scope. Exact owner Gridiron asset links are still unavailable.

## Current implementation

M1a is implemented: pinned native Python/JS workspaces, exact scoring and temporal identity, PostgreSQL migration/snapshot/outbox persistence, fenced durable jobs, guarded synthetic worker path and health-only API. See [local development](../engineering/local-development.md) for reproducible commands. Runtime verification had **409 passing tests** at that point, including real PostgreSQL integration, plus Ruff/strict mypy/AJV/artifact checks. All completed slices have independent review and regression-backed fixes; no Important findings remain deferred.

M1b implements the public transport, observed league/player contracts, bounded complete pagination, ownership/context checks and `arbit-worker espn-inspect`. The complete audited retrieval surface is wired through 19 registered endpoint families; `arbit-worker espn-endpoints --live` passed all 68 recognized successful variants after review (63 available, three limited, two metadata-only). [Coverage](../research/espn-endpoint-coverage-2026-10-30.md). A fresh live read returned eight teams, 132 owned, 923 available, 46 scoring items, 128 picks and 56 matchups through seven cookie-free GETs. [Reader receipt](../research/espn-reader-live-2026-10-30.json). The pinned reference checkout is available under ignored `.references`.

M1c scoring slice: all 46 actual definitions mapped; completed weeks 1–7 verified 797 played player-games plus 121 separate provider-zero entries and 56/56 lineup totals, with zero discrepancies. Private archived-input replay reproduces the result. Eleven categories lack nonzero live examples; synthetic math/boundary evidence is distinguished. [Scoring proof](../research/ffa-scoring-verification-2026-10-30.md). Recommendations remain disabled.

M1c durable sync now publishes complete FFA facts with persistent native identities, dated affiliations, immutable verified rules, correction history and private capture manifests. Shared PostgreSQL pacing/cooldown, leased heartbeats, durable retry/pause/freshness and offline replay are implemented. Protected loopback-only operator reads serve the stored league; default API remains health-only. Live proof: eight teams/eight managers, 132 owned, 923 available, 128 picks, 56 matchups, one snapshot/outbox after four successful refreshes (including a bounded automatic-worker run). [Operator guide](../engineering/ffa-synchronization.md), [safe evidence](../research/ffa-sync-live-2026-10-30.json).

M1d is implemented and fully imported: 1,140 selected logical files across 28 families, 1,087 tables/11,973,952 stored rows and 53 archive-only originals/metadata/reference files. Versioned original/normalized objects and additive 0003/0004 migrations pin checksums, source/observation/proof times, schemas, coverage and attribution. Durable staged acquisition/publication, exact GSIS/ESPN crosswalks and protected canonical-player reads are verified. All 786 checksum-free assets passed a second catalog check; offline verification covered all 1,140 manifests/1,157 unique data objects. All 121 rostered athletes map to GSIS, with two lacking weekly rows. Five later conflicting supplemental aliases were closed with backed-up immutable history; zero active provider/entity multiplicities remain. [Full audit](../research/nflverse-data-audit-2026-10-31.md), [guide](../engineering/nflverse-ingestion.md), [safe receipt](../research/nflverse-live-2026-10-31.json).

M1e is implemented and locally verified: durable public observations/daily cache, documented Sleeper directory/state/trends and two explicit candidate stat representations; read-only exact joins with conflicts excluded; scoped ESPN scoreboard/summary/core plays and per-play-time correction-safe replay; empty Gridiron manifest and exact-context/permission gate. Actual proof: 12,229 directory records, 40/121 owned-athlete direct hints (NFLverse remains 121/121); four completed games/842 plays including overtime/tie, all 293 game-scoped supplied athlete IDs resolved; final/pregame CLI and offline 25-observation/66-object verification. No images or messages. [Audit](../research/m1e-source-audit-2026-10-31.md), [guide](../engineering/supplemental-live-sources.md).

M2 member auth/binding, Front Office facts and PWA now exist locally. Google is selected, with real client/member/team acceptance still open. Active/corrected Live evidence and exact asset grants remain M6 gates. Recommendations remain disabled. The earlier private-setting 401 is historical; current settings requests return 200 without cookies, and message-board availability is outside product scope. See the [full audit](../research/espn-public-api-audit-2026-10-30.md).

## Milestones

| Milestone | State |
| --- | --- |
| M0 foundation | Delivered; architecture/stack accepted by owner |
| M1a runtime/core/snapshot | Implemented, reviewed and locally verified |
| M1b FFA access/capability inventory | All audited usable routes wired and live-verified; canonical local sync implemented in M1c; member production access awaits M2 |
| M1c scoring/normalization | Scoring and canonical FFA aliases/publication/durable local sync implemented and live-verified |
| M1d statistical foundation | Complete published catalog imported, reviewed, replay/identity/local-read verified |
| M1e supplemental/live sources and assets | Implemented/reviewed; observed source matrix, offline replay and asset prerequisites verified; empirical Live/asset gaps explicit |
| M2 application/auth/Front Office/PWA | Implemented/local validation; Google selected; real client/member acceptance pending |
| M3 Model/Scout | In progress; slices 1–2 merged to `main` via PR #1: slice 1 (FFA points from nflverse) verified against ESPN; nflverse-only architecture accepted (ADR-006, OWN-061, OWN-062); slice 2 (field catalog, historical targets, participation labels) and NFL availability reads (OWN-063) implemented; availability policy accepted with owner amendments (ADR-007, OWN-066); no projection yet. Next: slice 3 features |
| M4 Lineup/waivers | Not started. Sit/start is the first advisor, after M3 slice 6 (OWN-068) |
| M5 trade/Draft | Not started |
| M6 Live | In progress: scoreboards running on the local app; Gridiron delivery, play animation and fantasy attribution remain |
| M7 Archive/refinement | Not started |

## Repository and verification

Owner published baseline commit `cab6bd8` on main. Owner published `codex/m2-member-application` at `61368fd`. Current work: local branch `claude/platform-reset`, not pushed; no merge or deployment. Aggregate validation: `make runtime-check` after frozen installs and `make db-up`. On this host use the pinned npm-exec workaround in the development guide if Corepack is misconfigured. Local PostgreSQL service remains available; HTTP smoke process has been stopped.

Latest [M2 handoff](handoffs/2026-10-31-member-application.md) records member implementation, local proof and Google release gate. Earlier [M1e handoff](handoffs/2026-10-31-supplemental-live.md) records supplemental/live proof, review fixes and remaining gates; [NFLverse handoff](handoffs/2026-10-31-nflverse.md) records full M1d source/identity/HTTP proof and review rulings; [durable sync handoff](handoffs/2026-10-30-durable-ffa-sync.md) records canonical publication and live API proof; [scoring handoff](handoffs/2026-10-30-ffa-scoring.md) records exact scoring verification; [endpoint handoff](handoffs/2026-10-30-endpoint-coverage.md) records full routing; [reader handoff](handoffs/2026-10-30-public-reader.md) records core acquisition; [public API handoff](handoffs/2026-10-30-espn-public.md) records the earlier 81-probe audit. [M1a handoff](handoffs/2026-10-30-m1a.md) records runtime tests, code scope, environment adaptations and review results. [Initial foundation handoff](handoffs/2026-10-30-foundation.md) is historical. [Roadmap](roadmap.md), [decisions](decision-register.md), [known issues](known-issues.md), [research](../research/source-register.md) and [changelog](changelog.md) preserve continuity.

## M2 active work and source correction

The owner restricts Sleeper to relevant NFL live games/PBP only. Earlier directory/state/trend/fantasy-stat and hint-mapping paths are retired and no longer application inputs; old audit receipts remain historical. No eligible Sleeper live route is enabled. ESPN game/PBP remains active. [M2 plan](../superpowers/plans/2026-10-31-member-application.md) covers invited member access, stored Front Office facts and the deliberate application/PWA shell. Google is now the selected provider. No real OAuth client or external service has been provisioned.

## M2 implemented scope

Invited OIDC accounts, opaque sessions, administrator-approved manager bindings and access controls, typed/generated member API, Front Office saved facts, player drawer/search, watchlist/preferences and static-only PWA are implemented. Two clearly fictional browser members prove scope; the actual stored FFA snapshot validates without a fixture identity. Google is selected; owner-controlled client configuration and real invited sign-in/team proof remain open. [M2 handoff](handoffs/2026-10-31-member-application.md), [operations](../engineering/member-application.md). No recommendations, active Live workspace or deployment.

Final M2 verification: 453 backend tests, 14 client tests and 7 Chromium scenarios pass; generated contracts/type/build/PWA checks pass. One Sol review’s two Important and one Minor findings were fixed with regressions. Actual populated-source migration preserves all counts/digest; no real member account was created. See the final M2 handoff for remaining operational acceptance.

## Google configuration follow-up — 2026-10-31

The owner created the Google OAuth client and supplied credentials in a locally ignored file. That file was safely moved from `config/google-auth.env` to root `.env.auth.local`, restricted to mode 600, and confirmed untracked/ignored. Configuration validation and real-OIDC-mode local readiness passed without printing credentials or contacting Google. The remaining M2 gate is the first administrator invitation, actual Google sign-in, approved manager binding and second-member verification.

## Owner sign-in acceptance and manager labels — 2026-10-31

The owner confirmed successful real Google sign-in, first administrator invitation, team approval/session rotation and return to Front Office. This is owner-reported real acceptance, separate from prior fictional tests; second-member and native/assistive-technology checks remain open. ESPN's team/settings view supplies first names for all eight FFA managers; six display names are generic. Canonical optional first names and team context now label the administrator manager dropdown, retaining original handles for fallback/disambiguation and stable IDs for binding. A normal live sync stored all eight names with manager IDs and approved bindings unchanged.

## Design reset and real-time platform — 2026-10-31

The owner reported AI-identifiable design drift and stale data, and redirected the work (OWN-013–017). **Built and verified on `claude/platform-reset`; applied to the running local app on 2026-11-01 04:26 UTC.** [Handoff](handoffs/2026-10-31-platform-reset.md).

- **Design:** new officiating-and-broadcast character ([ADR-005](../architecture/decisions/005-officiating-character.md), [design system](../design/design-system.md)), all slogans removed, and `pnpm check:design` enforcing the rules; it flagged 436 violations on the old interface. The owner accepted it (OWN-018).
- **Sync:** `arbit-worker run` keeps the FFA league, NFL scoreboard, active-game plays and summaries, NFL teams and schedule, and NFLverse statistics current on a cadence that follows the real NFL slate.
- **Clients:** session-bound SSE updates open pages without a reload. Per-device sessions mean signing in on a phone no longer ends the laptop session.
- **Members now see:** real Live scoreboards with possession, down and distance, field position, score by quarter, win probability, team stats, leaders, drives and plays with a my-players filter; also NFL team/bye/opponent on roster rows, per-source data status, season results strip and playoff line.
- **Evidence:** 587 backend tests, 20 client tests, 10 browser scenarios and all static checks pass. The [first real slate](../research/live-slate-receipt-2026-11-01.md) was measured: 0 read failures, a median play delay of 36 seconds, and real game changes reaching an open page without a reload.
- **Running now:** `arbit-api` and `arbit-worker` as systemd user services on schema `0007_realtime`, upgraded with scoreboards 2026-11-01 21:25 (UTC−7). The fix for signing in from another local address (R-036) is built and waits on the next upgrade. They do not come back by themselves after a Windows restart (R-029).
- **Next:** Gridiron URL patterns are verified and week 8 art is stored privately. Scoreboards and animation have [19 listed prerequisites](../research/live-animation-prerequisites-2026-10-31.md); the owner chose [pixel sprites](../research/live-animation-prerequisites-2026-10-31.md#sprite-direction--owner-decision-2026-11-01) (OWN-022), approved the test frames (OWN-023) and owns the art (OWN-024). 59 frames are in `assets/sprites`: the six originals and 53 drawn from them by PixelLab (OWN-026), with the ball drawn separately (OWN-027). Every frame can be painted in any real 2026 uniform, measured from the owner's Gridiron set rather than inferred (OWN-028, [research](../research/uniform-measurement-2026-11-03.md), [handoff](handoffs/2026-11-03-real-uniforms.md)). The owner accepted the real-uniform plays and made the full-field view the standard (OWN-029, OWN-030, ENG-028). Good kicks now pass between the uprights (ENG-029). The owner asked for other players on the field, a jumbotron and a field that persists between plays, all added to the plan ([handoff](handoffs/2026-11-03-full-field-and-automation.md)). None are in the app yet. After the 2026-11-03 restart the dev database had to be started by hand (R-029). A read-only dev account lets Claude see the running app signed in as any team (`make dev-account`, ENG-031). The running app was upgraded at 17:50 on 2026-11-03 with it and the R-036 sign-in fix; R-039 lists what the signed-in view showed. The ball now spirals or tumbles the way it would in a real play (ENG-030). NGS tracking is skipped for now, and plays keep showing only the players in them (OWN-032, Q-011). ESPN's live feed already has yards after catch, so plays can show where the catch was made and the run after it (ENG-032); NFL's private API route is the owner's decision (Q-012). Slice 1, play facts, is done in code: 2,032 of 2,196 captured football plays are ready to animate ([task](../superpowers/plans/2026-11-03-play-facts.md), [handoff](handoffs/2026-11-03-play-facts.md)). Slice 2, play scripts for passes, runs, sacks and interceptions, is done and accepted by the owner (OWN-034): all 1,705 such captured plays get a script that moves naturally and keeps every rule ([task](../superpowers/plans/2026-11-03-choreography.md), [handoff](handoffs/2026-11-03-choreography.md)). Slice 3, kicks, tries, fumbles and penalties, is done in code. The owner's first review asked that defenders start at or behind the line of scrimmage and kept the 2026 kickoff alignment (OWN-035). That is fixed for every play (ENG-036). Players now also line up by their depth chart positions and make their position's first move after the snap (OWN-036, ENG-037, [task](../superpowers/plans/2026-11-04-play-alignment.md), [handoff](handoffs/2026-11-04-play-alignment.md)). One clip of each play type was rendered. The owner compared them with the game's video and sent notes (OWN-037). Those fixes are built (OWN-038, ENG-038, [task](../superpowers/plans/2026-11-04-play-realism.md), [handoff](handoffs/2026-11-04-play-realism.md)), with new PixelLab poses and officials who throw the flags. Committed 2026-11-05. The stadium board (slice 5) is built in code: the shared library gives each play's board from the stored plays, and it matches ESPN's own scoreboard over all 14 captured games (ENG-039, [task](../superpowers/plans/2026-11-05-jumbotron.md), [handoff](handoffs/2026-11-05-jumbotron.md)). The owner reviewed it ("It looks really good!") and asked for scrolling results, green, red and yellow by kind, penalty cards with the player's number, and team logos. Those are built (OWN-039, ENG-040). The owner accepted the board ("The scoreboard looks phenomenal!", OWN-040) and slice 5 is committed. The owner is finishing an NFL API feed with each play's start and end clock, and wants it pushed the moment data is available rather than polled. The owner then made the NFL API the primary live source, with ESPN's live data as the emergency fallback (OWN-041). Every route was surveyed (slice A, [survey](../research/nfl-api-data-survey-2026-11-05.md)). That's built and on the running app since 07:47 Arizona time on 2026-11-05: the NFL API lane, real-time pacing and the browser's live field (ENG-041 to ENG-043, [plan](../superpowers/plans/2026-11-05-nfl-api-primary.md), [handoff](handoffs/2026-11-05-live-by-kickoff.md)). The live proof is JAX at BAL at 18:15 Arizona time (OWN-042). 2,182 of 2,196 captured football plays and 72 of 74 tries get a script that keeps every rule ([task](../superpowers/plans/2026-11-04-kicks-fumbles-penalties.md), [handoff](handoffs/2026-11-04-kicks-fumbles-penalties.md)). The rest stay as text: laterals, a trick play, aborted or loose snaps, and plays ESPN describes only as a scoring summary. On 2026-11-04 the dev database stopped again while WSL kept running, and was started by hand (R-029). The normalizer change and the R-039 fix have been on the running app since the 21:16 upgrade. [Scoreboards](../superpowers/plans/2026-11-01-live-scoreboards.md) are running. Next is the proposed [automation plan](../superpowers/plans/2026-11-03-live-play-automation.md): interpreter and choreographer on the server, kicks, supporting players and the jumbotron as reviewed renders, the Gridiron listing lane with a labeled fallback (R-037), then the in-app renderer.
- **Live capture:** the worker has kept private raw copies of every live read since 2026-11-01 06:23 UTC, ahead of the first real slate (OWN-020, R-030). Animation shows only the players ESPN names on a play and the ball (OWN-021). The host PC slept through the 2026-11-01 early games, so only the late games were observed live (R-029).
