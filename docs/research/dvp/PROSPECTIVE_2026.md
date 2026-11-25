# M3-3 DvP prospective confirmation, 2026 weeks 12–18

Specification §9 Phase 4 and §12: "only a future, prospectively frozen 2026+ run can confirm independently." Frozen in TASK-20261124-003. The prospective harness was built and week 12 archived in TASK-20261124-006 (owner audit AUD-01).

## True prospective, not reconstruction

The owner's audit (AUD-01) separated two kinds of evaluation:

| | Order of events | Status here |
| --- | --- | --- |
| **True prospective** (what this window uses) | Freeze the method → **generate and archive forecasts** → games are played → evaluate the archived forecasts | **In place.** Week 12 was archived 2026-11-24 23:12 UTC, 25.8 hours before its cutoff |
| Frozen retrospective | Freeze the method → games are played → reconstruct forecasts → evaluate | Allowed only as a labeled `RETROSPECTIVE` reconstruction, never counted as prospective |

Earlier versions of this document planned the second kind: rebuild after the season, then forecast. That was replaced before any week-12 game.

## What was frozen, and when

**Group level.** At **2026-11-24 03:16 UTC**, [`config/dvp/frozen.json`](../../../config/dvp/frozen.json) fixed:
- the method: SHA-256 hashes of `walkforward.py`, `lab.py`, `asof.py`, `observations.py`, `reliability.py`, `provenance.py`, `teams.py`, `scripts/model/dvp.py`, `config/dvp/base.json`, `config/dvp/backtest.json` and `config/dvp/frozen-candidates.json`, at code `f75868b`;
- **the candidates:** D/ST B06; B00 (no DvP term) for QB, RB, WR, TE and K;
- **the protocol:** RMSE relative to B00, week-block bootstrap (2,000, seed 1729), and the 1% practical minimum;
- **the window:** 2026 regular-season weeks 12–18.

**Phase C.** At **2026-11-24 06:57 UTC**, [`config/dvp/frozen-phase-c.json`](../../../config/dvp/frozen-phase-c.json) fixed `decisions.py` and the start/sit rule (`config/dvp/sitstart.json`).

**The prospective procedure.** [`config/dvp/prospective.json`](../../../config/dvp/prospective.json) was committed and pushed at **2026-11-24 23:12 UTC**, before any week-12 forecast. It fixes:
- the data each forecast may use;
- the readiness rule;
- the classifications;
- the archive and ledger;
- the evaluation;
- an exploratory league-constrained D/ST evaluation.

None of the window's games had been played at any of these times.

## How each week is forecast

[`scripts/model/dvp_prospective.py`](../../../scripts/model/dvp_prospective.py) runs `forecast --week W` or `sweep`. Each run does the following, in order:

1. **Verify the frozen method.** It checks every hash in both freezes. The frozen `dvp.py` is read from git at `f75868b` and checked against its hash; the library modules must equal their frozen hashes and be the ones imported. Any mismatch stops the run (BLOCKED).
2. **Assemble the data.**
   - **2016–2025:** the frozen audit run's observations and schedule, hash-checked.
   - **2026:** a fresh `build_targets.py` of 2026 alone, into the week's archive, from the nflverse files Arbit holds at that moment. Every object's bytes are verified against its digest, and the rows are admitted through the projection firewall.
