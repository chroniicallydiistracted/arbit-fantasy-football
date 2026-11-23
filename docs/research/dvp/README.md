# M3-3 defense against the position: research runbook

**Slice M3-3 continuation.** This continues the existing v0 study under the owner's [DvP specification v1.1](../Arbit_FFA_M3_DvP_Plan.md) (OWN-074). It is not a new slice.

**Purpose:** measure, not assume, whether a defense's record against a position helps predict FFA points. Zero production influence is a valid outcome.

**What it never uses:** ESPN's or any other provider's projected fantasy points, rankings or forecasts, anywhere: features, baselines, priors, fallbacks or comparisons. The only fantasy points used are Arbit's own FFA actuals from completed games ([provenance](SOURCE_PROVENANCE.md)).

**Isolation:** offline and read-only. Nothing here writes canonical scoring tables, feature weights, services or deployments.

## Status (2026-11-23)

| Item | Status |
| --- | --- |
| v0 found, preserved and reproduced exactly | REPRODUCED ([continuity](M3-3_CONTINUITY.md), [reproduction](V0_REPRODUCTION.md)) |
| Source and score audit; projection dependencies = 0 | PASSED |
| Completed-game pipeline: 5,278 team-games reconciled | PASSED ([data quality](DATA_QUALITY.md)) |
| Tests T01–T07 and T29–T40 (with T08–T13, T21–T22) | PASSED, 38 tests |
| A01 on validated observations, with intervals | EXECUTED |
| A00, A02–A10, A12; B00–B12; C00–C05 | PLANNED ([registry](EXPERIMENT_REGISTRY.md)) |
| Full D/ST coverage | BLOCKED on R-072 (owner decision) |

**Headline so far (repeatability only, not forecasting):**

| Group | Games for half signal (k) | 95% interval, season resamples | What it means |
| --- | --- | --- | --- |
| D/ST conceded by the offense | ≈ 9 | 8–12 | The clearest matchup signal |
| QB (adjusted) | ≈ 22 | 13–46 | Modest |
| RB | ≈ 20 | 11–48 | Modest |
| WR, TE, K | 42–49 | ~20 to over 140 | Weak; v0's order among these three isn't established |

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

# The experiment registry, from the receipts
uv run python scripts/model/dvp.py registry --config config/dvp/base.json --receipts docs/research/dvp

uv run pytest libs/arbit-model/tests/test_dvp_*.py -q
```

**Runtime:** the reproduction took 8 s and the tests about 1 s.

**What it reads:**
- the database, read-only, for the league's rules and the pinned nflverse manifests;
- the nflverse object store;
- the FFA targets store pinned by `targets_index`.

**What it writes:**
- `artifacts/dvp/<run>/`: observations, schedule, half pairs and the run manifest, ignored by git;
- the receipts here.

Runs are timestamped and never overwrite earlier ones. Receipts name the code commit. The reproduction refuses to run if the targets' current pointer has moved from the pinned index, because v0 reads the current pointer.

## Documents

| Document | Contents |
| --- | --- |
| [M3-3_CONTINUITY.md](M3-3_CONTINUITY.md) | v0's origin, what is done and what remains |
| [V0_REPRODUCTION.md](V0_REPRODUCTION.md) | Reproduction, k arithmetic, discrepancies and dispositions, validated results |
| [DATA_QUALITY.md](DATA_QUALITY.md) | Reconciliation, cell status, anomalies, hand-checked examples, finality |
| [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) | Allowlist, scoring authority, code scan, rejected projections |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | Observation table, views, receipts, configuration |
| [EXPERIMENT_REGISTRY.md](EXPERIMENT_REGISTRY.md) | Every M3-3 experiment and its status |

Decisions, risks, history and handoffs live in the repository's own records:
- the [decision register](../../project/decision-register.md): OWN-074, ENG-057;
- [known issues](../../project/known-issues.md): R-072 to R-074;
- the [changelog](../../project/changelog.md);
- governance task TASK-20261123-005.

**Still to write:** methodology, the reliability report, the backtest report and the model card, with phases 2–4.
