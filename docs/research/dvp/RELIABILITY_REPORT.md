# M3-3 DvP reliability report (Phase 2: A00, A02–A10, A12)

Specification §5 Phase A, §6, §7, §11.6. TASK-20261124-001. Receipt: [reliability-results.json](reliability-results.json):
- code `3a1fe11`, run with `scripts/model/dvp.py reliability --config config/dvp/reliability.json`;
- audit run `phase1-audit-20261124T024442Z` on the R-072-repaired targets index `6ffb62fb…`;
- seed 1729, 2,000 bootstrap replicates, 1,000 random splits, 1,000 permutations.

Two runs gave identical results and byte-identical plots. Every number comes from Arbit's own FFA actuals of completed regular-season games, 2016–2025. No provider projection appears anywhere (`forbidden_vendor_projection_dependencies = 0`).

**What this is and isn't.** This phase measures *repeatability*: whether a defense keeps allowing more (or fewer) FFA points at a position than its opponents usually score. It is retrospective. The "adjusted" measure subtracts what the offense scored in its *other* games that season, including later ones, so nothing here is a forecast. Whether any of it improves next-game forecasts over the offense-only B00 is Phase B's question.

**Terms:**
- **The unit:** the defense for QB, RB, WR, TE and K. For D/ST it is the offense: the points opposing D/STs score against it.
- **k ("games for half signal"):** the game noise variance divided by the variance of true unit-season tendencies. After n games a unit's own record earns w(n) = n / (n + k).
- **Odd/even k** is v0's split-half shortcut. **REML k** comes from variance components that use every unit's actual game count (A05).

## Conclusions by position

| Group | v0 k (odd/even, adjusted) | **REML k, adjusted** (95% season bootstrap) | w(8) | Within-week permutation p (Holm, 12 tests) | Changes within a season? | Carries into next season? r (95%) | What repeats (A09, REML k) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **D/ST conceded by the offense** | 9.1 | **7.2** (6.0–8.6) | 53% | 0.012 | No: flat across 1–17 weeks apart | Yes, 0.40 (0.33–0.47) | Points-allowed tier 7.8, yards-allowed tier 8.0, sacks 10.1. Takeaways 43 and return TDs 107 barely repeat |
| **RB** | 20.0 | **19.5** (15.8–26.9) | 29% | 0.012 | No clear change | Yes, 0.28 (0.19–0.36) | Rushing yards 13.5; receptions 32; rushing TDs 41; receiving TDs about 850 (none) |
| **QB** | 22.2 | **24.2** (16.2–42.3) | 25% | 0.012 | **Yes:** odd/even r exceeds first-vs-second-half r by 0.12 (0.02–0.20); weeks-apart covariance decays | Yes, 0.29 (0.18–0.40) | Passing yards 28; passing TDs 74; turnovers 58 |
| **WR** | 42.0 | **26.7** (17.8–58.3) | 23% | 0.012 adjusted; **0.077 raw** | Slight decay, not established | Yes, 0.23 (0.11–0.34) | Receptions 38, receiving yards 40; receiving TDs 182 |
| **TE** | 40.1 | **37.4** (23.0–96.7) | 18% | 0.012 | Not established | Weakly, 0.16 (0.08–0.23) | Receptions 44, yards 48; TDs 180 |
| **K** | 55.3 | **50.5** (33.2–101.5) | 14% | 0.018 | Not established | Weakly, 0.14 (0.08–0.20) | Field goals 164 (none); extra points 30 |

**In plain terms:**
1. **Every group's tendency is real but small, except D/ST's.** Every adjusted measure rejects "no unit tendency" after Holm's correction, but one game's reliability is only 2–5% for the position groups (A05). Against that, the offense's own production at a position settles in 4–7 games for QB, RB, WR and TE (A03 `kFaced`). **Per game, a team's result says about three to seven times more about its offense at that position than about the defense it faced.**
2. **D/ST is the exception.** What an offense gives up to D/STs is about 12% reliable per game, k ≈ 7. It is stable across the season and from one era to the next, carries into the next season, and comes from points and yards allowed and sacks taken, not takeaways or return touchdowns.
3. **v0's WR k of 44 was an unlucky split.** Odd/even sits at the 2.5th percentile of 1,000 random balanced splits for WR (r 0.163 against a random-split median of 0.235). The variance-component fit uses every game once and agrees with the random splits: about 27, still wide (18–58). TE and K stay weakest, near 37 and 50.
4. **The order among WR, TE and K is not established** (joint season bootstrap: P(k_TE < k_WR) = 0.50, P(k_K < k_WR) = 0.42). QB and RB are probably below them (0.89–0.92), and D/ST below everything (≥ 0.998).
5. **Volume and yardage repeat; touchdowns mostly don't.** A defense's tendency to allow yards and receptions persists. Its touchdowns allowed to WRs and TEs are noise (k ≈ 180).
6. **QB is the one group whose tendency moves within a season.** A recent-window estimate should beat a season-long one there, which Phase B can test (B05).
7. **Raw WR numbers are mostly season-wide scoring.** Raw (unadjusted) WR repeatability is no better than what shuffling defenses within each week produces (p = 0.077). That is because whole seasons differ (WR scoring per team-game ranged 30.7–36.7). Adjusting for the offense faced, as v0 did, removes it.

