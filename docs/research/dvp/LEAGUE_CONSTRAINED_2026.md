# M3-3 DvP league-constrained D/ST decisions in FFA (C05L)

Owner audit Phase B (B6). TASK-20261124-009. Receipt: [league-2026-exploratory.json](league-2026-exploratory.json), written by `scripts/model/dvp_league_2026.py` at commit `3848cad`. Rule: [`config/dvp/league-2026-exploratory.json`](../../../config/dvp/league-2026-exploratory.json), committed and pushed in `07505d9` before any result. Data: [FFA 2026 data inventory](../FFA_2026_DATA_INVENTORY.md).

## The original requirement, split

The specification's C05 asked for lineup evaluation under the league's roster rules "where trustworthy history exists". It had been recorded as BLOCKED because no FFA lineups exist before 2026. The owner's Phase B clarification (OWN-076: 2026 is FFA's inaugural season) splits it into three parts:

| Requirement | Disposition | Why |
| --- | --- | --- |
| **C05L-HIST:** league-constrained evaluation on 2016–2025 | **NOT_APPLICABLE** | FFA didn't exist then. The unrestricted D/ST pairwise evaluation ([PLAYER_LEVEL_REPORT.md](PLAYER_LEVEL_REPORT.md)) remains the legitimate method for those seasons |
| **C05L-2026-EXP:** completed 2026 weeks 1–11 | **DONE, EXPLORATORY** (below) | The weeks were known before the prospective freeze, and the forecasts are reconstructed now: never a confirmation |
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

## C05L-2026-PRO: what is captured for weeks 12–18

- **When:** each prospective archive (`artifacts/dvp/prospective/2026/week-WW/league.json`, exported to [prospective/2026](prospective/2026/README.md)) records the league's state at the forecast moment, before kickoff.
- **What it records:**
  - every team's rostered D/STs;
  - the D/STs on no roster;
  - from week 13, each unrostered D/ST's availability state (free agent, waivers, or possibly waivers), from the stored drops and the waiver hold.
- **Week 12:** the archive was made before this capture existed, so week 12's availability is reconstructed the same way from the transaction log. No week-12 drop of a D/ST fell within 48 hours of the capture.
- **Evaluation** follows `config/dvp/prospective.json` (`leagueEvaluation`: start and stream, descriptive), with a free-agents-only streaming variant reported separately. It stays descriptive and never alters the frozen Phase B or Phase C confirmation rules.
