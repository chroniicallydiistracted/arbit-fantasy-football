# ADR-006: The Model is built only from nflverse and projects whole FFA stat lines, team first

Status: Accepted · 2026-11-09 · Accepted by the owner on 2026-11-09 (OWN-062). Owner direction OWN-061; research in [FFA projections from nflverse alone](../../research/ffa-projection-methods-2026-11-09.md).

## Context

The owner directed (OWN-061) that the Model use only nflverse data and every relevant field in it. It must never use another provider's fantasy or projection data, must be weighed against FFA's own scoring, and must look beyond a player's own statistics. [ADR-003](003-shared-intelligence.md) already requires one exact scorer, point-in-time features and evaluated baselines before ML. The [model specification](../model-specification.md) proposes volume × efficiency, shrinkage and simulated stat lines.

The research measured, on 2016–2025 nflverse data scored by FFA's rules:

- Opportunity (snap, target and carry shares) carries half its signal within one or two games. Efficiency needs dozens: yards per carry 34 games, receiving TDs per target 56–85, field goal accuracy 164.
- Touchdowns are 30–45% of weekly FFA variance at skill positions, yet a player's own TD rate is among the least reliable statistics measured.
- D/ST and kicker points are dominated by team and opponent environment, and the D/ST yards and points bands are nonlinear.
- A public-data study found that predicting *whether a player plays* explains much of a projection's edge.

## Decision

1. **Inputs.** Only nflverse repositories. A versioned field catalog gives every imported field one use:
   - pre-game input;
   - history (usable once published);
   - earlier seasons only;
   - outcome only;
   - identity;
   - excluded, with a reason.

   A field that appears upstream without an entry fails validation until it is classified. Excluded everywhere: other providers' fantasy points, rankings, values and projections, and nflverse's generic `fantasy_points` columns. Betting lines wait for the owner (Q-014).
2. **Target.** The FFA stat line per player-game and D/ST team-game from `arbit_data.nflverse.stat_lines`, scored only by `arbit_core.scoring.score` under the pinned rule hash. Every model is trained and judged in FFA points. Component models are also reported by their contribution to FFA points.
3. **Structure, team first.** Each game is projected from the team down:
   - a. **Game environment** (team-game): plays, dropback rate, drives, touchdowns, field goal attempts by distance band, sacks, turnovers and yards. Built from shrunk team ratings and pace, adjusted for the opponent, and including rest, home, roof, surface, schedule and the expected quarterback.
   - b. **Availability** (player-game): probability of playing and of a full or partial workload. Built from injury and practice reports, roster status, depth chart, recent snaps, and teammates' and opponents' availability.
   - c. **Role and opportunity** (player-game): shares of dropbacks, targets, air yards, carries, and red-zone and goal-line work. Shares are conditioned on who else is available, and redistribute when a teammate is out.
   - d. **Efficiency** (per opportunity): catch rate, yards, yards after catch, touchdown conversion by field position, fumbles and interceptions. Each is measured against nflverse's expected values (completion probability, expected YAC, rushing yards over expected, expected points) and shrunk with measured constants. Rookies and new roles start from position, role, draft capital and athletic-testing priors.
   - e. **Simulation.** Each simulated game draws team volume, splits it among teammates so their shares sum to the team total, draws each player's efficiency outcomes, and derives the kicker's attempts and the opponent D/ST line from the same simulated game. Every simulated line is scored by the shared engine.

   Outputs: mean, quantiles, per-category expectations, probability of playing, and measured evidence contributions.
4. **Exact rules over simulated lines.** FFA's athlete rules are linear, so an athlete's mean equals the score of his mean line. That is a built-in check on the simulator, not a shortcut. Field goal bands and D/ST yards and points bands are nonlinear and need the simulated distribution. Rule changes flow through the shared scorer without model edits.
5. **Staging.**
   - Baseline B (prior season or positional replacement).
   - Baseline A: empirical-Bayes shrinkage with the measured constants, recency weights, team environment and availability.
   - Then candidates, promoted only through the release gate, which an ADR adopts before any evaluation: gradient-boosted component models (count objectives, season-grouped validation), a hierarchical team-rating model, and a direct FFA-points regression challenger.
6. **Validation.**
   - Season-grouped cross-validation for fitting.
   - Rolling-origin weekly backtests with features rebuilt as of each decision time under the retrospective availability ADR (Q-005).
   - An untouched holdout season; 2026 decided weeks as a live forward test.
   - Block bootstrap by week, calibration of quantiles, and reports by position, role, rookie, injury and week.
   - The only comparisons are Arbit's own baselines and earlier releases.
7. **Horizons.** Weekly first. Rest of season sums weekly distributions over FFA's remaining scoring periods, with byes and availability. Draft season follows.

## Alternatives

- **One direct regression of FFA points.** Simpler, but it cannot keep teammates' shares consistent, misprices the nonlinear D/ST and field goal bands, and explains little. It stays as a challenger.
- **Averages of a player's recent FFA points.** These ignore role change, injuries and the environment, and chase touchdown noise. They become Baseline B's floor, not the model.
- **Deep sequence models.** Weekly samples are small and the nflverse field set is wide. Without evidence of benefit, they add leakage and calibration risk.
- **Other providers' projections or betting lines as inputs.** Excluded by OWN-061; lines wait for Q-014.

## Consequences

- More components to define and validate, but each one is testable alone, and advice can explain itself in measured parts: volume, role, efficiency, availability, matchup.
- Kicker and D/ST projections inherit the offense models, so an error in a team's environment shows up in several players at once. Reports by team-game expose it.
- Without betting lines the game environment is weaker in early weeks. Q-014 states the trade-off for the owner.
- Fields published after a season, like participation, inform only later seasons. Weather is not an input, because nflverse publishes it only after games.

## Validation and adoption

Accepted by the owner on 2026-11-09 (OWN-062): "I approve." Betting lines (Q-014) stay open; the ADR keeps them unused until the owner decides. Evidence for each stage is listed in the [M3 plan](../../superpowers/plans/2026-11-09-m3-model.md). Related: MD-001–MD-004, DATA-002, DATA-007, SC-003; [ADR-003](003-shared-intelligence.md).
