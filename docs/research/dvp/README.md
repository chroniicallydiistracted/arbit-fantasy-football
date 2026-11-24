# M3-3 defense against the position: research runbook

**Slice M3-3 continuation.** This continues the existing v0 study under the owner's [DvP specification v1.1](../Arbit_FFA_M3_DvP_Plan.md) (OWN-074). It is not a new slice.

**Purpose:** measure, not assume, whether a defense's record against a position helps predict FFA points. Zero production influence is a valid outcome.

**What it never uses:** ESPN's or any other provider's projected fantasy points, rankings or forecasts, anywhere: features, baselines, priors, fallbacks or comparisons. The only fantasy points used are Arbit's own FFA actuals from completed games ([provenance](SOURCE_PROVENANCE.md)).

**Isolation:** offline and read-only. Nothing here writes canonical scoring tables, feature weights, services or deployments.

## Status (2026-11-24)

| Item | Status |
| --- | --- |
| v0 found, preserved and reproduced exactly | REPRODUCED ([continuity](M3-3_CONTINUITY.md), [reproduction](V0_REPRODUCTION.md)) |
| Source and score audit; projection dependencies = 0 | PASSED |
| Completed-game pipeline: 5,278 team-games reconciled | PASSED ([data quality](DATA_QUALITY.md)) |
| Tests T01–T07 and T29–T40 (with T08–T13, T21–T22) | PASSED, 38 tests |
| A01 on validated observations, with intervals | EXECUTED |
| Phase 2 reliability lab: A00, A02–A10, A12 | EXECUTED ([reliability report](RELIABILITY_REPORT.md), [methodology](METHODOLOGY.md)) |
| Phase 3 walk-forward: B00–B12 on development folds 2017–2023 and 2024 validation | EXECUTED ([backtest report](BACKTEST_REPORT.md)); candidates frozen in `config/dvp/frozen-candidates.json` |
| Phase 4: frozen manifest, 2025 conditional holdout, decisions | EXECUTED. **D/ST PROMISING; QB INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL** ([model card](MODEL_CARD.md)) |
| Prospective 2026 weeks 12–18 (frozen before they were played) | PLANNED ([plan](PROSPECTIVE_2026.md)) |
| C00–C05 (player-level, D/ST only if confirmed) | PLANNED ([registry](EXPERIMENT_REGISTRY.md)) |
| Canonical targets repaired (R-072): all 5,278 D/ST team-games, every opponent from the schedule | DONE ([targets repair](../targets-repair-r072.md), TASK-20261123-007) |

**Headline so far (repeatability only, not forecasting):** REML variance components on adjusted points, each unit with its own game count (A05).

| Group | Games for half signal (k) | 95% interval, season resamples | What it means |
| --- | --- | --- | --- |
| D/ST conceded by the offense | ≈ 7 | 6.0–8.6 | The clearest matchup signal: stable within and across seasons |
| RB | ≈ 20 | 16–27 | Modest; rushing yards allowed repeat fastest (k ≈ 14) |
| QB | ≈ 24 | 16–42 | Modest, and it drifts within a season |
| WR | ≈ 27 | 18–58 | Weak. v0's 44 was an unlucky odd/even split |
| TE, K | ≈ 37, ≈ 50 | 23–97, 33–101 | Weakest; the order among WR, TE and K isn't established |

An offense's own production at a position settles in 4–7 games, so per game a team's result says three to seven times more about its offense than about the defense it faced.

**Forecasting (Phase 3), next-game RMSE against the offense-only B00:**
- **D/ST:** the opponent term (B06: shrunk, k about 8, with a last-season prior) cuts error by 3.0% in development and 6.4% in 2024.
- **QB, RB and WR:** under 1% in development, not replicated in 2024 (WR got worse).
- **TE and K:** nothing.
- **Unshrunk DvP:** makes every position worse.
- **2025 conditional holdout:** D/ST −4.1%, so D/ST is PROMISING; the positions are not.

Whether any of this improves next-game forecasts over an offense-only baseline is Phase B.

## Running it

From a worktree, with the main checkout's data:

