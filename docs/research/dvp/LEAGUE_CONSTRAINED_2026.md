# M3-3 DvP league-constrained D/ST decisions in FFA (C05L)

Owner audit Phase B (B6). TASK-20261124-009. Receipt: [league-2026-exploratory.json](league-2026-exploratory.json), written by `scripts/model/dvp_league_2026.py` at commit `3848cad`. Rule: [`config/dvp/league-2026-exploratory.json`](../../../config/dvp/league-2026-exploratory.json), committed and pushed in `07505d9` before any result. Data: [FFA 2026 data inventory](../FFA_2026_DATA_INVENTORY.md).

## The original requirement, split

The specification's C05 asked for lineup evaluation under the league's roster rules "where trustworthy history exists". It had been recorded as BLOCKED because no FFA lineups exist before 2026. The owner's Phase B clarification (OWN-076: 2026 is FFA's inaugural season) splits it into three parts:

| Requirement | Disposition | Why |
| --- | --- | --- |
| **C05L-HIST:** league-constrained evaluation on 2016–2025 | **NOT_APPLICABLE** | FFA didn't exist then. The unrestricted D/ST pairwise evaluation ([PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md)) remains the legitimate method for those seasons |
| **C05L-2026-EXP:** completed 2026 weeks 1–11 | **DONE, EXPLORATORY; corrected in v2** ([below](#corrected-evaluation-v2-final-directive-2026-11-25)) | The weeks were known before the prospective freeze, and the forecasts are reconstructed now: never a confirmation |
| **C05L-2026-PRO:** weeks 12–18, prospective | **PENDING_FUTURE_DATA** | Rosters and availability are captured at each forecast's moment. Results only after the games, as a separately declared, descriptive evaluation |

## C05L-2026-EXP: method

- **Forecasts:** the frozen B00 and B06, through the prospective adapter.
  - Parameters are fit on 2016–2025.
  - Each week is forecast from the actuals available by its preweek cutoff.
  - 2026 data are the observations archived with the week-12 prospective forecast (hash-checked).
  - The forecasts are RETROSPECTIVE: made now with the frozen method.
- **Decision time:** the week's preweek cutoff, its first kickoff.
- **Who held what:** the draft and every executed move, replayed to the cutoff (`arbit_model.ffa_history`). The replay reproduces every captured period roster and every daily snapshot (inventory). Current ownership is never used.
- **What was claimable:** a D/ST on no roster and not dropped within 48 hours, so off waivers. Units dropped within 24 hours (waivers), or 24–48 hours (possibly still on waivers), are excluded from free-agent streaming. They are counted, and allowed only in a separate upper-bound variant.
- **Decisions:**
  - **Start:** a team holding two or more D/STs with a game. Each model starts its higher forecast.
  - **Stream:** each team chooses among its own playing D/STs and the claimable free agents.
- **Labels:** Arbit's canonical FFA D/ST actuals. ESPN's official D/ST points in the captured lineups equal them for all 116 labelled units; the other 9 were on bye.

## C05L-2026-EXP: results (weeks 1–11)

| Decision | Decisions | B06 picks differently | Points from those changes, B06 − B00 (95%, week blocks) | B06 right when it differs | Hit rate (best option), B00 / B06 | Mean regret (points), B00 / B06 |
| --- | --- | --- | --- | --- | --- | --- |
| Start (held D/STs) | 28 | 12 (43%) | **−6** (−90 to +80) | 50% | 57% / 57% | 3.50 / 3.71 |
| Stream (held + claimable free agents, about 19.5 options) | 88 | 77 (88%) | **+46** (−280 to +360) | 51% | 1.1% / 2.3% | 12.2 / 11.7 |
| Stream including waiver-wire units (upper bound) | 88 | 78 | +96 (−214 to +386) | 61% | 1.1% / 2.3% | 12.0 / 10.9 |

- **Coverage:** 88 team-weeks (8 teams × 11 weeks).
  - 28 had a start decision: 2 or more held D/STs playing. Several teams carried a second D/ST.
  - All 88 had a stream decision, with about 19.5 options.

**Managers' own starts** in the same 28 start decisions:
- they scored 201 points, against 197 for B00's picks and 191 for B06's;
- they picked the best held D/ST 61% of the time;
- they agreed with B06 64% of the time and with B00 50%.

**Matchup implications** (start decisions, ESPN official totals, opponent unchanged):
- Starting B06's pick instead of the D/ST actually started would have turned 2 actual losses into wins (week 4 by 0.04 points, week 11), and 1 actual win into a loss (week 1).
- B00's pick would have changed only that week-1 result, also to a loss. In week 1 both models start the same D/ST over the manager's choice.
- Where the two models' picks give different results (2 matchups), B06's wins both.

**What this shows:**
- **Too few decisions to measure.** Eleven weeks give 28 start decisions and 88 streaming decisions. Every interval spans zero by a wide margin.
- **Consistent with the pair-level result,** but it doesn't confirm it. Phase C's pairwise accuracy gain (+4 to +8 points) means roughly one better choice in 12 to 23. Over 12 changed start choices, that is not separable from noise.
- **Streaming** is where the models disagree most (88% of decisions). There B06 leans ahead on points (+46, +96 with waiver-wire units), but its interval spans zero.
- **Hit rates** for streaming are low for both models, because picking the single best of about 20 D/STs is hard.
- **Managers' start choices** were about as good as either model's in these weeks. Their picks agree more often with B06.
- **No rule is attached, and nothing changes the frozen Phase B or Phase C rules** (config `decisionRule: none`).

## Corrected evaluation (v2, final directive, 2026-11-25)

The owner's final directive (PB-AUD-02 to -06 and -08) found defects and gaps in v1.
- **Run:** v2 corrects them under its own rule, [`config/dvp/league-2026-exploratory-v2.json`](../../../config/dvp/league-2026-exploratory-v2.json), committed and pushed in `671b5ef` before it was computed. The receipt is [league-2026-exploratory-v2.json](league-2026-exploratory-v2.json), from commit `39f763e`.
- **v1 is preserved unchanged** above, with its receipt.
- **v2 reads only the pinned league inputs:** [manifest](../ffa-2026-league-inputs-v1.json) `c354dcca…`, all 9 files hash-checked. It never reads the live database.

**What changed:**

| Finding | v1 | v2 |
| --- | --- | --- |
| PB-AUD-08 inputs | Read from the live database at run time | A pinned, hash-checked bundle; the same inputs give the same result |
| PB-AUD-02 ownership | Executed trades would be ignored; a waiver without a processing time would fall back to its proposal time | Both stop the run, and the draft is validated. The replay equals **all 1,522 snapshots** at each one's own time, and all 11 period rosters |
| PB-AUD-03 availability | A 24/48-hour drop rule, unvalidated | Rule v2: processing at midnight Pacific on the league's days; drop holds; game locks. Validated against every snapshot (below). Week 9 is VERIFIED from a snapshot 34 minutes before its cutoff |
| PB-AUD-04 uncertainty | Bootstrap blocks only where decisions changed (9 of 11 start/sit weeks) | Every evaluated week is a block (11), and zero-change weeks add zero |
| PB-AUD-05 streaming | Independent managers, unqualified | Still independent single-week recommendations, now with feasibility classes and collisions |
| PB-AUD-06 managers and matchups | Option counts only | Exact option sets with availability evidence; the actual starter and whether it was an option; matchup counterfactuals only for eligible picks, with ties and unknowns counted |

**Validating the availability rule** (ESPN's reported state of every unowned D/ST in every snapshot, at the snapshot's time):

| Rule | Snapshots | Unit-moments | Agreement | Falsely claimable | Over-restrictive |
| --- | --- | --- | --- | --- | --- |
| v2, design (to 2026-11-10) | 1,106 | 22,425 | 98.9% | 36 (0.16%) | 208 |
| v2, **holdout** (from 2026-11-22) | 416 | 7,904 | **99.3%** | 54 (0.68%) | 0 |
| v2, decision-like moments (after Wednesday's run, before the next kickoff) | — | 1,144 | 94.9% | 0 | 58 |
| v1, design | 1,106 | 22,425 | 29.5% | 15,613 | 208 |
| v1, holdout | 416 | 7,904 | 22.0% | 6,168 | 0 |

- **Acceptance:** rule v2 passes its declared test (holdout agreement at least 99%, falsely claimable at most 1%), so cutoff states it gives are RECONSTRUCTED.
- **Why v1 fails:** v1 agrees only 22–29% overall because it ignores game locks.
- **Where v2 errs:**
  - **All 208 over-restrictive cases:** players dropped inside a waiver run. ESPN frees those at once, while v2 holds them 24 hours.
  - **All 90 falsely claimable cases fall on Tuesdays,** when ESPN puts every unowned unit on waivers, bye teams included. v2 locks only units whose game started.
- **A refined rule v3** would cover both. It is recorded as a proposal to validate on future snapshots, not adopted after seeing these errors.
- **Effect on these results:** three cutoff states would change under it (week 2 LA, week 6 JAX, week 10 CIN). Neither model picks any of them even when they are offered, so the results are the same.

**Results, v1 and v2:**

| Decision | Decisions v1 / v2 | Changed | B06 − B00 points v1 | v2 | 95% interval v1 | v2 (11 week blocks) |
| --- | --- | --- | --- | --- | --- | --- |
| Start (held D/STs) | 28 / 28 | 12 | −6 | **−6** | −90 to +80 (9 blocks) | **−96 to +74** |
| Stream, claimable at the cutoff | 88 / 88 | 77 | +46 | **+110** | −280 to +360 | **−202 to +398** |
| Stream with waiver units (upper bound) | 88 / 88 | 78 | +96 | **+96** | −214 to +386 | **−214 to +386** |
| Stream from every unowned unit | — / 88 | 78 | — | +96 | — | −214 to +386 |

- **Samples:** no decision was added or removed. The start/sit picks are identical.
- **The +46 → +110 change is all week 9,** in 8 claimable decisions:
  - **What changed:** the snapshot 34 minutes before the cutoff shows HOU and NYJ as free agents; v1's 48-hour rule had excluded them.
  - **Effect:** B06 then picks HOU for all 8 teams, and week 9 moves from −50 to +14.
  - **The catch:** only one team could have claimed HOU.
- **Start/sit interval:** −96 to +74, as the reviewer computed (−96.03 to +74.02). Weeks 7 and 8 had no changed decision and are now blocks of zero.
- **Week 11:** it contributes +92 to streaming in both versions. Without it, v1's +46 becomes −46 and v2's +110 becomes +18. As the directive requires, it stays in the primary result.

**Feasibility and collisions** (streaming, claimable pool):
- **Feasibility:** of B06's 88 picks, 20 are units the team holds, 11 are executable at once (an open slot), and **57 need a drop**. No team was ever at the 3-D/ST limit. At the preweek cutoff no player is game-locked, so a legal drop exists; its cost is not modelled. B00's picks: 31 held, 10 executable, 47 need a drop.
- **Collisions:** all 68 of B06's picks of unowned units fall in collisions, each recommended to several teams in the same week (11 units). Of B00's 57, 56 do. Each model's forecast is the same for every team, so it points every manager at the same free agent.
- **What the gross points mean:** they assume every manager gets that unit, which is impossible. They are a single-manager, single-week measure, not a league-wide strategy or net roster value.

**Managers:**
- All 28 start decisions are strictly comparable: each manager's finalized starter was among the D/STs held at the cutoff. None needed setting aside for a different decision time.
- Managers scored 201 points against B00's 197 and B06's 191. They agreed with B06 64% of the time and with B00 50%.

**Matchups** (individual-decision counterfactual, opponent's total fixed):
- All 28 picks were eligible, with no unknown points and no ties.
- B06's pick would have turned 2 actual losses into wins and 1 win into a loss. B00's would have turned the same win into a loss.
- Where the two models' results differ, B06's is better in both cases.
- This is not a change in win probability.

**Conclusion:** unchanged from v1. FFA-specific roster-constrained utility is inconclusive: start/sit −6 with an interval spanning zero. Streaming utility is inconclusive:
- every streaming interval spans zero widely;
- the claimable estimate rests on one week's collision-heavy picks;
- streaming recommendations are not jointly executable.

B06 remains the promising historical candidate (DEC-07). Nothing here promotes or rejects it.

## C05L-2026-PRO: what is captured for weeks 12–18

- **When:** each prospective archive (`artifacts/dvp/prospective/2026/week-WW/league.json`, exported to [prospective/2026](prospective/2026/README.md)) records the league's state at the forecast moment, before kickoff.
- **What it records** (amendment 1, [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md)), from week 13:
  - every team, including any with no D/ST;
  - ESPN's own reported state of all 32 D/STs in the same snapshot: OWNED, FREE_AGENT, WAIVERS or UNKNOWN;
  - decision-time captures until the cutoff.
- **Week 12:** has a supplement from its original snapshot. All 19 unowned units were on waivers at forecast time, because of game locks until Wednesday's processing.
- **Evaluation** follows `config/dvp/prospective.json` and amendment 1. The kinds are rosterOnly, unownedPool, claimablePool and claimableWithWaivers, with teams without a decision listed. It stays descriptive and never alters the frozen Phase B or Phase C confirmation rules.