## A02: split methods

Adjusted, games for half signal (95% season bootstrap):

| Group | Odd/even (v0) | Alternating games | 1st vs 2nd half | First 6 vs next 6 | Home vs away | 1,000 random splits: median (2.5–97.5%) |
| --- | --- | --- | --- | --- | --- | --- |
| QB | 22.2 (13–43) | 19.3 (13–34) | 45.2 (26–106) | 51.2 (17–569) | 33.5 (21–68) | 24.2 (16.9–37.7) |
| RB | 21.0 (12–44) | 20.3 (13–36) | 26.3 (16–54) | 24.2 (16–39) | 15.4 (10–27) | 19.3 (14.0–27.4) |
| WR | 42.4 (20–208) | 22.8 (14–54) | 38.3 (19–108) | 28.0 (17–58) | 33.5 (21–71) | 26.8 (18.7–42.2) |
| TE | 42.1 (22–167) | 39.9 (22–129) | 69.6 (28–720) | 31.7 (17–104) | 25.9 (16–62) | 36.9 (24.0–63.3) |
| K | 48.9 (22–288) | 36.0 (25–63) | 71.4 (33–471) | 54.4 (30–186) | 49.4 (26–148) | 49.6 (30.8–104.1) |
| D/ST | 8.7 (7.3–10.1) | 7.4 (5.7–9.1) | 8.5 (6.1–12.0) | 6.4 (4.6–8.6) | 6.2 (4.7–7.8) | 7.3 (6.0–9.0) |

- **The random-split range isn't a confidence interval.** It shows how much the arbitrary choice of halves moves k on the same data.
- **The minimum of 4 games per half never binds:** k is unchanged from 2 to 7 games.
- **Chronological splits** give larger k for QB, TE and K: halves far apart in time agree less (A06).
- **Home vs away** is a different question: home and away games differ in context, not only in sample.

## A03: what the cell is adjusted for

REML k (odd/even r):

| Group | None (raw) | Season-centered | Offense's other games: mean (v0) | median | mean shrunk toward the season mean |
| --- | --- | --- | --- | --- | --- |
| QB | 29.1 (0.217) | 38.3 (0.173) | 24.2 (0.271) | 24.8 (0.271) | 25.6 (0.255) |
| RB | 19.5 (0.297) | 22.9 (0.267) | 19.5 (0.281) | 19.8 (0.278) | 19.3 (0.290) |
| WR | 27.8 (0.163) | 48.6 (0.077) | 26.7 (0.163) | 27.3 (0.165) | 28.1 (0.154) |
| TE | 37.7 (0.160) | 42.9 (0.142) | 37.4 (0.164) | 34.5 (0.179) | 36.3 (0.169) |
| K | 48.0 (0.164) | 57.8 (0.143) | 50.5 (0.144) | 48.4 (0.163) | 52.3 (0.150) |
| D/ST | 7.3 (0.481) | 7.7 (0.466) | 7.2 (0.485) | 7.5 (0.484) | 7.2 (0.485) |

- **The raw measure contains whole-season scoring shifts.** Centering on the season removes them, and k rises (WR 27.8 → 48.6).
- **Adjusting for the offense faced removes offense-driven noise,** and k falls back (WR 26.7). Raw and adjusted k look alike for different reasons; only the adjusted one measures the defense.
- **Median and shrunk expectations change little.** One big game by an offense doesn't drive the adjustment.
- **The offense's own reliability (`kFaced`):** QB 6.5, RB 6.6, WR 4.2, TE 4.4, K 22, D/ST 17.4. Phase B's B00 baseline rests on this.

