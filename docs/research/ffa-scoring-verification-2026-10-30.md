# Actual FFA scoring mapping and verification

All **46 configured scoring definitions** are mapped. The final live audit covered completed scoring periods **1–7**: **797 played player-games**, **121 separately classified official-zero entries**, and **56/56 starting-lineup totals**. There were **zero mismatches and zero errors**. [Machine-readable support, coverage and source receipts](ffa-scoring-audit-2026-10-30.json).

The run used nine cookie-free public GETs: initial settings/status, seven explicitly scoped archived boxscores/rosters, and a final settings/status check. The final report records its UTC observation window and code commit. All nine privately retained parsed-input archives reproduce the exact support report, totals and nonzero-category coverage; their manifest hash is included. These parsed Decimal-string archives are not represented as original HTTP bytes; each separately preserves the authentic source-body hash and receipt.

## Source corrections

The pinned reference repository's football stat table is incorrect: 24 is rushing yards, 42 receiving yards and 53 receptions. Category 85 is missed field goals, not missed PATs. `appliedStats` contains fantasy point contributions; arithmetic uses the separate raw `stats` map. The source's override key 16 selects the D/ST scoring role; it is not a points-allowed range or the player's current lineup slot.

Factual category identities were checked against the maintained wrapper's own [football constants at commit 700e15dd](https://github.com/cwendt94/espn-api/blob/700e15ddbb91124f031473d2411c8a6285944274/espn_api/football/constant.py), file blob `81834cda9e5dac613ebcfac9ad29a1619ba46c28`, then cross-checked against actual ESPN stat/contribution pairs. Arbit uses its own implementation. Rates are always fetched from FFA; no default PPR, kicking or defense values are inferred.

## Configured definitions

A band is lower-inclusive and upper-exclusive. Blank upper bound means no upper limit; the under-100-yard band has no lower bound, so negative net yardage remains in it. D/ST uses raw points allowed 120 and yards allowed 127; the configured source indicator flags must agree. D/ST-adjusted field 187 is not substituted. Other statistical adapters must reproduce these definitions before using the scorer.

| ESPN ID | Canonical metric | Band | Base points | D/ST points |
| --- | --- | --- | --- | --- |
| 3 | `passing.yards` | count × rate | 0.04 | 0.04 |
| 4 | `passing.touchdowns` | count × rate | 4.0 | 4.0 |
| 19 | `passing.two_point_conversions` | count × rate | 2.0 | 2.0 |
| 20 | `passing.interceptions` | count × rate | -2.0 | -2.0 |
| 24 | `rushing.yards` | count × rate | 0.1 | 0.1 |
| 25 | `rushing.touchdowns` | count × rate | 6.0 | 6.0 |
| 26 | `rushing.two_point_conversions` | count × rate | 2.0 | 2.0 |
| 42 | `receiving.yards` | count × rate | 0.1 | 0.1 |
| 43 | `receiving.touchdowns` | count × rate | 6.0 | 6.0 |
| 44 | `receiving.two_point_conversions` | count × rate | 2.0 | 2.0 |
| 53 | `receiving.receptions` | count × rate | 1.0 | 1.0 |
| 63 | `misc.fumble_recovery_touchdowns` | count × rate | 6.0 | 6.0 |
| 72 | `misc.fumbles_lost` | count × rate | -2.0 | -2.0 |
| 77 | `kicking.field_goals_40_49` | count × rate | 4.0 | 4.0 |
| 80 | `kicking.field_goals_0_39` | count × rate | 3.0 | 3.0 |
| 85 | `kicking.field_goals_missed` | count × rate | -1.0 | -1.0 |
| 86 | `kicking.extra_points_made` | count × rate | 1.0 | 1.0 |
| 89 | `defense.points_allowed` | 0 to < 1 | 0.0 | 5.0 |
| 90 | `defense.points_allowed` | 1 to < 7 | 0.0 | 4.0 |
| 91 | `defense.points_allowed` | 7 to < 14 | 0.0 | 3.0 |
| 92 | `defense.points_allowed` | 14 to < 18 | 0.0 | 1.0 |
| 93 | `returns.blocked_kick_touchdowns` | count × rate | 6.0 | 6.0 |
| 95 | `defense.interceptions` | count × rate | 0.0 | 2.0 |
| 96 | `defense.fumbles_recovered` | count × rate | 0.0 | 2.0 |
| 97 | `defense.blocked_kicks` | count × rate | 0.0 | 2.0 |
| 98 | `defense.safeties` | count × rate | 0.0 | 2.0 |
| 99 | `defense.sacks` | count × rate | 0.0 | 1.0 |
| 101 | `returns.kickoff_touchdowns` | count × rate | 6.0 | 6.0 |
| 102 | `returns.punt_touchdowns` | count × rate | 6.0 | 6.0 |
| 103 | `returns.interception_touchdowns` | count × rate | 6.0 | 6.0 |
| 104 | `returns.fumble_touchdowns` | count × rate | 6.0 | 6.0 |
| 123 | `defense.points_allowed` | 28 to < 35 | 0.0 | -1.0 |
| 124 | `defense.points_allowed` | 35 to < 46 | 0.0 | -3.0 |
| 125 | `defense.points_allowed` | 46 to no upper bound | 0.0 | -5.0 |
| 128 | `defense.yards_allowed` | no lower bound to < 100 | 0.0 | 5.0 |
| 129 | `defense.yards_allowed` | 100 to < 200 | 0.0 | 3.0 |
| 130 | `defense.yards_allowed` | 200 to < 300 | 0.0 | 2.0 |
| 132 | `defense.yards_allowed` | 350 to < 400 | 0.0 | -1.0 |
| 133 | `defense.yards_allowed` | 400 to < 450 | 0.0 | -3.0 |
| 134 | `defense.yards_allowed` | 450 to < 500 | 0.0 | -5.0 |
| 135 | `defense.yards_allowed` | 500 to < 550 | 0.0 | -6.0 |
| 136 | `defense.yards_allowed` | 550 to no upper bound | 0.0 | -7.0 |
| 198 | `kicking.field_goals_50_59` | count × rate | 5.0 | 5.0 |
| 201 | `kicking.field_goals_60_plus` | count × rate | 6.0 | 6.0 |
| 206 | `returns.two_point_returns` | count × rate | 2.0 | 2.0 |
| 209 | `misc.one_point_safeties` | count × rate | 1.0 | 1.0 |

