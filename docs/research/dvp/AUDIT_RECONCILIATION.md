# M3-3 DvP: reconciliation of the external audit (final directive)

The owner's [final directive](M3-3_AUDIT_REMEDIATION_AND_COMPLETION_DIRECTIVE_FINAL.md) asks for each external finding to be checked independently against the local evidence before anything is changed. The machine-readable register is [audit-findings.json](audit-findings.json). It uses stable IDs and records each finding's:
- assertion and the requirement it relates to;
- implementation at the reviewed commit `2e2520f`;
- evidence and tests;
- disposition and reasoning;
- remediation and expected effect;
- completion criteria and closure status.

Later tasks update the same register.

Started 2026-11-25 in TASK-20261124-010.

## Dispositions

| ID | Finding | Disposition | Closure |
| --- | --- | --- | --- |
| AUD-01a | No unattended external timestamp for archives | AGREE | IN_PROGRESS: built and verified live; the deploy key needs the owner's registration |
| AUD-01b | Data readiness not established | PARTIALLY_AGREE | RESOLVED_VERIFIED |
| AUD-01c | Window completion: any completed game, missed weeks accepted | AGREE | RESOLVED_VERIFIED |
| AUD-01d | Archive steps not transactional or recoverable | PARTIALLY_AGREE | RESOLVED_VERIFIED |
| PB-AUD-07 | Prospective availability from a heuristic, incomplete captures | AGREE | RESOLVED_PENDING_FUTURE_DATA (from week 13) |
| PB-AUD-01 | Live reconciliation by id, type and status only | AGREE | RESOLVED_VERIFIED |
| PB-AUD-02 | Trades and waiver timing in the ownership replay | AGREE (no effect on weeks 1–11) | RESOLVED_VERIFIED |
| PB-AUD-03 | Availability rule not validated against snapshots | AGREE | RESOLVED_VERIFIED |
| PB-AUD-04 | Bootstrap drops zero-change weeks | AGREE (reproduced: −96.03 to +74.02) | RESOLVED_VERIFIED |
| PB-AUD-05 | Streaming ignores shared acquisitions and roster feasibility | AGREE | RESOLVED_VERIFIED |
| PB-AUD-06 | Manager starts compared across different decision times | PARTIALLY_AGREE (gap real; no decision affected) | RESOLVED_VERIFIED |
| PB-AUD-08 | League inputs read from the live database | AGREE | IN_PROGRESS (inputs pinned; the audit rerun is remediation 7) |
| PB-RESULTS | Phase B v1 totals and the week-11 sensitivity (directive §8) | AGREE (recomputed) | RESOLVED_VERIFIED |
| AUD-06 | Simulation suite outstanding | AGREE | RESOLVED_VERIFIED ([report](SIMULATION_AUD06.md)) |
| AUD-07 | 1.8-point threshold described as exact | AGREE (reproduced; a heuristic, not an equivalence) | RESOLVED_VERIFIED ([report](THRESHOLDS_AUD07.md)) |

No finding has been rejected so far. Three are only partly accepted.
- **AUD-01b:**
  - The refresh dependency the reviewer asked about already exists: the worker's statistics lane imports changed nflverse files daily, and imported the 2026 player statistics on 2026-11-22, -23 and -24.
  - The harness already waited for every earlier result.
  - What was missing was completeness per cell and a stated cause for each wait.
- **AUD-01d:**
  - Staging plus an atomic rename, read-only files and a locked, fsynced ledger already existed.
  - Durability, a run-level lock, recovery and archival timing were missing.
  - One consequence was serious: a crash between the rename and the ledger append would have blocked the week until its cutoff.

## Phase A: prospective operations (resolved in TASK-20261124-010)