## A04: by era, half size and position order

| Group | 2016–2020 k (95%) | 2021–2025 k (95%) |
| --- | --- | --- |
| QB | 23.6 (11–66) | 20.5 (12–51) |
| RB | 16.5 (7–72) | 27.0 (22–31) |
| WR | 33.0 (17–68) | 54.2 (15–268) |
| TE | 32.6 (19–88) | 49.3 (16–1065) |
| K | 78.5 (20–1398) | 35.1 (15–127) |
| D/ST | 9.2 (7.8–9.7) | 8.3 (6.1–11.1) |

- **Eras:** the 16-game and 17-game eras differ within their intervals. D/ST is the only group with a tight, unchanged estimate.
- **Half size:** units with both halves of 8 or more games and those with a 7-game half give similar correlations.
- **Weight curves:** w(n) curves with intervals are in [weight-curves.svg](plots/weight-curves.svg).

## A05: variance components (model check)

- **Fit:** REML converged for all 18 fits, and none sits at the τ² = 0 boundary. In the season bootstrap, the boundary share is 0 for every adjusted fit; for season-centered raw WR it is 0.45%.
- **Agreement:** the method of moments agrees with REML within 0.3 games for every group (largest: K, 50.8 vs 50.5).
- **Season-wide variance:** the scoring level of a whole season (SD of season means) is 1.8 points for WR, 0.9 RB, 0.7 QB, 0.6 D/ST, 0.5 TE and 0.3 K. That is why raw WR looks more repeatable than it is.
- **Model check:** the odd/even r that REML's k implies, given each unit's actual half sizes, against the observed one:

  | | QB | RB | WR | TE | K | D/ST |
  | --- | --- | --- | --- | --- | --- | --- |
  | Implied | 0.253 | 0.296 | 0.235 | 0.180 | 0.140 | 0.532 |
  | Observed | 0.271 | 0.281 | 0.163 | 0.164 | 0.144 | 0.485 |

  WR's observed split is the outlier, consistent with A02.

## A06: within a season

| Group | Odd/even r minus 1st-vs-2nd-half r (95%) | Covariance ratio, 1–4 weeks apart → 9–17 weeks apart | Rolling 3-game window r: observed vs stable-trait model |
| --- | --- | --- | --- |
| QB | **+0.116 (0.019 to 0.201)** | 0.060 → 0.005–0.046 | 0.103 vs 0.066 |
| RB | +0.043 (−0.067 to 0.153) | 0.053–0.066 → 0.020–0.044 | 0.095 vs 0.081 |
| WR | −0.014 (−0.088 to 0.059) | 0.036–0.048 → 0.017–0.028 | 0.069 vs 0.060 |
| TE | +0.058 (−0.047 to 0.165) | 0.031–0.032 → 0.008–0.042 | 0.045 vs 0.044 |
| K | +0.041 (−0.066 to 0.129) | 0.024–0.032 → −0.005–0.015 | 0.046 vs 0.033 |
| D/ST | −0.008 (−0.089 to 0.082) | 0.118–0.123 → 0.102–0.111 | 0.193 vs 0.189 |

- **QB:** the tendency drifts within a season. Odd/even mixes early and late games, so it overstates how well week-1 games describe week-17 games. Recent games say more than the season average would suggest.
- **D/ST:** flat. Its tendency is a stable trait.
- **Plot:** [lag-decay.svg](plots/lag-decay.svg).

## A07: between seasons

The same franchise's adjusted mean in consecutive seasons, each with 8 or more games (288 pairs):

| Group | r (95%) | Slope (95%) | Leave-one-season-out error: decayed prior vs reset to the league |
| --- | --- | --- | --- |
| D/ST | 0.40 (0.33–0.47) | 0.40 (0.32–0.47) | 6.38 vs 7.55 (−16%) |
| QB | 0.29 (0.18–0.40) | 0.30 (0.18–0.42) | 5.21 vs 5.64 (−8%) |
| RB | 0.28 (0.19–0.36) | 0.28 (0.19–0.35) | 9.41 vs 10.16 (−7%) |
| WR | 0.23 (0.11–0.34) | 0.23 (0.11–0.38) | 15.07 vs 15.70 (−4%) |
| TE | 0.16 (0.08–0.23) | 0.16 (0.08–0.24) | 4.67 vs 4.77 (−2%) |
| K | 0.14 (0.08–0.20) | 0.15 (0.08–0.21) | 1.64 vs 1.67 (−2%) |

