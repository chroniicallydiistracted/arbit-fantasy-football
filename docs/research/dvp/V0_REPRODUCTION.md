# M3-3 v0 reproduction and discrepancies

Specification §4 (A01, T29). Receipt: [v0-reproduction.json](v0-reproduction.json), from audit run `phase1-audit-20261123T222517Z` on code `556e1cb`. v0 is the odd/even study in [defense-position-study-2026-11-23.json](../defense-position-study-2026-11-23.json), created in TASK-20261123-004 ([continuity](M3-3_CONTINUITY.md)).

## Result: REPRODUCED

- **Exact rerun:** `scripts/model/defense_position_study.py`, unchanged, reran on the pinned targets index (`4afbd836…`). Its output equals the v0 receipt in every field except `startedAt` and `reportSha256`, the hash that covers `startedAt`.
- **Independent recompute:** `arbit_model.dvp.reliability` rebuilt v0 from the targets with v0's own data choices. All 12 measures match to the receipt's precision: units, r to 3 decimals and k to 1 decimal.
- **v0's files are unchanged:** their SHA-256 hashes are pinned in [continuity-manifest.json](continuity-manifest.json) and checked by T29.

## Why WR's k is 44.1 and not 42.6

v0 converts the split-half correlation with k = m(1 − r)/r, where m is the mean half size over all units. Seventeen-game seasons split 8/9, so m = 8.2469, not 8.

| Measure | r (unrounded) | m | k (v0) | k if halves were 8 | One game's reliability | w(8) |
| --- | --- | --- | --- | --- | --- | --- |
| WR raw | 0.15766 | 8.2469 | 44.06 | 42.74 | 0.0222 | 15.4% |
| WR adjusted | 0.16411 | 8.2469 | 42.00 | 40.75 | 0.0233 | 16.0% |
| RB raw | 0.30567 | 8.2469 | 18.73 | 18.17 | 0.0507 | 29.9% |
| QB adjusted | 0.27112 | 8.2469 | 22.17 | 21.51 | 0.0432 | 26.5% |
| D/ST raw | 0.46806 | 8.1302 | 9.24 | 9.09 | 0.0977 | 46.4% |

The specification's 42.63 uses r rounded to 0.158 with m = 8. Nothing in v0's arithmetic is wrong. Using the mean half size is an approximation, because the halves differ in size from unit to unit; A05 will compare it with a variance-component fit.

## Discrepancies found, and how each is dispositioned