**AUD-01c (the completion gate)** was the first thing done, because its correction had to precede any week-12 outcome.
- **The amendment:** [`config/dvp/prospective-amendment-1.json`](../../../config/dvp/prospective-amendment-1.json) and [`window.py`](../../../libs/arbit-model/src/arbit_model/dvp/window.py) were committed and pushed in `463a6c0` at 2026-11-25 03:37 UTC. The first week-12 kickoff is 2026-11-26 01:00 UTC.
- **What it changes:**
  - A missed week makes the window INCOMPLETE_WINDOW.
  - Only a COMPLETE window lets the frozen rules say CONFIRMED or NOT_CONFIRMED, separately for Phase B and Phase C.
  - A week is complete only when every scheduled game is final and every archived forecast is labelled. A game postponed or canceled for 4 days is recorded instead.
- **Untouched:** the original `prospective.json`, whose hash the amendment records and the week-12 archive also records; the frozen methods; the thresholds; the window; and the week-12 archive.
- **Note:** the original declaration itself allowed a confirmation with missed weeks excluded. So the old code matched its declaration, and it is the declared rule that is now stricter, under DEC-03.

**AUD-01a (external evidence):**
- **Commitments:** each archive gets a sanitized commitment on branch `research-evidence/dvp-prospective`. It holds the ledger entry, every file's SHA-256 and the forecasts CSV; the league capture appears only as a hash.
- **Verification:** the pushed bytes are read back. GitHub's repository activity record of the push is the timestamp.
- **Live check:** week 12's commitment was pushed and read back equal at 2026-11-25 03:46:49 UTC, before its cutoff. Week 12 also has its original evidence: GitHub received the same files in the push of `168196d` at 2026-11-24 23:13:15 UTC.
- **Credential:** unattended publication needs a key that can write to this repository only. It is generated at `~/.config/arbit/research-evidence/id_ed25519`, but registering it on GitHub was refused by the session's permission classifier, so it waits for the owner. Until then the timer's publication attempts fail, are recorded, alert and retry each run.

**AUD-01b (readiness):** every earlier game gets one of eight states. The harness reports which state blocks a week, and the live sweep shows it:
- week 13 waits on 16 week-12 games (AWAITING_RESULT);
- 162 games are ELIGIBLE_VERIFIED;
- one is RETRIEVED_INVALID: 2026 week 7 TB–CAR, a refused line, which doesn't block.

**AUD-01d (the archive transaction):** [`archive.py`](../../../libs/arbit-model/src/arbit_model/dvp/archive.py).
- **Each run:** takes the season lock, writes and fsyncs every file, renames the folder atomically and records `archivedAt`.
- **Recovery** resolves:
  - staging leftovers, which are removed;
  - an archive without a ledger entry: recovered before its cutoff, or recorded MISSED after it;
  - an archive that disagrees with its own manifest, which is quarantined.
- **Retries:** publication is retried; a forecast is never regenerated.
- **Tests:** failure injection at every step, killed processes, a concurrent run and fsync coverage.

**PB-AUD-07 (the league capture):**
- **The problem:** the week-12 capture labelled every unowned D/ST a free agent. In the same snapshot, 32 seconds before the forecast, ESPN reported all 19 on waivers.
- **ESPN's pattern:** from the snapshot history, an unowned unit whose game has started goes on waivers until Wednesday's processing. A Tuesday forecast therefore sees no free agents at all.
- **The new capture:**
  - reads one snapshot in one transaction;
  - lists every team, including any with no D/ST;
  - records ESPN's observed state for all 32 units, with contradictions as UNKNOWN;
  - keeps the drop-time rule only as a labelled fallback.
- **Decision-time captures:** each run between a week's archive and its cutoff records the league again. The last capture before the cutoff is the decision-time state.
- **Week 12:** has a separately versioned supplement, read from its original snapshot. Its rosters equal the original capture's. The archive is unchanged.

**Operations:**
- **Alerts:** reach the Windows desktop from the systemd service context; verified: "shown".
- **Database:** the harness's sessions are read-only on the server. A test write was refused with `ReadOnlySqlTransaction`.
- **The timer:**
  - runs at 00:17, 06:17, 12:17 and 18:17 UTC from 2026-11-25 to 2027-01-15;
  - catches up missed runs at the next wake (`Persistent`);
  - the 00:17 run falls inside the PC's daily 00:10–00:35 UTC wake window;
  - disables itself once every week is final and every commitment is verified.