- **What carries over:** a unit's tendency partly survives the offseason. Last season's adjusted mean, multiplied by the slope, is a usable early-season prior for D/ST, QB and RB, and nearly worthless for TE and K.
- **No guaranteed trait:** k ≈ 40 games doesn't make a guaranteed trait of two and a half seasons. Rosters turn over, which is why the slope is well below 1.

## A08: nulls, placebos and resampling

The null: each week's cells are shuffled among the units that played that week, which keeps every unit's schedule and every week's values (1,000 shuffles). See [null-distributions.svg](plots/null-distributions.svg).

| Group | Observed r: raw / adjusted | Null 97.5th percentile: raw / adjusted | p raw / adjusted |
| --- | --- | --- | --- |
| QB | 0.217 / 0.271 | 0.128 / 0.064 | 0.001 / 0.001 |
| RB | 0.297 / 0.281 | 0.155 / 0.094 | 0.001 / 0.001 |
| WR | 0.163 / 0.163 | **0.190** / 0.082 | **0.077** / 0.001 |
| TE | 0.160 / 0.164 | 0.107 / 0.089 | 0.003 / 0.002 |
| K | 0.164 / 0.144 | 0.136 / 0.111 | 0.009 / 0.006 |
| D/ST | 0.481 / 0.485 | 0.137 / 0.084 | 0.001 / 0.001 |

- **Holm across the 12 tests:** every adjusted measure stays significant (≤ 0.018), and raw WR does not (0.077).
- **Raw nulls sit above zero** (WR mean 0.093) because shuffling within a week keeps season-wide scoring levels, a structure raw r includes.
- **Resampling:** for the adjusted odd/even k, resampling whole seasons gives wider intervals than resampling units, for WR, TE and K. For example, WR's upper bound is 208 games by season against 130 by unit. Resampling franchises falls between. The season interval is the one reported, because one game links two units and a season's units share conditions.

## A09: which part of the points repeats

Each cell's FFA points are split by the scorer's own rule contributions, which sum back to the cell exactly (maximum difference 0.000000). Components with at least 5% of the cell variance:

| Group | Component: variance share, REML k |
| --- | --- |
| QB | passing TDs 46%, k 74; passing yards 24%, k 28; rushing TDs 12%, k ≈ ∞; turnovers 9%, k 58; rushing yards 8%, at the boundary |
| RB | rushing TDs 33%, k 41; rushing yards 29%, **k 13.5**; receiving yards 15%, k 43; receptions 12%, k 32; receiving TDs 12%, k 850 |
| WR | receiving yards 41%, k 40; receiving TDs 30%, k 182; receptions 26%, k 38 |
| TE | receiving yards 37%, k 48; receiving TDs 32%, k 180; receptions 28%, k 44 |
| K | field goals 92%, k 164; extra points 5%, k 30 |
| D/ST | yards-allowed tier 23%, **k 8.0**; takeaways 22%, k 43; points-allowed tier 20%, **k 7.8**; return and defensive TDs 18%, k 107; sacks 15%, **k 10.1** |

**What repeats:**
- **Run defense:** rushing yards allowed to RBs repeat about as fast as anything at the position groups.
- **D/ST:** its signal is the offense's tendency to be held to few points and yards and to be sacked, not its turnovers.
- **Kickers:** a defense's effect on field goals is noise, while its extra-point tendency (how many touchdowns it allows) repeats a little.
- **Volume:** true counts (targets, carries) need a realized-statistics source not yet admitted to the DvP firewall. Receptions are the volume measure here.

## A10: robustness and influence

| Group | k leaving out one season (min–max) | Excluding 2020 / 2022 | Winsorized 1–99% / trimmed at 3 SD | Largest move of r from one unit-season | Without the single largest cell |
| --- | --- | --- | --- | --- | --- |
| QB | 18.7–27.7 | 20.4 / 23.4 | 22.8 / 24.2 | 0.015 | 21.9 |
| RB | 17.4–26.2 | 23.1 / 20.4 | 20.8 / 19.6 | 0.014 | 20.8 |
| WR | 33.0–62.4 | 44.5 / 40.2 | 41.5 / 33.9 | 0.016 | 42.2 |
| TE | 33.7–55.6 | 48.4 / 38.1 | 40.4 / 47.9 | 0.014 | 41.6 |
| K | 35.2–69.9 | 58.7 / 46.0 | 45.8 / 38.3 | 0.014 | 47.2 |
| D/ST | 8.4–9.2 | 8.6 / 9.1 | 8.7 / 9.1 | 0.010 | 8.7 |

