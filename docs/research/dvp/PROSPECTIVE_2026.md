# M3-3 DvP prospective confirmation, 2026 weeks 12–18

Specification §9 Phase 4 and §12: "only a future, prospectively frozen 2026+ run can confirm independently." TASK-20261124-003.

## What was frozen, and when

At **2026-11-24 03:16 UTC**, before the first 2026 week-12 game (kickoff 2026-11-26 01:00 UTC), [`config/dvp/frozen.json`](../../../config/dvp/frozen.json) fixed:
- the method: SHA-256 hashes of `walkforward.py`, `lab.py`, `asof.py`, `observations.py`, `reliability.py`, `provenance.py`, `teams.py`, `scripts/model/dvp.py`, `config/dvp/base.json`, `config/dvp/backtest.json` and `config/dvp/frozen-candidates.json`, at code `f75868b`;
- **the candidates:** D/ST B06; B00 (no DvP term) for QB, RB, WR, TE and K;
- **the protocol:** RMSE relative to B00, week-block bootstrap (2,000, seed 1729), and the 1% practical minimum;
- **the decision rule:** the same as the 2025 holdout;
- **the prospective window:** 2026 regular-season weeks 12, 13, 14, 15, 16, 17 and 18.

None of those games had been played at the freeze.

**Phase C was frozen too.** At **2026-11-24 06:57 UTC**, also before the week-12 kickoff, [`config/dvp/frozen-phase-c.json`](../../../config/dvp/frozen-phase-c.json) fixed:
- `decisions.py`;
- the start/sit rule (`config/dvp/sitstart.json`) and its parameters.

The 2026 window therefore confirms both levels: forecast error and D/ST start/sit choices ([PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md)).

## How it will be evaluated

1. **When the 2026 regular season is complete,** rebuild the FFA targets with the 2026 games (`build_targets.py`, a new index). Rerun the DvP audit on it: 2026 cells, reconciliation, projection firewall.
2. **Check out the frozen code** (`git worktree add <dir> 165d140`, the freeze commit; its method files equal `f75868b`'s). `dvp.py verify` confirms that every frozen hash matches there. On `main`, `scripts/model/dvp.py` later gained reporting, Phase C and verify, so the frozen holdout command refuses on `main`, as designed. The 2025 holdout was rerun from that tree on 2026-11-24 with forecasts equal to within 7×10⁻¹⁵ points (the last bit of polars' parallel sums) and identical results.
3. **Forecast weeks 12–18 of 2026,** each before its own preweek cutoff, from the actuals available then. Parameters are fit on 2016–2025.
   - Weeks 1–11 of 2026 supply in-season history only. They are not evaluated: their results were known at the freeze.
4. **Score** D/ST B06 and each position's B00, plus the best DvP variants for information, against the 2026 actuals with the frozen protocol and rule.
5. **Score Phase C** on the same window's D/ST rows: `decisions.units`, `pairs`, `metrics` and `decide` from the frozen `decisions.py`, with the frozen parameters. Confirmation needs B06 to clear 1.8 points of accuracy with net points gained.

This needs a small `prospective` harness that accepts the new targets index while verifying the method hashes. It is to be written then, as a new file outside the frozen method, and it calls the frozen tree's library functions unchanged.

## What would change the conclusion

| Outcome | Meaning |
| --- | --- |
| D/ST B06 cuts 2026 weeks 12–18 RMSE by at least 1% | The D/ST term is confirmed independently. It may be proposed to the owner as a Sit/Start contribution |
| D/ST misses the minimum, or worsens | The 2025 result was not independent enough. D/ST stays research-only |
| A position's best DvP variant clears 1% | Still not promoted (it wasn't frozen as a candidate). It is noted for a new, separately frozen test |

**A limitation:** seven weeks are one short window, about 220 D/ST team-games. With a 2025 interval of −0.39 to −0.11 points, a true effect of that size should usually show. A miss in one short window is evidence to weigh, not a final verdict.
