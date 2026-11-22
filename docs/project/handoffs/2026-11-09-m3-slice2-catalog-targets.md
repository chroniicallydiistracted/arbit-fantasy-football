# Handoff — 2026-11-09/10 — M3 slice 2: field catalog, historical FFA targets, availability policy

## Current state

The owner accepted ADR-006 ("I approve.", OWN-062). Betting lines (Q-014) and the Lineup-before-Scout order were not part of that answer and stay open.

**Slice 2 is implemented, not released.** It is on branch `claude/m3-model`, worktree `/home/andre/arbit-m3-model`, uncommitted alongside slices 1 and the architecture work.

What touched shared state:
- The database and the nflverse object store were only read.
- Historical targets were written to the private model store, `/home/andre/arbit-fantasy-football/data/model/objects`. Writes are content-addressed and add-only, and the pointer `data/model/targets-current.json` names index `4afbd836…`.
- Nothing on the running app changed.

[ADR-007](../../architecture/decisions/007-model-availability.md) (what the Model may know before each game) is **proposed** and must be accepted by the owner before slice 3 features enter any backtest.

## Completed work

- **Package** `libs/arbit-model`, now a workspace member (root `pyproject.toml`: members, sources, mypy packages, pytest paths; `py.typed`).
- **Field catalog** (`arbit_model.fields`, committed `nflverse_fields.json`):
  - Every imported nflverse field gets one use: `pre_game`, `history`, `earlier_seasons`, `outcome`, `identity` or `excluded`. It comes from 63 ordered rules, each with a reason and, where relevant, a decision (OWN-061, Q-014, R-063).
  - Families with mixed fields list them by name, so a new upstream field matches nothing until classified. `misc` is split by table because its tables share column names.
  - Each entry records its type, tables and first season with a value.
  - Result: 1,827 fields in 32 families. Uses: 148 pre-game, 717 history, 18 earlier seasons, 5 outcome, 411 identity, 528 excluded.
  - Policy outcomes: nflverse `fantasy_points*`, ffopportunity, DynastyProcess values and ESPN draft probabilities are excluded (OWN-061). The DynastyProcess directory is identity only. Betting lines and the line-based win probability are excluded pending Q-014. Weather is `outcome` (R-063). Current-snapshot player fields and draft-pick career totals are excluded because they leak later seasons. Participation is `earlier_seasons`.
  - `scripts/model/field_catalog.py` checks the catalog against the current manifests, or regenerates it with `--write`.
- **Historical targets** (`arbit_model.targets`, `arbit_model.storage`, `arbit_model.inputs`, `scripts/model/build_targets.py`):
  - For every completed game with play-by-play, regular and postseason, 2012–2026:
    - an FFA stat line for every player-game and D/ST team-game, from the slice 1 adapter, scored only by `arbit_core.scoring.score` under the stored rules;
    - participation labels: `played`, `active_no_snaps`, `inactive`, `rostered_no_snaps`, `not_active_roster` or `unknown`, each with its evidence.
  - Zero lines: a player who played (a snap) without a statistics row gets an explicit all-zero line, with its source recorded. This applies at every listed position, because a game's snap position isn't the player's FFA position.
  - R-061: a player whose snap row shows no defensive or special-teams snap is ruled out of an unattributed two-point return. Anything less stays unknown.
  - Storage: each season is three Parquet tables (athlete, defense, participation) and a manifest with its pinned inputs, rules hashes, adapter version, counts and limitations. An index lists the seasons.
- **Verification tool** (`scripts/model/verify_nflverse_scoring.py`):
  - `--pin RECEIPT` replays an earlier receipt's nflverse manifests and decided period.
  - `--targets INDEX --targets-store ROOT` checks every compared line against the stored targets, reported under `targetCheck` outside the hashed comparison.
- **Vintage measurement** (`scripts/model/nflverse_vintages.py`, [receipt](../../research/nflverse-vintages-2026-11-10.json), SRC-30): when each week first appeared in each 2026 nflverse file, from every manifest version the worker kept.
- **Availability policy:** proposed ADR-007.
  - One decision time per game, at kickoff. Inactives reach nflverse only after the game (R-064).
  - Publication rules by family.
  - Observed vintages win from 2026-10-31.
  - nflfastR outputs are allowed, with an ablation inside their fitting window.
  - The worker needs a game-day import after 07:00 UTC (slice 5).
- **Tests** (18, `libs/arbit-model/tests/`):
  - Catalog: rules match the committed file field by field; every rule is used and has a reason; the policy exclusions above; a new upstream field is reported and can't be catalogued silently; `misc` splitting; first-season derivation; render round trip.
  - Targets: every participation label and its evidence; seasons without `INA` or without snap counts; shared-engine scoring; zero lines at any position; R-061 by defensive and special-teams snaps; D/ST lines; no targets without play-by-play; tables keep unknowns null with reasons.
  - The tests were written after the code. Deliberately breaking four behaviors (R-061 off, R-061 ignoring special teams, no zero lines, `INA` not inactive) made them fail; the special-teams case was added after the first such run missed it.
