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

## How it will be evaluated

1. **When the 2026 regular season is complete,** rebuild the FFA targets with the 2026 games (`build_targets.py`, a new index). Rerun the DvP audit on it: 2026 cells, reconciliation, projection firewall.
2. **Check out the frozen code** (`f75868b`; `scripts/model/dvp.py` later gained only reporting) and verify every frozen method hash.
3. **Forecast weeks 12–18 of 2026,** each before its own preweek cutoff, from the actuals available then. Parameters are fit on 2016–2025.
   - Weeks 1–11 of 2026 supply in-season history only. They are not evaluated: their results were known at the freeze.
4. **Score** D/ST B06 and each position's B00, plus the best DvP variants for information, against the 2026 actuals with the frozen protocol and rule.

This needs a small `prospective` stage that accepts the new targets index while verifying the method hashes. It is to be written then, and must not change any frozen method file.

## What would change the conclusion

| Outcome | Meaning |
| --- | --- |
| D/ST B06 cuts 2026 weeks 12–18 RMSE by at least 1% | The D/ST term is confirmed independently. It may be proposed to the owner as a Sit/Start contribution |
| D/ST misses the minimum, or worsens | The 2025 result was not independent enough. D/ST stays research-only |
| A position's best DvP variant clears 1% | Still not promoted (it wasn't frozen as a candidate). It is noted for a new, separately frozen test |

**A limitation:** seven weeks are one short window, about 220 D/ST team-games. With a 2025 interval of −0.39 to −0.11 points, a true effect of that size should usually show. A miss in one short window is evidence to weigh, not a final verdict.