3. **Check readiness** (amendment 1, AUD-01b). Every game of weeks before W gets a state:
   - **Ready:** ELIGIBLE_VERIFIED (all 12 cells present and valid), RETRIEVED_INVALID (all present, some invalid for a recorded reason) or POSTPONED_OR_CANCELED (no result 4 days after kickoff, recorded).
   - **Blocking:** AWAITING_RESULT, NOT_YET_AVAILABLE (before 12:00 UTC the next day), SOURCE_NOT_YET_PUBLISHED, PUBLISHED_NOT_RETRIEVED (nflverse has a newer statistics file than the one the worker's statistics lane imported) or DATA_INTEGRITY_FAILURE.
   - Any blocking game makes the run wait and retry.
4. **Forecast with the frozen estimator** through the adapter `arbit_model.dvp.shadow`:
   - targets come from the schedule, so no score or label is needed;
   - parameters are fit on 2016–2025;
   - the walk covers weeks 1 to W, because the residuals need each earlier week's point-in-time B00.
   - Only week W is archived.
5. **Capture the league** (amendment 1, PB-AUD-07; C05L-2026-PRO in [LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md)). From week 13:
   - one snapshot is read in one read-only, repeatable-read transaction;
   - every team is listed, including any with no D/ST;
   - all 32 D/STs get ESPN's own reported state in that snapshot: OWNED, FREE_AGENT, WAIVERS or UNKNOWN, where UNKNOWN covers a roster entry and a reported state that disagree;
   - the drop-time rule is kept only as a labelled fallback;
   - the snapshot's id, time, hash, rules hash and age are recorded.

   Week 12's capture, made before this, has rosters only. A separate supplement gives the states ESPN reported in that same snapshot: all 19 unowned units were on waivers.
6. **Archive once** (amendment 1, AUD-01d). `forecasts.parquet`, `forecasts.csv`, `manifest.json`, `league.json` and the inputs (the 2026 observations, schedule and targets store) go into `artifacts/dvp/prospective/2026/week-WW/`.
   - The run holds the season's lock throughout.
   - Files are staged and fsynced, then the folder is renamed into place in one step and the parent fsynced. `archivedAt` is taken after that.
   - The folder refuses a second write, and its files are read-only.
   - A ledger line holds every file's SHA-256, `generatedAt`, `archivedAt` and the previous line's hash.
   - Archival that would finish at or after the cutoff is recorded MISSED.
7. **Publish a commitment** (amendment 1, AUD-01a):
   - **What:** the ledger entry, its hash and every file's hash, plus the forecasts CSV.
   - **Where:** branch `research-evidence/dvp-prospective`, from a dedicated clone, with a key that writes to this repository only.
   - **Checks:** it is read back and compared. GitHub's activity record of the push is the external timestamp.
   - **Record:** every attempt goes to `publications.jsonl`; failures retry each run.
8. **Until the cutoff,** each run records the league again whenever the snapshot changed (`captures.jsonl`). The last capture before the cutoff is the decision-time state.
9. **Export** the forecasts, manifest and ledger to [`prospective/2026/`](prospective/2026). The league capture holds per-team rosters and stays local; its hash is in the manifest and the commitment.

**The adapter is the frozen estimator.**
- On synthetic seasons, given the frozen walk's targets, it reproduces `walkforward.walk` bit for bit (`test_dvp_shadow.py`).
- On the real 2025 holdout it reproduces every frozen forecast column within 7.1×10⁻¹⁵ points ([rehearsal-2025.json](prospective/rehearsal-2025.json)).
  - Only the B09 placebo controls differ: they draw random numbers per batch.
  - The adapter also forecasts 8 cells whose labels later turned out invalid. The frozen walk dropped them before forecasting (AUD-05); the adapter keeps them.

## Status of the window

| Week | Cutoff (UTC) | Inputs complete from (UTC) | Status |
| --- | --- | --- | --- |
| 12 | 2026-11-26 01:00 | (weeks 1–11 done) | **PROSPECTIVE:** archived 2026-11-24 23:12:45. External evidence, both verified: GitHub recorded the push of `168196d` at 23:13:15; the evidence-branch commitment `959ff9e` at 2026-11-25 03:46:49 |
| 13 | 2026-12-04 01:15 | 2026-12-01 12:00 | Pending |
| 14 | 2026-12-11 01:15 | 2026-12-08 12:00 | Pending |
| 15 | 2026-12-18 01:15 | 2026-12-15 12:00 | Pending |
| 16 | 2026-12-25 01:15 | 2026-12-22 12:00 | Pending |
| 17 | 2027-01-01 01:15 | 2026-12-29 12:00 | Pending |
| 18 | 2027-01-10 18:00 | 2027-01-05 12:00 | Pending |

The "inputs complete" times assume nflverse publishes the week's statistics by then. If it hasn't, the harness waits.

**Missed weeks** are recorded in the ledger as `MISSED`. Under amendment 1 a missed week makes the window INCOMPLETE_WINDOW: descriptive only. A later reconstruction is stored apart as `RETROSPECTIVE`, evaluated separately and never counted.

## Operations (owner-authorized timer, OWN-077 DEC-02)

**The timer:** `arbit-dvp-prospective.timer`, a systemd user timer installed by `sh infra/systemd/install-dvp-prospective.sh` from the main checkout.
- **Schedule:**
  - runs at 00:17, 06:17, 12:17 and 18:17 UTC, from 2026-11-25 to 2027-01-15;
  - a run missed while the PC slept fires at the next wake (`Persistent=true`);
  - the PC's wake task (`infra/windows/arbit-wake.ps1`) wakes it daily at 00:10–00:35 and 16:55–17:20 UTC and starts WSL, so every day has at least two runs;
  - user services survive logout (linger is on).
- **Shutdown:** it disables itself once every window week is final and every commitment verified.
- **Each run** (`sweep`):
  - recovers an interrupted run;
  - forecasts a ready week or records a missed one;
  - captures the league before each archived week's cutoff;
  - publishes pending commitments;
  - writes `artifacts/dvp/prospective/2026/status.json`.

**Alerts:**
- **Raised for:** a failure, a missed week, a week still not ready within 18 hours of its cutoff, an unverified commitment within 18 hours of its cutoff, or a recovery that quarantined or missed an archive.
- **Where they go:** the service journal (`journalctl --user -u arbit-dvp-prospective`), `alerts.jsonl` beside the ledger, and a Windows notification, whose delivery result is recorded.

**Least privilege:**
- **Database:** sessions are read-only on the server.
- **Publication:** uses `~/.config/arbit/research-evidence/id_ed25519`. The owner registers it once as a write deploy key for this repository: `gh repo deploy-key add ~/.config/arbit/research-evidence/id_ed25519.pub --allow-write --title "Arbit research evidence"`. Until then, publication fails, alerts and retries.
- **Scope:** the service never touches the app, the league, weights or main.

**Manual procedures** (from the main checkout, with `uv run --env-file .env.local python scripts/model/dvp_prospective.py`):

| Situation | Command |
| --- | --- |
| See the state | `sh infra/systemd/install-dvp-prospective.sh --check`; `cat artifacts/dvp/prospective/2026/status.json` |
| Run now | `systemctl --user start arbit-dvp-prospective.service` (or `... sweep`) |
| A commitment failed | `... publish` (retries; never regenerates) |
| Check everything | `... verify` (ledger, captures, supplements and publications chains; files; exports; weeks without a pre-cutoff commitment) |
| An interrupted run | The next run recovers it. A staging folder is removed. An archive without a ledger entry is recorded before its cutoff, or recorded MISSED after it. An inconsistent archive is quarantined. |
| Stop the timer | `sh infra/systemd/install-dvp-prospective.sh --remove` |

## How it will be evaluated

`dvp_prospective.py evaluate` runs after the games. It follows these steps:
1. It checks the ledger chain and every archived file's hash.
2. It builds the 2026 labels fresh, the same way the forecasts' inputs were built.
3. It joins the labels to the stored forecasts without dropping any target. Labels that are valid, invalid or missing are counted per position.
4. **Phase B,** over the prospective weeks only: the frozen protocol.
   - D/ST B06 is **CONFIRMED** if it cuts RMSE by at least 1%, otherwise **NOT_CONFIRMED**.
   - For positions whose frozen candidate is B00, the best DvP variant is reported and never promoted.
5. **Phase C,** on the same D/ST rows: the frozen `decisions.py` with the frozen parameters, as one period. Confirmation needs B06 to clear 1.8 points of pairwise accuracy with net points gained.
6. **League-constrained D/ST choices:** exploratory and descriptive only, from the last league capture before each cutoff.
   - **rosterOnly:** start among a team's rostered D/STs.
   - **unownedPool:** stream among its rostered D/STs and every unowned one.
   - **claimablePool:** stream among its rostered D/STs and those ESPN reported as free agents. It is evaluated even when there are none.
   - **claimableWithWaivers:** stream with the units on waivers as well.
   - Teams without a decision are listed with the reason.
   - For each kind: the points of B06's pick minus B00's pick.

**The completion gate** (amendment 1, [`window.py`](../../../libs/arbit-model/src/arbit_model/dvp/window.py)):
- **A week is PROSPECTIVE** only when all of these hold:
  - its archive matches its ledger entry;
  - it was generated before the cutoff, and durably archived before it;
  - a verified external commitment predates the cutoff.
- **A week is LABELLED** only when every scheduled game is final (or recorded postponed or canceled) and every archived forecast on a final game has a label: valid, or invalid for a recorded reason.
- **The window:**
  - **COMPLETE** when all seven weeks are PROSPECTIVE and LABELLED. Only then does each frozen rule (Phase B and Phase C, separately) say CONFIRMED or NOT_CONFIRMED.
  - **INCOMPLETE_WINDOW** if any week was missed.
  - **BLOCKED** if any archive conflicts.
  - **INTERIM** otherwise.

Rehearsals and reconstructions are labeled as such and never say CONFIRMED.

**Checked on real data before the window:**
- **2025 rehearsal:** equivalence, plus the evaluation of 2025 weeks 12–18 with real labels. Its labels say REHEARSAL.
- **A scratch run on 2026 week 11:** forecasting after the cutoff recorded MISSED and exited 3; a reconstruction was stored as RETROSPECTIVE; a repeat did nothing; `evaluate --weeks 11` scored it as descriptive; `verify` passed.
- **A real `sweep`:** it skipped week 12 and waited on week 13 because week 12's 16 games have no results yet.

## What would change the conclusion

| Outcome | Meaning |
| --- | --- |
| D/ST B06 cuts 2026 weeks 12–18 RMSE by at least 1%, and Phase C clears 1.8 points with net points gained | The D/ST term is confirmed independently. It may be proposed to the owner as a Sit/Start contribution (OWN-074) |
| D/ST misses either minimum, or worsens | The 2025 result was not independent enough. D/ST stays research-only |
| A position's best DvP variant clears 1% | Still not promoted, because it wasn't frozen as a candidate. It is noted for a new, separately frozen test |

**A limitation:** seven weeks are one short window, about 220 D/ST team-games. A miss in one short window is evidence to weigh, not a final verdict.