(Odd/even, adjusted.)
- **No single game, unit-season or season drives any result.** Each conclusion above survives every perturbation.
- **After a bye:** a defense coming off a bye allows 1.0 fewer RB points than usual (SE 0.56). That is exploratory, not significant once the six groups are considered. Other groups show no bye effect.

## A12: completion and correction sensitivity

- **Refused lines:** v0 summed cells with a refused line (13–17 per position) as their partial sums. Excluding them, as the validated observations do, moves k by at most 2 games (WR 42.4 excluded vs 44.4 summed).
- **Stat corrections, measured where Arbit holds them:** for 158 completed 2026 games, FFA points by position as first held were compared with the latest version.
  - 2 of 1,896 cells changed: one QB by 0.04 and one TE by 0.10 points. Corrections are negligible against game noise (within unit-season SD 4.5–13.6 points).
  - **This is a lower bound.** Arbit's nflverse copies start on 2026-10-31 and miss 2026-11-10 to 11-22, so weeks 1–8 and 10 were first held long after any correction. Week 9 is the one cleanly observed week.
  - Seasons 2016–2025 hold only final revisions, so their correction history can't be replayed (a backtest limitation recorded in SCORE_FINALITY_AUDIT.json).

## A00: landscape

| Group | Mean per team-game | SD | Skew | SD of unit-season means | Within unit-season SD | Raw vs adjusted rank agreement (Spearman, mean of seasons) | Units moving 8+ places |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QB | 16.6 | 7.8 | 0.39 | 2.4 | 7.6 | 0.94 | 9 of 320 |
| RB | 23.1 | 10.2 | 0.84 | 3.3 | 9.7 | 0.93 | 17 |
| WR | 33.7 | 14.0 | 0.53 | 4.3 | 13.6 | 0.90 | 26 |
| TE | 12.4 | 8.3 | 1.02 | 2.4 | 8.0 | 0.90 | 25 |
| K | 7.8 | 4.6 | 0.52 | 1.3 | 4.5 | 0.96 | 5 |
| D/ST | 5.9 | 6.6 | 0.52 | 2.8 | 6.1 | 0.98 | 0 |

- **Signs and zeros:** negative cells are kept (D/ST 820, K 50, QB 27), and so are true zeros (K 162, TE 109).
- **Noise dominates:** within a unit-season, the game-to-game spread is 2.2 (D/ST) to 3.4 (K) times the spread between unit-seasons.
- **Ranks:** adjusting for opponents reorders WR and TE defenses the most.

## Plots

- [k by method with intervals](plots/k-forest.svg)
- [weight curves](plots/weight-curves.svg)
- [lag decay](plots/lag-decay.svg)
- [permutation nulls](plots/null-distributions.svg)
- [between-season carryover](plots/carryover.svg)
- Split scatters: [QB](plots/split-scatter-QB.svg), [RB](plots/split-scatter-RB.svg), [WR](plots/split-scatter-WR.svg), [TE](plots/split-scatter-TE.svg), [K](plots/split-scatter-K.svg), [D/ST](plots/split-scatter-DST.svg)

## What Phase B takes from this (no decision is made here)

- **The comparator:** B00 predicts each offense's position total from its own completed games. The offense's k of 4–7 says that is where most of the signal is.
- **Variants to test,** each against B00 on identical games:
  - **D/ST:** an offense-allowed term with k ≈ 7–9.
  - **QB:** a recency-weighted defense term (B05), because the QB tendency drifts.
  - **RB:** a term on rushing yards allowed (B07).
  - **WR, TE and K:** heavily shrunk terms (k ≈ 27–50), or none.
  - **Priors:** last season's adjusted mean × the A07 slope.
- **Not to carry forward as fact:** v0's position order (TE < WR < K), WR's k of 44, and any w(n) as a share of the Sit/Start model. w(n) is credibility inside a DvP estimate.
- **Exploratory, not confirmatory:** every result here is descriptive over 2016–2025, including 2025. Phase B tunes on 2016–2023 and validates on 2024; 2025 stays a conditional holdout (§12).

**Status per spec gate:**
- The interpretation is reproducible.
- All conclusions come from actual FFA outcomes.
- No vendor-projection lineage.
- No predictive claim is made.
