# M3-3 continuity: where the DvP work stands

Specification §0 rule 1, §4 and §9 Phase 0 (T29). Manifest: [continuity-manifest.json](continuity-manifest.json).

## The existing M3-3 study (v0)

| | |
| --- | --- |
| **Who and when** | Claude, in TASK-20261123-004 (M3 slice 3b), 2026-11-23. Committed in `c8c0396`, merged to `main` in `b3c0a9a` (PR #6) |
| **Owner decision it serves** | OWN-068: sit/start projections must explain why, including the opponent's defense against the position |
| **Engineering record** | ENG-056 (team environment and defense against the position) |
| **Script** | [scripts/model/defense_position_study.py](../../../scripts/model/defense_position_study.py), using `split_half` from [ffa_signal_study.py](../../../scripts/model/ffa_signal_study.py) |
| **Receipt** | [defense-position-study-2026-11-23.json](../defense-position-study-2026-11-23.json) (targets index `4afbd836…`, regular seasons 2016–2025) |
| **Write-up** | [team-features-2026-11-23.md](../team-features-2026-11-23.md), section "How fast a defense's record against a position means something" |
| **Method** | Covered in [V0_REPRODUCTION.md](V0_REPRODUCTION.md): FFA points per team-game and position, inverted to the defense; D/ST by the offense; same-season leave-one-out adjustment; odd and even NFL weeks with at least 4 games each; k = m(1 − r)/r |
| **Used by** | `arbit_model.feature_specs.SHRINKAGE`: the 3b team features shrink defense-against-the-position with v0's k. Nothing runs in a service, so no live weight depends on it |

**Preserved:**
- The script, its receipt, the shared split-half script and the signal-study receipt are byte-identical. Their SHA-256 hashes are in the manifest, and T29 checks them on every test run.
- The extension writes new receipts here and new runs under `artifacts/dvp/<run>/`.

## Inventory (updated 2026-11-24)

| Phase | Work | Status |
| --- | --- | --- |
| 0 | Continuity manifest, source map, provenance allowlist | EXECUTED |
| 0 | v0 lineage audit: projection-free, league scoring, completed games | PASSED (A11) |
| 0 | v0 reproduction: exact rerun and independent recompute | REPRODUCED |
| 0 | Discrepancies dispositioned (misattribution, missing D/ST lines, refused lines, unequal halves) | EXECUTED ([V0_REPRODUCTION.md](V0_REPRODUCTION.md)) |
| 1 | Completed-game observation pipeline, D/ST orientation, row lineage, as-of index | EXECUTED |
| 1 | Tests T01–T40, all of them | PASSED (`libs/arbit-model/tests/test_dvp_*.py`) |
| 1 | Data quality, provenance and finality reports | EXECUTED |
| 1 | Full D/ST coverage (the R-072 repair, OWN-075) | DONE: 5,278 of 5,278 team-games on targets `6ffb62fb…` |
| 2 | A00–A12 reliability lab | EXECUTED ([RELIABILITY_REPORT.md](RELIABILITY_REPORT.md)) |
| 3 | B00–B12 walk-forward; development folds and 2024 validation | EXECUTED ([BACKTEST_REPORT.md](BACKTEST_REPORT.md)) |
| 4 | Frozen manifest, 2025 conditional holdout, decisions | EXECUTED: D/ST PROMISING ([MODEL_CARD.md](MODEL_CARD.md)) |
| 4 | 2026 weeks 12–18 prospective confirmation | FROZEN before the games, scored after the season ([PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)) |
| 5 | C00–C05 player-level start/sit, D/ST (the only group past the gate) | EXECUTED: PROMISING; C03 BLOCKED. League-constrained evaluation: 2016–2025 NOT_APPLICABLE (OWN-076), 2026 weeks 1–11 exploratory, weeks 12–18 prospective ([LEAGUE_CONSTRAINED_2026.md](LEAGUE_CONSTRAINED_2026.md)) |
| — | Verify-only mode: every artifact read back, every receipt reproduced | PASSED ([verify-receipt.json](verify-receipt.json)) |

## What changed from v0, and what did not

- **Changed:**
  - The extension takes each opponent from the schedule.
  - Refused and missing cells stay missing.
  - Intervals are reported.
  - On that basis, TE's k is 43.1 (v0 37.6) and K's is 41.8 (v0 49.4), and the WR, TE and K intervals overlap.
- **Not changed:**
  - v0's files.
  - The canonical FFA targets.
  - `feature_specs.SHRINKAGE`, which still holds v0's constants.
  - Any service.

  Whether DvP gets a weight at all, and with which k, is for Phase B (B03/B04), measured against the offense-only B00.

## Records

The repository's own records are kept rather than parallel copies:
- **Decisions:** [decision register](../../project/decision-register.md), OWN-074 and ENG-057.
- **Risks:** [known issues](../../project/known-issues.md), R-072 to R-074.
- **History:** [changelog](../../project/changelog.md).
- **Handoffs:** the governance task TASK-20261123-005 and its handoff.