The compiler produces 26 effective athlete rules and 46 effective D/ST rules. Defense overrides apply on the bench as well as in a starting slot. Separate 50–59 and 60+ field-goal categories prevent counting a 60-yard kick twice. Unknown categories/options, reverse items, unknown override roles, missing controls and unsupported precision fail the support gate.

## Completeness and comparison policy

Only actual (`statSourceId=0`) weekly/game (`statSplitTypeId=1`) blocks with the exact season/period and a single played game (`210=1`) are recomputed. Duplicate blocks, projections, aggregates, missing maps or missing D/ST range totals cannot become actual scores. Known additive counters omitted within a complete played-game map use the explicitly versioned zero-suppression policy; a missing raw counter with nonzero applied points fails. Empty no-game data with an explicit official zero remains a provider-zero entry, not a verified played-stat case.

The shared Decimal scorer computes contributions from raw values, then compares contributions, the scoped actual total, the archived player-pool reference, and the sum of official applied contributions. Unexpected contributions for zero-rate categories are checked even if opposing values cancel. Starting totals exclude bench 20 and IR 21; unknown slots, overfilled starting slots, duplicate players/teams, missing coverage and settings drift fail the audit.

Comparison/display precision is explicitly **0.01, half-up**. This removes provider binary-serialization artifacts while preserving real cent differences. The current FFA rules produce exact cent values for observed stats; unobserved ESPN rounding ties are not claimed as a provider guarantee.

Thirty-five categories had nonzero actual contributions in these rostered game samples. Eleven did not: **63, 89, 93, 98, 101, 125, 128, 135, 136, 206, 209**. Their mappings and mathematical behavior have synthetic hand-calculated/boundary tests; nonzero live empirical validation remains unobserved. The report keeps this distinction explicit. Newly observed examples should extend the anonymized fixtures.

## Operator command and remaining gates

```sh
uv run arbit-worker espn-score-audit
uv run arbit-worker espn-score-audit --periods 1 2 3 4 5 6 7
```

Default periods come from observed first through latest-minus-one, bounded to 17. Current/future periods and multiweek matchup mappings are rejected by this verifier. It prints safe counts, discrepancies and source hashes, with nonzero exit on failure; it does not print player/member names or source bodies. It needs no database or ESPN credentials.

**Recommendations remain disabled.** This completes actual-rule mapping and observed completed-week scoring verification. Persisted canonical identities/rules/snapshots, source scheduling/correction workflows, validated statistical models, membership/authentication and feature UI remain separate requirements. A matching score audit does not certify all future data, final season results, eligibility/lock optimization or model quality.