- **Records:**
  - Decisions and issues: OWN-062; ADR-006 accepted; ADR-007 proposed; Q-005 updated; R-061 partly resolved; R-064 and R-065 new.
  - Sources and requirements: SRC-30; MD-002 and MD-004 evidence.
  - Documents: plan slice 2 outcome; model specification note; research note corrected on inactives; status, changelog, AGENTS.md link, package README.

## Verification

All commands ran in `/home/andre/arbit-m3-model` with `ARBIT_NFLVERSE_PATH=/home/andre/arbit-fantasy-football/data/nflverse uv run --env-file /home/andre/arbit-fantasy-football/.env.local` where they read data.

| Command | Result |
| --- | --- |
| `python scripts/model/field_catalog.py --write`, then `python scripts/model/field_catalog.py` | 1,140 current manifests; 1,827 fields catalogued; unclassified `[]`; rule drift `[]`; exit 0 |
| `python scripts/model/build_targets.py --output /home/andre/arbit-fantasy-football/data/model --seasons 2012-2026` | Index `4afbd8364fa7…`. 354,480 player-games, 353,806 scored; 7,402 D/ST team-games, all scored; 93,238 zero lines; 115 lines resolved by R-061; 597,282 participation labels. No completed game lacked play-by-play, and no statistics row fell outside a completed game. Unknowns: 662 unattributed two-point returns, 11 unverified punt return TDs, 1 invalid fumble recovery TD value |
| `python scripts/model/build_targets.py --output <scratch> --seasons 2025-2026 --pin docs/research/nflverse-ffa-scoring-2026-11-09.json` | Index `994b30186f8a…`, built from the slice 1 receipt's manifests |
| `python scripts/model/verify_nflverse_scoring.py --replay /home/andre/arbit-fantasy-football/data/model/espn-verification-2026-11-09 --pin docs/research/nflverse-ffa-scoring-2026-11-09.json --targets 994b30186f8a… --targets-store <scratch>` | Report hash `f503d6ff…`, identical to the slice 1 receipt. Targets: 10,771 checked; 10,734 same points; 21 unknown on both sides; 16 resolved by R-061, all equal to ESPN; 0 missing; 0 mismatches. ESPN played-weeks without a statistics row: 1,381 zero lines, 5 unknown, 96 without a line, each with a reason (35 active with no snap, 24 non-active status with no snap, 9 with no PFR ID, 28 in a game still in progress at the receipt). [Receipt](../../research/ffa-targets-check-2026-11-10.json) |
| `python scripts/model/nflverse_vintages.py 2026 docs/research/nflverse-vintages-2026-11-10.json` | 10 import versions per file; findings in ADR-007 |
| `uv run pytest -q libs/arbit-model/tests` | 18 passed |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | All passed; 208 files formatted; 113 source files clean |
| `uv run ruff check`, `ruff format --check`, `mypy --strict` on `scripts/model/*.py` | All passed (5 files) |
| `python3 scripts/validate_foundation.py` | PASS (after this handoff existed) |
| Full `uv run pytest` | 1,307 passed, 1 failed: `test_foundation_references` ran before this handoff was written and saw its links as broken. Rerun after writing it: passed. Before slice 2 the suite had 1,290 tests |

## Decisions, issues and limitations

- **Owner decisions open:**
  - Accept ADR-007 before any backtest.
  - Q-014, betting lines.
  - Lineup before the full Scout.
- **ADR-007 changes the plan:** one decision time per game, not two (R-064).
- **Limits of the labels (R-065):**
  - 2012 has no snap counts.
  - 2013–2018 rosters don't mark inactives.
  - Players without a PFR ID can't be joined to snaps.
  - Practice-squad elevations keep a non-active status.
  - ESPN's "games played" also counts active players who took no snap.
- **Limits of the targets:**
  - Earlier seasons use nflverse's final revisions, which include stat corrections.
  - The position column is nflverse's current label; `game_position` is that game's snap-count position.
- **Store location:** the targets live in the owner's private `data/model` alongside the slice 1 ESPN capture. Slice 5's release registry will reference index hashes instead of the pointer file.

## Resume here

1. Owner: accept or amend ADR-007; decide Q-014; confirm sequencing.
2. **Slice 3, point-in-time features.** First, a reader that applies ADR-007 to a decision time, with the mutation test: change every row published after the decision time and require an identical feature. Then team environment, availability (injury reports, depth charts, roster moves), role and opportunity, shrunk efficiency and cold-start priors. Every feature records the field catalog entries it reads.
3. Keep using the worktree. The running worker loads `main`, so merge only on the owner's request.
