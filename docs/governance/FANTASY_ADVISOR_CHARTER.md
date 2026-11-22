# Future Arbit advisor: Football Operations charter

**Status: product requirement / proposed operating role — NOT an implemented model or advisor.**
This charter is for the eventual *fantasy football decision-making agent*, not
for Codex/Claude's engineering authority. It cannot override the approved
statistical model's data policy.

| Functional role | Specific fantasy responsibility | Required evidence before advice |
| --- | --- | --- |
| General Manager | Long-horizon roster construction, trades, acquisition priority and championship objectives | True roster, league rules, standings, schedule, effective transaction state |
| Director of Pro Personnel | Waivers, free agents, changing opportunity and replacement alternatives | Eligible pool, availability, roster implications, source freshness |
| Head Coach | Starting lineup and weekly matchup optimization | Official slot/lock rules, injuries, upcoming matchups, modeled distributions |
| Director of Analytics | Distributions, baseline comparison, uncertainty and counterfactuals | Point-in-time nflverse model version, exact FFA scoring, coverage/holdout evidence |
| Director of Scouting | Player roles, schemes, usage and contextual research | Verifiable observations and dated NFL information, distinct from canonical model features |
| Director of Strategy & Administration | FAAB/waiver priority, roster scarcity, future option value | Actual league transaction constraints and feasible alternatives |

The GM issues one unified recommendation only after a constraint/validation pass.
For each decision: action, essential evidence, other feasible options, uncertainty,
roster impact, deadlines and safe execution steps. Never assume automatic waiver,
trade or lineup writes; initial ESPN operations are read-only. The assistant must
not simulate an approval, invent trade acceptance probability, or promote observed
postgame information into a pregame feature.

**Important separation:** Arbit's *statistical Model* uses **only nflverse** as
accepted in [ADR-006](../architecture/decisions/006-model-architecture.md).
External current/public football reporting may be consulted by a future advisory
workflow **only when separately scoped, sourced, allowed and labeled**; such
information is not thereby authorized as Model input, training target, benchmark,
or scored fantasy stat. ESPN FFA league facts are authoritative for user/team
context. [ADR-007](../architecture/decisions/007-model-availability.md) is accepted with
owner amendments (OWN-066). The first advisor is the Head Coach's sit/start
(OWN-068). It must explain each projection through measured contributions: role and
efficiency, opponent defense against the position, team environment, availability and
FFA scoring. Weather for the upcoming game is open (Q-016), and is advisor-layer context
at most until decided. Recommendation features remain gated until implemented and validated.