- **PB-AUD-06:** the method gap was real. The receipt lacked exact candidate sets, and starters were not checked against the cutoff. But the evidence shows no decision was affected: all 28 finalized starters were held at the cutoff.

## Phase B corrections (resolved in TASK-20261124-011)

Details: [LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md#corrected-evaluation-v2-final-directive-2026-11-25) and [FFA_2026_DATA_INVENTORY.md](../FFA_2026_DATA_INVENTORY.md).

- **§8 recomputed (PB-RESULTS):**
  - every total in the reviewer's table matches;
  - week 11 contributes +92 to streaming, and +46 becomes −46 without it;
  - the all-week start/sit interval is −96.03 to +74.02, as the reviewer computed.
- **PB-AUD-08:**
  - **The bundle:** the normalized league inputs are pinned in one read-only transaction as a hashed local bundle (manifest `c354dcca…`), and the corrected experiment runs from it alone.
  - **Still to do:** remediation 7 reruns the experiment from the bundle and compares.
- **PB-AUD-01 (live content):**
  - 536 of 536 transactions are content-equal, and the union of pages equals the store.
  - The four FUTURE_ROSTER records are located on period 8's page.
  - All 11 lineups have identical membership, slots, points and positions. The only differences are players' current NFL teams.
- **PB-AUD-02 (ownership):**
  - The replay now fails closed on unsupported ownership changes and on waivers without a processing time, and validates the draft.
  - It equals all 1,522 snapshots at their own times.
- **PB-AUD-03 (availability rule v2):**
  - **Validation:** 99.3% holdout agreement against ESPN's reported states, against 22% for v1.
  - **Its errors** are two documented patterns: waiver-run drops and Tuesday locks. A rule v3 is proposed for future validation, not adopted.
  - **A defect caught in a trial run:** the game lock compared with ≤ at the exact cutoff. It was fixed to the declared rule before the recorded run.
- **PB-AUD-04:** the bootstrap uses every evaluated week. Zero-change weeks count as zero, and the block counts are recorded.
- **PB-AUD-05:**
  - Every B06 recommendation of an unowned unit collides with another team's; 57 of its 88 claimable picks need a drop.
  - Streaming is reported as independent single-manager recommendations only.
- **C05L-2026-EXP v2:**
  - **The rule** was declared and pushed in `671b5ef` before computing. v1 is preserved.
  - **Samples are unchanged.** Claimable streaming moves from +46 to +110, all from week 9's snapshot-verified pool, a full collision.
  - **The conclusion is unchanged:** inconclusive.

## AUD-06 and AUD-07 (resolved in TASK-20261125-001)

**AUD-06:** a predeclared suite of 33,100 repetitions ran Arbit's own estimators and complete procedure on synthetic leagues with a known signal ([report](SIMULATION_AUD06.md)).
- **False promotion:** none, without a signal, in 900 position-repetitions.
- **Strong signals** (like D/ST) were promoted 80–90% of the time; moderate ones (like RB) about 2%. Real QB, RB and WR gains are what a moderate signal produces.
- **Estimators:** k is recovered within 15–19%, slightly conservatively.
- **Intervals:** those resting on few blocks undercover. The league bootstrap is the worst, at 77–87%.
- **Acceptance:** A8 fails and A3 for WR is inconclusive; both are reported, not re-scored.
- **Earlier conclusions:** none changes, and no material methodological defect was found.

**AUD-07:** the 1.8-point derivation reproduces exactly (1.82) but rests on assumptions the data don't meet, so it is a practical heuristic ([report](THRESHOLDS_AUD07.md)).
- **D/ST B06** stays PROMISING across thresholds from 0 to 2% and 0 to 3 points.
- **RB** would be PROMISING at 0.5% or less.
- **No threshold changed.**

## Still to do (later tasks of this directive)

The research eligibility registry, and the comprehensive audit (remediation 7, which also reruns the pinned Phase B evaluation for PB-AUD-08). AUD-01a closes when unattended publication is verified with the registered key. Each closes in this register.