```bash
# Phase 0-1 audit: admits sources, builds observations, checks, writes receipts
ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \
  python scripts/model/dvp.py audit --config config/dvp/base.json \
    --targets <main>/data/model --out <main>/artifacts/dvp --receipts docs/research/dvp

# v0: exact rerun, independent recompute, v0-validated with intervals (no database needed)
uv run python scripts/model/dvp.py reproduce-v0 --config config/dvp/base.json \
  --targets <main>/data/model --run <main>/artifacts/dvp/<audit run> --receipts docs/research/dvp

# Phase 2 reliability lab (A00, A02-A10, A12): reads the audit run; A12 reads the database
ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \
  python scripts/model/dvp.py reliability --config config/dvp/reliability.json \
    --targets <main>/data/model --run <main>/artifacts/dvp/<audit run> --receipts docs/research/dvp

# Phase 3 walk-forward: development folds, then validation from the frozen candidates
POLARS_MAX_THREADS=2 ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \
  python scripts/model/dvp.py backtest --config config/dvp/backtest.json --stage development \
    --targets <main>/data/model --run <main>/artifacts/dvp/<audit run> --receipts docs/research/dvp
# (commit config/dvp/frozen-candidates.json, then the same with --stage validation)
# Phase 4: freeze (reads the schedule from the database), commit config/dvp/frozen.json, then
#   ... backtest --stage holdout   (refuses unless every frozen hash matches)
uv run python scripts/model/dvp.py report --receipts docs/research/dvp

# The experiment registry, from the receipts
uv run python scripts/model/dvp.py registry --config config/dvp/base.json --receipts docs/research/dvp

uv run pytest libs/arbit-model/tests/test_dvp_*.py -q
```

**Runtime:** the audit takes about 2 s, the reproduction 8 s, the reliability lab about 80 s, the development backtest about 26 s and validation about 8 s. The DvP tests take about 8 s with `POLARS_MAX_THREADS=2`; with the default thread pool, tiny frames make them several times slower.

**What it reads:**
- the database, read-only, for the league's rules and the pinned nflverse manifests;
- the nflverse object store;
- the FFA targets store pinned by `targets_index` (the R-072-repaired index), and, for v0's rerun only, `v0_targets_index` (the index v0 ran on).

**What it writes:**
- `artifacts/dvp/<run>/`: observations, schedule, half pairs and the run manifest, ignored by git;
- the receipts here.

Runs are timestamped and never overwrite earlier ones. Receipts name the code commit. v0 reads whatever `targets-current.json` names, so the reproduction gives it a pointer of its own to `v0_targets_index` inside the run directory. The reproduction refuses an audit run that read a different index from `targets_index`.

## Documents

| Document | Contents |
| --- | --- |
| [M3-3_CONTINUITY.md](M3-3_CONTINUITY.md) | v0's origin, what is done and what remains |
| [V0_REPRODUCTION.md](V0_REPRODUCTION.md) | Reproduction, k arithmetic, discrepancies and dispositions, validated results |
| [DATA_QUALITY.md](DATA_QUALITY.md) | Reconciliation, cell status, anomalies, hand-checked examples, finality |
| [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) | Allowlist, scoring authority, code scan, rejected projections |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Observation table, views, receipts, configuration |
| [EXPERIMENT_REGISTRY.md](EXPERIMENT_REGISTRY.md) | Every M3-3 experiment and its status |
| [RELIABILITY_REPORT.md](RELIABILITY_REPORT.md) | Phase 2 results: splits, adjustments, variance components, time, carryover, nulls, components, robustness, corrections |
| [METHODOLOGY.md](METHODOLOGY.md) | Hypotheses, estimators, look-ahead protections, and Phase B's comparator and metrics declared before it runs |
| [BACKTEST_REPORT.md](BACKTEST_REPORT.md) | Phases 3–4: B00 and every variant on development folds, 2024 and the 2025 conditional holdout; controls, cutoff and availability sensitivity, candidates, decisions |
| [MODEL_CARD.md](MODEL_CARD.md) | What the forecast is, results by position, intended and unintended use, limits, fallback, eligibility |
| [PROSPECTIVE_2026.md](PROSPECTIVE_2026.md) | The frozen 2026 weeks 12–18 confirmation and how it will be scored |

Decisions, risks, history and handoffs live in the repository's own records:
- the [decision register](../../project/decision-register.md): OWN-074, ENG-057, OWN-075, ENG-058;
- [known issues](../../project/known-issues.md): R-072 to R-074;
- the [changelog](../../project/changelog.md);
- governance tasks TASK-20261123-005, TASK-20261123-007 and TASK-20261124-001 to -003.

**Next:** the prospective 2026 scoring after the season, and Phase C for D/ST if it is confirmed.
