# Arbit Product Specification

Version 0.1 · 2026-10-30 · Status: proposed foundation derived from owner brief v1.0.

## Intent and constraints

Arbit turns football data into explained fantasy decisions for FFA members. It serves one existing ESPN redraft league: **1729878439**, season **2026**. The owner confirms a portable, local-first deployment proposal. The brief describes this as FFA's inaugural season; confirm available history from ESPN rather than inventing previous seasons. A new redraft starts each year; season-scoped identities preserve team-name and manager changes.

Arbit is the product name; FFA is league context; **Front Office** is the personalized headquarters. ESPN controls league facts. nflverse is the primary statistical foundation. Sleeper is limited to verified NFL live-game and play-by-play data (OWN-011) and is never a league provider. Gridiron field and uniform assets remain an intended Live dependency. The full product comprises Front Office, Draft, Scout, Market, Lineup, Live, Model, and Archive.

The initial assignment delivers specifications, research, governance, roadmap, and scaffold. Later milestones deliver the product. Milestone slices are sequencing decisions, not replacements for the comprehensive final scope.

## Users and access

- **Member:** invited FFA manager, linked by an administrator to an ESPN manager/team; sees own decision workspace and the league rosters needed for legitimate matchup and trade analysis.
- **Co-manager:** explicitly assigned shared control of a team if ESPN data and league membership confirm it; never inferred from an email or display name.
- **Administrator:** manages invitations, identity bindings, source credentials, refresh health, asset curation, and historical corrections. Administrative changes are audited.

The application advises. The initial product does not submit ESPN lineups, waiver claims, trades, or draft picks. Each recommendation leads to a clear ESPN action link or manual workflow. Future transaction execution is a separate product and authorization decision. Saving Arbit preferences, watchlists, scenarios, and comparisons is in scope.

## Shared product requirements

Every recommendation consumes the same canonical player identities, FFA scoring/eligibility rules, league snapshot, and versioned player evaluations. It states the action, alternatives, expected benefit with horizon, evidence, assumptions, uncertainty, data freshness, and reasons it might fail. Unknown measurements are not zero. Missing or unsupported league rules block affected advice rather than silently reverting to a default scoring system.

Users can select season/week where meaningful; fantasy matchup periods and NFL weeks remain distinct. Current ownership and lineup locks are checked when displaying actions. Stale recommendations remain visibly historical and lose any suggestion that they reflect current availability. Status must distinguish live/provisional provider facts, finalized ESPN league totals, and Arbit estimates.

## Module boundaries and acceptance

Detailed workflows, screen content, interactions, and failure states are in [Feature experiences](feature-experiences.md). Testable obligations have stable IDs in [Requirements](requirements.md).

| Module | Required depth | Acceptance evidence |
| --- | --- | --- |
| Front Office | Manager/team, roster, matchup, standings, positional needs, trends, lineup issues, prioritized decisions linking to all modules | Two member fixtures yield their own team and actionable shared-model advice; degraded sources are visible; no feature duplicates scoring |
| Draft | Preparation, strategy, scenario simulation, live state, dynamic selections, roster construction, scoring, scarcity, byes, round/pick availability, option comparison | Replay a complete configured FFA draft; recommendations respond to all teams' picks and roster needs; no picked player recommended; simulated probabilities identify assumptions |
| Scout | Search, rich profiles, history, current and game-level metrics, advanced role/utilization, trends, news, depth, schedule, FFA points, comparisons, outlooks, rankings, archetypes | Trace metrics to data/time/source and calculation; multi-player comparison uses consistent filters; missing metrics and small samples explicit |
| Lineup | Full-roster optimization, individual sit/start, own fantasy opponent, NFL matchup/defense and usage analysis, scoring, projections, confidence | Optimal legal assignment against exhaustive small fixtures; locked players fixed; choices explained; incomplete injury/rules inputs prevent overconfident advice |
| Market: waivers | FFA availability, waiver/free-agent state, trend/opportunity evaluation, schedule, roster fit, position filters, add/drop improvement | Ownership change invalidates pickup; every package legal under roster/waiver rules; gain compared to actual team and replacement; unknown bid/waiver state shown |
| Market: trades | Whole-league needs/depth/byes, valuations, multi-player packages, both managers' benefit, feasibility, comparisons, evaluation of custom proposals | Both rosters legal after trade and drops; package values tied to shared model and horizon; feasibility assumptions exposed; no fabricated acceptance probability |
| Live | Scores, game state, stats, play-by-play, player participation, fantasy events and matchup context, roster filters, field/play visualizations, weekly fields/uniforms | Replay pass/run/sneak/sack/interception/FG/PAT plus correction and unknown type; fantasy attribution and score revisions correct; re-created motion labeled; reduced motion works |
| Model | Shared features, historical analysis, projections/distributions, rankings, comparisons, archetypes, matchup/roster value and decision support, evaluated ML | Point-in-time reproducible run; rolling temporal holdout and baseline comparison; all advisors share scoring and evaluation versions; no future-data leakage |
| Archive | Season standings/results/champions, Geller Cup, records, team/player history and comparisons | Inaugural season has honest empty history; final results frozen with auditable corrections; champion derived from verified playoff outcome |

## Primary user journeys

1. Invited manager signs in, confirms assigned team, and opens Front Office. They see a prioritized issue, inspect supporting Scout evidence, compare alternatives, and continue to ESPN if they choose an action.
2. Before kickoff, manager opens Lineup, checks lock state and injury freshness, compares a flexible slot, changes the optimization objective, and reviews the projected lineup and tradeoffs.
3. During waiver week, manager filters Market by position and time horizon, evaluates an add/drop pair and waiver constraints, then watches availability refresh without losing the comparison.
4. Before and during the draft, manager explores strategy scenarios, sets a watchlist, follows authoritative or clearly labeled manual draft state, and gets updated choices before each pick.
5. During games, manager follows roster-related plays, opens a play re-creation, sees provisional FFA scoring context, and observes corrections without duplicated fantasy points.
6. After the season, manager browses verified standings, records, and Geller Cup history; historical figures disclose the original season scoring rules.

## Cross-cutting experience and quality

- Desktop web first, with installable PWA and usable small-screen flows. Keyboard and screen-reader access, WCAG 2.2 AA target, chart tables, visible focus, non-color signals, reduced motion.
- Explicit loading, empty, no-league-binding, partial, stale, offline, unsupported-rule, and provider-error states. No fabricated players, values, news, or league history to fill screens.
- Long-lived sessions remain revocable. ESPN access is server-only and separate from member sign-in. Private data is not cached into a shared device's service-worker storage.
- Initial performance targets: LCP ≤2.5 seconds and INP ≤200 ms at the 75th percentile on agreed supported devices; cached read API p95 ≤500 ms under 25 concurrent sessions. These are proposed budgets to measure, not achieved claims.
- Freshness and recovery objectives are in the data and system specifications. Freshness depends on provider publication as well as polling frequency.
- Analytical releases require explicit baseline and calibration evidence; no assertion that complex models automatically improve decisions.

## Completion and scope control

A requirement is done only with implementation, relevant automated evidence, usable failure states, documentation, and a handoff. Mockups and synthetic data must be labeled and do not satisfy provider or model integration acceptance. Multi-league tenancy, dynasty/keeper support, payment systems, betting, automatic ESPN transactions, and an LLM vendor dependency are excluded from the initial scope. Full advanced analysis, play animation, and draft simulation stay on the roadmap even if earlier milestones ship sooner.

The [original brief](vision-source.txt) controls intent; unexplained omissions are defects. Decisions that change product scope are recorded and taken to the owner before implementation.
