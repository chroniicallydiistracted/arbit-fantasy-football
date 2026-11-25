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
3. **Check readiness.** Every game of weeks before W must have a result and FFA lines, and the time must be past each one's availability (12:00 UTC the next day). Otherwise the run waits and retries.
4. **Forecast with the frozen estimator** through the adapter `arbit_model.dvp.shadow`:
   - targets come from the schedule, so no score or label is needed;
   - parameters are fit on 2016–2025;
   - the walk covers weeks 1 to W, because the residuals need each earlier week's point-in-time B00.
   - Only week W is archived.
5. **Capture the league's D/ST rosters,** read-only from the current snapshot. From week 13 the capture also records each unrostered D/ST's availability: FREE_AGENT, WAIVERS (dropped within the 24-hour hold) or WAIVERS_OR_FREE_AGENT (dropped 24–48 hours earlier). This is C05L-2026-PRO in the owner's Phase B audit ([LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md)).
6. **Archive once.** `forecasts.parquet`, `forecasts.csv`, `manifest.json`, `league.json`, and the inputs (the 2026 observations, schedule and targets store) go into `artifacts/dvp/prospective/2026/week-WW/`.
   - The folder is created by an atomic rename and refuses a second write; its files are read-only.
   - A ledger line holds every file's SHA-256 and the previous line's hash.
7. **Export** the forecasts, manifest, league capture and ledger to [`prospective/2026/`](prospective/2026) for committing. A push to GitHub gives an external timestamp.

**The adapter is the frozen estimator.**
- On synthetic seasons, given the frozen walk's targets, it reproduces `walkforward.walk` bit for bit (`test_dvp_shadow.py`).
- On the real 2025 holdout it reproduces every frozen forecast column within 7.1×10⁻¹⁵ points ([rehearsal-2025.json](prospective/rehearsal-2025.json)).
  - Only the B09 placebo controls differ: they draw random numbers per batch.
  - The adapter also forecasts 8 cells whose labels later turned out invalid. The frozen walk dropped them before forecasting (AUD-05); the adapter keeps them.

## Status of the window

| Week | Cutoff (UTC) | Inputs complete from (UTC) | Status |
| --- | --- | --- | --- |
| 12 | 2026-11-26 01:00 | (weeks 1–11 done) | **PROSPECTIVE:** archived 2026-11-24 23:12:45. GitHub recorded the push of `168196d` at 23:13:15 |
| 13 | 2026-12-04 01:15 | 2026-12-01 12:00 | Pending |
| 14 | 2026-12-11 01:15 | 2026-12-08 12:00 | Pending |
| 15 | 2026-12-18 01:15 | 2026-12-15 12:00 | Pending |
| 16 | 2026-12-25 01:15 | 2026-12-22 12:00 | Pending |
| 17 | 2027-01-01 01:15 | 2026-12-29 12:00 | Pending |
| 18 | 2027-01-10 18:00 | 2027-01-05 12:00 | Pending |

The "inputs complete" times assume nflverse publishes the week's statistics by then. If it hasn't, the harness waits.

**Running weeks 13–18 on time.** A systemd user timer runs the `sweep` every six hours from the main checkout (`infra/systemd/arbit-dvp-prospective.*.template`, installed by `sh infra/systemd/install-dvp-prospective.sh`). It needs the owner's approval to install, because it outlives a session. Without it, someone must run `sweep` in each week's window.

**Missed weeks** are recorded in the ledger as `MISSED` and excluded. A later reconstruction is stored apart as `RETROSPECTIVE`, evaluated separately and never counted.

## How it will be evaluated

`dvp_prospective.py evaluate` runs after the games. It follows these steps:
1. It checks the ledger chain and every archived file's hash.
2. It builds the 2026 labels fresh, the same way the forecasts' inputs were built.
3. It joins the labels to the stored forecasts without dropping any target. Labels that are valid, invalid or missing are counted per position.
4. **Phase B,** over the prospective weeks only: the frozen protocol.
   - D/ST B06 is **CONFIRMED** if it cuts RMSE by at least 1%, otherwise **NOT_CONFIRMED**.
   - For positions whose frozen candidate is B00, the best DvP variant is reported and never promoted.
5. **Phase C,** on the same D/ST rows: the frozen `decisions.py` with the frozen parameters, as one period. Confirmation needs B06 to clear 1.8 points of pairwise accuracy with net points gained.
6. **League-constrained D/ST choices:** exploratory and descriptive only.
   - **Start:** among a team's rostered D/STs.
   - **Stream:** among its rostered D/STs and those on no roster.
   - For each, the points of B06's pick minus B00's pick.

Until all seven weeks are archived or missed and labeled, results are **INTERIM** and carry no label. Rehearsals and reconstructions are labeled as such and never say CONFIRMED.

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