| # | Discrepancy | Effect on v0 | Disposition |
| --- | --- | --- | --- |
| 1 | **Opponent misattribution.** nflverse's schedule codes the Raiders as OAK (2016–2019) and the Chargers as SD (2016), while statistics use LV and LAC. The targets take a player's opponent from the schedule by comparing these codes. For the home team the comparison fails, so the team itself is recorded as the opponent. | In 40 home games, 1,327 player lines (3,994 FFA points) were credited to the team's own defense. In 2016, OAK and SD each show 23 games allowed, and each visiting defense in those games lost one. This affects position measures only. | v0 stays as the baseline but is not used for inference. `v0-validated` takes every opponent from the schedule. Canonical fix: an owner decision (R-072). |
| 2 | **Missing D/ST lines.** The same code mismatch makes the D/ST scorer skip every game involving those teams. | 156 regular-season team-games have no D/ST line. Five offense-seasons drop out (315 units, not 320), and other D/STs lose one to four games each. | Missing, not zero. Full D/ST coverage is BLOCKED until the canonical scorer is repaired (R-072). |
| 3 | **Refused lines summed as zero.** 58 team-game-position cells hold a line the scorer refused (a statistic it couldn't verify, null points). v0's sum treated it as 0. | Slight downward bias in 58 of 26,390 position cells. | `v0-validated` excludes those cells. |
| 4 | **Unequal halves.** Halves are 5–9 games. | k is an approximation (see above). | A05 (variance components) and T12. |
| 5 | **Retrospective adjustment.** The leave-one-out baseline uses the offense's later games. | Fine for description; not a forecast. | Phase B builds point-in-time baselines (B00–B03). |

No provider projection was found anywhere in v0's lineage ([SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md)), so v0 is not contaminated in the specification's sense.

## v0's method on validated observations (`v0-validated`, A01)

Same method: odd and even NFL weeks, at least 4 games per half, the same-season leave-one-out adjustment. The data is different: cells are attributed by the schedule, and invalid or missing cells are excluded. Intervals come from three methods:
- a Fisher interval, which assumes independent units and is the narrowest;
- 2,000 seeded bootstrap resamples of units (seed 1729);
- 2,000 of whole seasons, which is the honest one, because one game links two teams and a season's units share conditions.

| Measure | v0 units / r / k | Validated units | r | Spearman | k | w(8) | k 95%, units | k 95%, seasons |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QB raw | 320 / 0.213 / 30.6 | 320 | 0.217 | 0.205 | 29.8 | 21% | 18–60 | 18–68 |
| QB adjusted | 320 / 0.271 / 22.2 | 320 | 0.271 | 0.293 | 22.2 | 26% | 15–39 | 13–46 |
| RB raw | 320 / 0.306 / 18.7 | 320 | 0.297 | 0.287 | 19.5 | 29% | 12–36 | 11–48 |
| RB adjusted | 320 / 0.292 / 20.0 | 320 | 0.281 | 0.289 | 21.0 | 28% | 14–38 | 12–41 |
| WR raw | 320 / 0.158 / 44.1 | 320 | 0.163 | 0.152 | 42.2 | 16% | 23–113 | 21–299 |
| WR adjusted | 320 / 0.164 / 42.0 | 320 | 0.163 | 0.141 | 42.4 | 16% | 22–142 | 20–231 |
| TE raw | 320 / 0.180 / 37.6 | 320 | 0.160 | 0.161 | 43.1 | 16% | 23–145 | 25–143 |
| TE adjusted | 320 / 0.171 / 40.1 | 320 | 0.164 | 0.135 | 42.1 | 16% | 22–137 | 23–160 |
| K raw | 320 / 0.143 / 49.4 | 320 | 0.164 | 0.163 | 41.8 | 16% | 23–122 | 21–145 |
| K adjusted | 320 / 0.130 / 55.3 | 320 | 0.144 | 0.144 | 48.9 | 14% | 25–182 | 23–291 |
| D/ST raw (offense) | 315 / 0.468 / 9.2 | 315 | 0.468 | 0.457 | 9.2 | 46% | 7–13 | 8–12 |
| D/ST adjusted (offense) | 315 / 0.472 / 9.1 | 315 | 0.472 | 0.453 | 9.1 | 47% | 7–13 | 8–10 |

What this does and does not show:
- **Every measure repeats more than chance.** Every Fisher interval for r excludes 0; the lowest is K adjusted, 0.035–0.250. In up to 1.6% of the season resamples for K, TE and WR, the correlation fell to 0 or below, so no k exists for those resamples.
- **WR, TE and K can't be ranked.** Their k estimates (42–49) have intervals spanning roughly 20 to well over 100 games. v0's ordering (TE 37.6 < WR 44.1 < K 49.4) was partly noise, and the misattribution moved TE and K the most.
- **RB and QB repeat more** (k about 20–30). For QB, adjusting for the offenses faced again helps: 29.8 raw against 22.2 adjusted.
- **The D/ST matchup is the clear signal:** k ≈ 9 with a tight interval, on 315 of 320 offense-seasons.
- **This is repeatability, not forecasting.** w(n) is credibility inside a DvP estimate, not a share of the Sit/Start model (§6). Whether any of it improves next-game forecasts over the offense-only B00 is Phase B's question.

**Diagnostics:**
- **Pairs and half sizes:** both are in the receipt. Most halves have 8 games, then 9, then 7. Five D/ST halves have 5–6 games, where an opponent's missing lines remove weeks.
- **Half means:** within 3 SD except 1–4 halves per measure.
- **Scatter plots:** PLANNED with A00/A02. The pairs behind them are saved as `artifacts/dvp/<run>/v0/pairs-*.parquet` (ignored by git; hashes are in the run manifest).

## 2025 exposure

v0 used 2016–2025 descriptively. So did this reproduction and `v0-validated`. No 2025 forecast has been made or inspected, and no forecast parameter has been tuned. 2025 can therefore serve at best as a conditionally held-out evaluation (`CONDITIONALLY_HELD_OUT`), and only for forecasts whose parameters come from earlier seasons. Independent confirmation needs 2026 games forecast after a registered freeze (§5, §12).
