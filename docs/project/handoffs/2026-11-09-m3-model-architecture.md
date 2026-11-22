# Handoff — 2026-11-09 — Model inputs and architecture: nflverse only, team first

## Current state

After M3 slice 1 ([handoff](2026-11-09-m3-ffa-points.md)), the owner directed (OWN-061) that the Model use only nflverse data, considering every field. It must never use another provider's fantasy or projection data, must be weighed against FFA's own scoring, and must take in context beyond a player's own statistics. The owner asked for research into others' methods and a model architecture and development plan.

This handoff covers that research, the proposed architecture and the re-sequenced plan. Everything is on branch `claude/m3-model`, worktree `/home/andre/arbit-m3-model`, uncommitted alongside slice 1. Nothing on the running app changed; the database and object store were only read. No projection exists yet.

## Completed work

- **Research** ([note](../../research/ffa-projection-methods-2026-11-09.md)):
  - How OWN-061 is applied: what counts as nflverse, what is excluded everywhere, why training includes retired players, and why betting lines are left to the owner.
  - A methods review: nflfastR models, expected fantasy points, Open Source Football analyses, WOPR, stabilization, touchdown regression, D/ST practice, teammate correlation, hierarchical Bayes, Petersen's textbook, and a public-data weekly model.
  - Measured signal on our own data.
  - Which fields are known before a game.
- **Signal study** (`scripts/model/ffa_signal_study.py`, [receipt](../../research/ffa-signal-study-2026-11-09.json)). It builds 2016–2025 FFA stat lines with the slice 1 adapter and scores them with the shared engine under the stored rules. Results:
  - Variance share of each FFA category by position.
  - Split-half reliability and games-for-half-signal for 60 statistic-and-position pairs.
  - Opportunity carries half its signal within 0.7–2 games, efficiency in 10–164.
  - Touchdowns are 30–45% of skill-position variance.
  - D/ST and kicker points follow the team and opponent environment.
- **Architecture:** proposed [ADR-006](../../architecture/decisions/006-model-architecture.md). Field catalog for every nflverse field; FFA stat-line target; team environment → availability → role and opportunity → shrunk efficiency → joint simulation scored by the shared engine; Baseline A before ML candidates; season-grouped and rolling-origin validation.
- **Plan:** the [M3 plan](../../superpowers/plans/2026-11-09-m3-model.md) is re-sequenced into nine slices, with slice 2 written in full.
  - Baseline A, weekly and then rest of season, comes before ML candidates, so trade-deadline value doesn't wait on ML.
  - Slice 2 covers the availability ADR (Q-005), the field catalog with a completeness test, historical targets from 2012, participation labels, R-061 and the Model package.
- **Records:**
  - OWN-061; Q-014 (betting lines); Q-009 (outside draft position data excluded).
  - Model specification 0.2; MD-001 title and acceptance changed (outside projections now excluded rather than benchmark-only); MD-002 and MD-004 evidence.
  - R-027 (ESPN ratings stay out of the Model); R-063 (weather published only after games); SRC-26 to SRC-29.
  - ADR index, status, changelog, roadmap note, and the AGENTS.md invariant and latest-handoff link.

## Verification

All commands ran in `/home/andre/arbit-m3-model` on 2026-11-09.

| Command | Result |
| --- | --- |
| `ARBIT_NFLVERSE_PATH=/home/andre/arbit-fantasy-football/data/nflverse uv run --env-file /home/andre/arbit-fantasy-football/.env.local python scripts/model/ffa_signal_study.py docs/research/ffa-signal-study-2026-11-09.json` | 2016–2025 regular seasons, 42 pinned manifests. Relevant player-weeks: QB 4,522, RB 8,985, WR 13,562, TE 6,536, K 4,812; plus 5,160 D/ST team-games. 490 athlete lines refused (R-061). Same numbers as the exploratory run |
| `uv run ruff check scripts/model/ffa_signal_study.py`, `uv run ruff format --check ...`, `uv run mypy --strict ...` | All passed |
| Read-only checks of the stored 2026 schedules, injuries and weekly rosters | Weather empty for every 2026 game (R-063). Lines and expected QBs present for week 10, absent for week 11. Roster status `INA` present (game-day). Injuries cover weeks 1–9 |
| `python3 scripts/validate_foundation.py` | PASS: 46 JSON artifacts, 146 Markdown documents, 60 traceable requirements, local links verified |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | All passed; 201 files formatted, 108 source files clean |
| Full `pytest` | Not rerun: no library, API or client code changed since slice 1's full run (1,290 passed) |

Tests: the study is a read-only research script, like the slice 1 verification tool. No library behavior changed, so no new tests were added.

## Decisions, issues and limitations

- **Owner decisions open:**
  - accept ADR-006;
  - Q-014, betting lines in nflverse schedules;
  - the earlier Lineup-before-Scout sequencing.
- **Interpretations recorded in the research:**
  - "All fields" means a recorded use for every field, not every field as an input.
  - "All currently active players" means every active player at an FFA position is projected, while training also uses retired players' history.
  - ESPN's official points remain the league authority and the check on the FFA conversion; they are not another provider's projection.
- **Signal study limits:** within-season split halves over relevant players; restricting to starters narrows the range. The constants seed Baseline A, and the backtest confirms or replaces them.
- **Source limits:** the methods review mixes peer-reviewed, open-source and industry work, labeled in SRC-26 to SRC-28. Industry claims are hypotheses for the backtest, not adopted facts.

## Resume here

1. Owner: accept or amend ADR-006, decide Q-014, and confirm sequencing.
2. **Slice 2** in the [M3 plan](../../superpowers/plans/2026-11-09-m3-model.md). Write the retrospective availability ADR (Q-005) first, then the field catalog and its completeness test, historical targets 2012–2026, participation labels, R-061, and `libs/arbit-model` as a workspace member.
3. Keep using the worktree. The running worker loads `main`, so merge only on the owner's request.
