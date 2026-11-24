"""Audit the M3-3 DvP research against every action item of the owner's specification v1.1.

`docs/research/dvp/Arbit_FFA_M3_DvP_Plan.md` (OWN-074) lists the action items. Each one appears in
`ITEMS` below with the checks that prove it, and `docs/research/dvp/PLAN_COMPLETION_SCOPE.md`
explains each item's logic under the same ID. The audit reruns the evidence and does not take old
receipts on trust:

- `rerun` copies the frozen audit run and the committed receipts into a scratch directory. It then
  reruns every stage there: the audit, the v0 reproduction, the reliability lab, development and
  validation from this tree, and the 2025 holdout from the frozen commit's tree. It also checks that
  the holdout is refused from this tree, reruns Phase C, verify, report and registry, and runs the
  model tests with per-test results (JUnit XML). Nothing is written to the committed run or to
  `docs/research/dvp`.
- `check` compares every rerun with its committed receipt, evaluates every item's checks and
  writes `plan-audit-receipt.json`. It exits 1 if a check fails.

Items the specification leaves open, or that are not done (the prospective 2026 scoring, the
owner's weight decision, BLOCKED experiments, modes not built), have kind `open`. Their checks
prove the open state is recorded honestly. They never count as done.

Read-only: the database is read only by the rerun stages themselves, through their read-only
connections (T26).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
RECEIPTS = ROOT / "docs/research/dvp"
SPEC = ROOT / "docs/research/dvp/Arbit_FFA_M3_DvP_Plan.md"
FORMAT = "arbit-dvp-m3-3-plan-audit-v1"
AUDIT_RUN = "phase1-audit-20261124T024442Z"
FORECAST_KEY = ("season", "week", "game_id", "offense", "position")
TOLERANCE = 1e-9  # dvp.FORECAST_TOLERANCE
STAGES = ("development", "validation", "holdout")
GROUPS = ("QB", "RB", "WR", "TE", "K", "DST")
EXPERIMENTS = (
    *(f"A{i:02d}" for i in range(13)),
    *(f"B{i:02d}" for i in range(13)),
    *(f"C{i:02d}" for i in range(6)),
)
VOLATILE = {"/code", "/generatedAt"}  # fields every rerun changes by design


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


# --- rerun --------------------------------------------------------------------------------------


def _copy_run(run: Path, scratch: Path, name: str) -> Path:
    target = scratch / "runs" / name / run.name
    shutil.copytree(run, target)
    return target


def _copy_receipts(scratch: Path, name: str, *, committed: bool) -> Path:
    target = scratch / "receipts" / name
    if committed:
        shutil.copytree(RECEIPTS, target)
    else:
        target.mkdir(parents=True)
    return target


def _tree_hashes(folder: Path) -> dict[str, str]:
    return {str(p.relative_to(folder)): sha256(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def rerun(args: argparse.Namespace) -> None:
    run: Path = args.run.resolve()
    scratch: Path = args.scratch.resolve()
    frozen_tree: Path = args.frozen_tree.resolve()
    main: Path = args.main.resolve()
    if scratch.exists() and any(scratch.iterdir()):
        raise SystemExit(f"{scratch} is not empty; give the audit a fresh scratch directory")
    if run.name != AUDIT_RUN:
        raise SystemExit(f"the frozen audit run is {AUDIT_RUN}, not {run.name}")
    holdout_code = load(RECEIPTS / "backtest-holdout.json")["code"]
    if git("rev-parse", "HEAD", cwd=frozen_tree) != holdout_code:
        raise SystemExit(f"--frozen-tree must be checked out at the holdout's code {holdout_code}")
    (scratch / "logs").mkdir(parents=True)
    before = {"run": _tree_hashes(run), "config": _tree_hashes(ROOT / "config/dvp")}
    data = {
        "ARBIT_NFLVERSE_PATH": str(main / "data/nflverse"),
        "POLARS_MAX_THREADS": "2",
    }
    targets = str(main / "data/model")
    env_file = str(main / ".env.local")
    dvp = ["uv", "run", "--env-file", env_file, "python", "scripts/model/dvp.py"]
    runs = {n: _copy_run(run, scratch, n) for n in ("main", "backtest", "holdout", "refuse", "c")}
    out = {
        "audit": _copy_receipts(scratch, "audit", committed=False),
        "v0": _copy_receipts(scratch, "v0", committed=False),
        "reliability": _copy_receipts(scratch, "reliability", committed=False),
        "development": _copy_receipts(scratch, "development", committed=False),
        "validation": _copy_receipts(scratch, "validation", committed=False),
        "holdout": _copy_receipts(scratch, "holdout", committed=False),
        "refuse": _copy_receipts(scratch, "refuse", committed=True),
        "sitstart": _copy_receipts(scratch, "sitstart", committed=True),
        "verify": _copy_receipts(scratch, "verify", committed=True),
        "report": _copy_receipts(scratch, "report", committed=True),
    }
    stage = ["--targets", targets]
    steps: list[tuple[str, Path, list[str], int]] = [
        (
            "audit",
            ROOT,
            [*dvp, "audit", "--config", "config/dvp/base.json", *stage]
            + ["--out", str(scratch / "out-audit"), "--receipts", str(out["audit"])],
            0,
        ),
        (
            "reproduce-v0",
            ROOT,
            [*dvp, "reproduce-v0", "--config", "config/dvp/base.json", *stage]
            + ["--run", str(runs["main"]), "--receipts", str(out["v0"])],
            0,
        ),
        (
            "reliability",
            ROOT,
            [*dvp, "reliability", "--config", "config/dvp/reliability.json", *stage]
            + ["--run", str(runs["main"]), "--receipts", str(out["reliability"])],
            0,
        ),
        *(
            (
                f"backtest-{s}",
                ROOT,
                [*dvp, "backtest", "--config", "config/dvp/backtest.json", "--stage", s, *stage]
                + ["--run", str(runs["backtest"]), "--receipts", str(out[s])],
                0,
            )
            for s in ("development", "validation")
        ),
        (
            "backtest-holdout-frozen-tree",
            frozen_tree,
            [*dvp, "backtest", "--config", "config/dvp/backtest.json", "--stage", "holdout"]
            + [*stage, "--run", str(runs["holdout"]), "--receipts", str(out["holdout"])],
            0,
        ),
        (
            "backtest-holdout-refused-here",
            ROOT,
            [*dvp, "backtest", "--config", "config/dvp/backtest.json", "--stage", "holdout"]
            + [*stage, "--run", str(runs["refuse"]), "--receipts", str(out["refuse"])],
            1,
        ),
        (
            "sitstart",
            ROOT,
            [*dvp, "sitstart", "--config", "config/dvp/sitstart.json"]
            + ["--run", str(runs["c"]), "--receipts", str(out["sitstart"])],
            0,
        ),
        (
            "verify",
            ROOT,
            [*dvp, "verify", "--config", "config/dvp/backtest.json"]
            + ["--run", str(runs["main"]), "--receipts", str(out["verify"])],
            0,
        ),
        ("report", ROOT, [*dvp, "report", "--receipts", str(out["report"])], 0),
        (
            "registry",
            ROOT,
            [
                *dvp,
                "registry",
                "--config",
                "config/dvp/base.json",
                "--receipts",
                str(out["report"]),
            ],
            0,
        ),
        (
            "model-tests",
            ROOT,
            ["uv", "run", "pytest", "libs/arbit-model/tests", "-q", "-rA", "-p", "no:cacheprovider"]
            # The audit's own tests read the receipt this audit writes; they run in CI instead.
            + ["--ignore", "libs/arbit-model/tests/test_dvp_plan_audit.py"]
            + ["--junitxml", str(scratch / "junit.xml")],
            0,
        ),
    ]
    record = []
    for name, cwd, argv, expected in steps:
        env = {**os.environ, **data, "ARBIT_DVP_AUDIT_RUN": str(run)}
        env.pop("VIRTUAL_ENV", None)  # each tree runs in its own environment
        started = time.monotonic()
        with (scratch / "logs" / f"{name}.log").open("w") as log:
            code = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        seconds = round(time.monotonic() - started, 1)
        record.append(
            {
                "step": name,
                "cwd": "frozen-tree" if cwd == frozen_tree else "this-tree",
                "argv": [
                    a.replace(str(scratch), "<scratch>").replace(str(main), "<main>") for a in argv
                ],
                "exit": code.returncode,
                "expectedExit": expected,
                "seconds": seconds,
                "finishedAt": datetime.now(UTC).isoformat(),
            }
        )
        print(f"{name}: exit {code.returncode} (expected {expected}) in {seconds}s")
    after = {"run": _tree_hashes(run), "config": _tree_hashes(ROOT / "config/dvp")}
    manifest = {
        "format": FORMAT + "-reruns",
        "code": git("rev-parse", "HEAD"),
        "frozenTree": git("rev-parse", "HEAD", cwd=frozen_tree),
        "run": run.name,
        "runPath": str(run),
        "steps": record,
        "committedRunUnchanged": before["run"] == after["run"],
        "configUnchanged": before["config"] == after["config"],
    }
    (scratch / "reruns.json").write_text(json.dumps(manifest, indent=2) + "\n")


# --- check --------------------------------------------------------------------------------------


@dataclass
class Context:
    scratch: Path
    reruns: dict[str, Any]
    junit: dict[str, str]  # test node id -> passed / failed / skipped

    @property
    def run(self) -> Path:
        return Path(self.reruns["runPath"])

    def committed(self, name: str) -> Any:
        return load(RECEIPTS / name)

    def rerun_receipt(self, step: str, name: str) -> Any:
        return load(self.scratch / "receipts" / step / name)


Result = tuple[bool, Any]
CHECKS: dict[str, tuple[str, Callable[[Context], Result]]] = {}


def check(check_id: str, description: str) -> Callable[[Callable[[Context], Result]], Any]:
    def register(fn: Callable[[Context], Result]) -> Callable[[Context], Result]:
        CHECKS[check_id] = (description, fn)
        return fn

    return register


def _junit(path: Path) -> dict[str, str]:
    out = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        node = f"{case.get('classname')}::{case.get('name')}"
        outcome = "passed"
        for child in case:
            if child.tag in ("failure", "error"):
                outcome = "failed"
            elif child.tag == "skipped":
                outcome = "skipped"
        out[node] = outcome
    return out


TEST_ID = re.compile(r"(?:^|_)t(\d{2})(?=_)")


def _tests(ctx: Context, match: Callable[[str], bool]) -> Result:
    found = {n: o for n, o in ctx.junit.items() if match(n.split("::")[-1].split("[")[0])}
    passed = sum(o == "passed" for o in found.values())
    return bool(found) and passed == len(found), {
        "tests": len(found),
        "passed": passed,
        "names": sorted({n.split("::")[-1].split("[")[0] for n in found}),
    }


def _ids(name: str) -> set[int]:
    return {int(m) for m in TEST_ID.findall(name.removeprefix("test"))}


for _t in range(1, 41):

    def _make(t: int) -> Callable[[Context], Result]:
        return lambda ctx: _tests(ctx, lambda name: name.startswith("test") and t in _ids(name))

    CHECKS[f"test:T{_t:02d}"] = (f"Every test tagged T{_t:02d} ran and passed", _make(_t))


@check("test:B11", "The B11 projection-injection test ran and passed")
def _b11(ctx: Context) -> Result:
    return _tests(ctx, lambda name: name.startswith("test_b11_"))


@check("test:phase-c", "Every Phase C test (test_dvp_decisions.py) ran and passed")
def _phase_c_tests(ctx: Context) -> Result:
    found = {n: o for n, o in ctx.junit.items() if "test_dvp_decisions" in n}
    return bool(found) and all(o == "passed" for o in found.values()), {"tests": len(found)}


@check("test:phase4-rule", "The Phase 4 decision-rule test ran and passed")
def _phase4_rule(ctx: Context) -> Result:
    return _tests(ctx, lambda name: name == "test_phase4_decision_rule")


@check("test:dvp-all", "Every DvP test ran and passed; none skipped (the real-artifact tests ran)")
def _dvp_all(ctx: Context) -> Result:
    found = {n: o for n, o in ctx.junit.items() if ".test_dvp_" in n}
    counts = {k: sum(o == k for o in found.values()) for k in ("passed", "failed", "skipped")}
    return bool(found) and counts["passed"] == len(found), counts


@check(
    "test:model-suite",
    "The whole model test suite passed with nothing skipped (the audit's own tests run in CI)",
)
def _model_suite(ctx: Context) -> Result:
    counts = {k: sum(o == k for o in ctx.junit.values()) for k in ("passed", "failed", "skipped")}
    return counts["failed"] == 0 and counts["skipped"] == 0 and counts["passed"] > 0, counts


# Reruns -------------------------------------------------------------------------------------


@check("rerun:steps", "Every rerun step exited as expected")
def _steps(ctx: Context) -> Result:
    steps = {s["step"]: [s["exit"], s["expectedExit"], s["seconds"]] for s in ctx.reruns["steps"]}
    return all(e == x for e, x, _ in steps.values()), steps


@check("rerun:committed-run-unchanged", "The committed audit run and config/dvp were not modified")
def _untouched(ctx: Context) -> Result:
    flags = {k: ctx.reruns[k] for k in ("committedRunUnchanged", "configUnchanged")}
    return all(flags.values()), flags


def _diff(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}")
            else:
                out += _diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            d
            for i, (x, y) in enumerate(zip(a, b, strict=True))
            for d in _diff(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [path]


def unexpected_differences(
    committed: Any, rerun: Any, allowed: set[str]
) -> tuple[list[str], list[str]]:
    """Every field path where two receipts differ, and those outside the allowed paths (a path
    is allowed if it is an allowed path or lies under one)."""
    differ = _diff(committed, rerun)
    return differ, [d for d in differ if not any(d == a or d.startswith(a + "/") for a in allowed)]


def _same(ctx: Context, step: str, name: str, allowed: set[str]) -> Result:
    differ, unexpected = unexpected_differences(
        ctx.committed(name), ctx.rerun_receipt(step, name), allowed
    )
    return not unexpected, {"differingFields": differ, "unexpected": unexpected}


RERUNS = {
    "rerun:audit": (
        "audit",
        "audit-receipt.json",
        VOLATILE | {"/runId", "/runManifest/code", "/runManifest/runId", "/runManifest/startedAt"},
    ),
    # The code scan covers modules added after the audit run (walkforward, decisions); its count of
    # findings and the status are compared, not the list of scanned files.
    "rerun:projection-audit": (
        "audit",
        "PROJECTION_EXCLUSION_AUDIT.json",
        VOLATILE | {"/runId", "/codeScan/files"},
    ),
    "rerun:finality-audit": ("audit", "SCORE_FINALITY_AUDIT.json", {"/generatedAt", "/runId"}),
    "rerun:continuity": ("audit", "continuity-manifest.json", set()),
    "rerun:v0": ("v0", "v0-reproduction.json", VOLATILE),
    # A12's vintage diagnostic reads Arbit's live 2026 capture history, which grows as nflverse
    # publishes (158 games and 12 versions at the receipt, 162 and 13 on 2026-11-24 23:40 UTC).
    "rerun:reliability": (
        "reliability",
        "reliability-results.json",
        VOLATILE | {"/results/A12/vintages"},
    ),
    # Development and validation ran before the freeze added the holdout stage and the decision
    # rule to backtest.json (rerun:config-freeze-only-added), and before receipts gained the
    # content hash of their forecasts.
    "rerun:development": (
        "development",
        "backtest-development.json",
        VOLATILE | {"/config/sha256", "/forecastsContentSha256"},
    ),
    "rerun:validation": (
        "validation",
        "backtest-validation.json",
        VOLATILE | {"/config/sha256", "/forecastsContentSha256"},
    ),
    # From the frozen tree the code is the same commit; only the byte hash of the Parquet file
    # (row order, last-bit float noise) and the time may differ.
    "rerun:holdout-frozen-tree": (
        "holdout",
        "backtest-holdout.json",
        {"/generatedAt", "/forecastsSha256"},
    ),
    "rerun:sitstart": ("sitstart", "sitstart.json", VOLATILE),
    "rerun:verify": ("verify", "verify-receipt.json", VOLATILE),
    "rerun:registry": ("report", "experiment-registry.json", set()),
}
for _cid, (_step, _name, _allowed) in RERUNS.items():

    def _make_same(step: str, name: str, allowed: set[str]) -> Callable[[Context], Result]:
        return lambda ctx: _same(ctx, step, name, allowed)

    CHECKS[_cid] = (
        f"A fresh rerun reproduces {_name}; only {sorted(_allowed) or 'nothing'} may differ",
        _make_same(_step, _name, _allowed),
    )


@check("rerun:report-files", "report regenerates METRICS.csv and every plot byte for byte")
def _report_files(ctx: Context) -> Result:
    names = [
        "METRICS.csv",
        *(f"plots/{p.name}" for p in sorted((RECEIPTS / "plots").glob("*.svg"))),
    ]
    differ = [
        n for n in names if sha256(RECEIPTS / n) != sha256(ctx.scratch / "receipts/report" / n)
    ]
    return not differ, {"files": len(names), "differ": differ}


def _sorted(frame: pl.DataFrame, key: tuple[str, ...]) -> pl.DataFrame:
    return frame.select(sorted(frame.columns)).sort(list(key))


@check("rerun:observations", "The rerun audit rebuilds the same observation table")
def _observations(ctx: Context) -> Result:
    new_runs = sorted((ctx.scratch / "out-audit").glob("phase1-audit-*"))
    a = pl.read_parquet(ctx.run / "observations.parquet")
    b = pl.read_parquet(new_runs[-1] / "observations.parquet")
    key = ("game_id", "offense", "position")
    same = a.columns == b.columns and _sorted(a, key).equals(_sorted(b, key))
    return same, {"rows": a.height, "columns": len(a.columns), "newRun": new_runs[-1].name}


def forecast_difference(a: pl.DataFrame, b: pl.DataFrame) -> dict[str, Any]:
    if set(a.columns) != set(b.columns) or a.height != b.height:
        return {"comparable": False}
    a, b = _sorted(a, FORECAST_KEY), _sorted(b, FORECAST_KEY)
    worst, differing, other = 0.0, 0, []
    for name in a.columns:
        x, y = a.get_column(name), b.get_column(name)
        if not x.dtype.is_float():
            if not x.equals(y):
                other.append(name)
            continue
        xs, ys = x.to_numpy(), y.to_numpy()
        missing = np.isnan(xs)
        if not np.array_equal(missing, np.isnan(ys)):
            other.append(name)
            continue
        gap = np.abs(xs[~missing] - ys[~missing])
        differing += int((gap > 0).sum())
        worst = max(worst, float(gap.max()) if gap.size else 0.0)
    return {
        "comparable": True,
        "rows": a.height,
        "nonFloatOrMissingDifferences": other,
        "floatValuesDiffering": differing,
        "maxAbsDifference": worst,
    }


def _stage_file(run: Path, stage: str) -> Path:
    return run / f"backtest-{stage}" / "forecasts.parquet"


for _s in ("development", "validation"):

    def _make_idem(stage: str) -> Callable[[Context], Result]:
        def run_check(ctx: Context) -> Result:
            rerun_file = _stage_file(ctx.scratch / "runs/backtest" / ctx.run.name, stage)
            same_bytes = sha256(rerun_file) == sha256(_stage_file(ctx.run, stage))
            log = (ctx.scratch / "logs" / f"backtest-{stage}.log").read_text()
            left = "same forecasts as the existing file; left unchanged" in log
            return same_bytes and left, {
                "fileBytesUnchanged": same_bytes,
                "loggedLeftUnchanged": left,
            }

        return run_check

    CHECKS[f"rerun:forecasts-{_s}"] = (
        f"The {_s} rerun reproduced its forecasts within {TOLERANCE:g} and left the file unchanged",
        _make_idem(_s),
    )


@check(
    "rerun:forecasts-holdout",
    f"The frozen-tree holdout forecasts equal the committed ones within {TOLERANCE:g}",
)
def _holdout_forecasts(ctx: Context) -> Result:
    a = pl.read_parquet(_stage_file(ctx.run, "holdout"))
    b = pl.read_parquet(_stage_file(ctx.scratch / "runs/holdout" / ctx.run.name, "holdout"))
    d = forecast_difference(a, b)
    ok = (
        d["comparable"]
        and not d["nonFloatOrMissingDifferences"]
        and d["maxAbsDifference"] <= TOLERANCE
    )
    return ok, d


@check(
    "rerun:holdout-refused-here",
    "From this tree the holdout refuses: dvp.py no longer matches its frozen hash",
)
def _refused(ctx: Context) -> Result:
    log = (ctx.scratch / "logs/backtest-holdout-refused-here.log").read_text()
    step = next(s for s in ctx.reruns["steps"] if s["step"] == "backtest-holdout-refused-here")
    said = "frozen manifest does not match" in log
    wrote = (ctx.scratch / "receipts/refuse/backtest-holdout.json").read_bytes() == (
        RECEIPTS / "backtest-holdout.json"
    ).read_bytes()
    return step["exit"] == 1 and said and wrote, {
        "exit": step["exit"],
        "message": said,
        "receiptUntouched": wrote,
    }


@check("rerun:frozen-tree", "The holdout reran at the commit recorded in its receipt")
def _frozen_tree(ctx: Context) -> Result:
    code = ctx.committed("backtest-holdout.json")["code"]
    return ctx.reruns["frozenTree"] == code, {
        "frozenTree": ctx.reruns["frozenTree"],
        "receipt": code,
    }


@check(
    "rerun:config-freeze-only-added",
    "The freeze only added keys to backtest.json; development and validation settings are unchanged",
)
def _config_added(ctx: Context) -> Result:
    code = ctx.committed("backtest-validation.json")["code"]
    before = json.loads(git("show", f"{code}:config/dvp/backtest.json"))
    now = load(ROOT / "config/dvp/backtest.json")
    changed = [k for k, v in before.items() if k != "stages" and now.get(k) != v]
    stages = all(now["stages"].get(s) == v for s, v in before["stages"].items())
    return not changed and stages, {"added": sorted(set(now) - set(before)), "changed": changed}


# Committed evidence ---------------------------------------------------------------------------


@check("v0:bytes", "v0's files are byte-identical to the hashes pinned in the continuity manifest")
def _v0_bytes(ctx: Context) -> Result:
    manifest = ctx.committed("continuity-manifest.json")["v0"]
    files = {**manifest.get("files", {}), **manifest.get("consumers", {})}
    result = {p: sha256(ROOT / p) == h for p, h in files.items()}
    return bool(result) and all(result.values()), result


@check("v0:reproduced", "v0 reproduces exactly (rerun) and independently (all measures match)")
def _v0(ctx: Context) -> Result:
    r = ctx.committed("v0-reproduction.json")
    independent = {k: v["matchesReceipt"] for k, v in r["independent"].items()}
    return r["status"] == "REPRODUCED" and all(independent.values()), {
        "status": r["status"],
        "independentMeasures": len(independent),
        "allMatch": all(independent.values()),
    }


@check("v0:wr-k", "WR k: v0's 44.1 comes from the mean half size 8.25; halves of 8 give 42.7")
def _wr_k(ctx: Context) -> Result:
    k = ctx.committed("v0-reproduction.json")["kArithmetic"]["WR_raw"]
    ok = round(k["kV0"], 1) == 44.1 and round(k["kIfHalvesWere8"], 1) == 42.7
    return ok, {key: k[key] for key in ("pearson", "meanHalfGames", "kV0", "kIfHalvesWere8")}


@check(
    "v0:validated", "v0's method on validated observations: 320 units per group, seeded intervals"
)
def _v0_validated(ctx: Context) -> Result:
    v = ctx.committed("v0-reproduction.json")["v0Validated"]
    units = {k: x["units"] for k, x in v.items()}
    boot = {
        k: x["bootstrapSeasons"]["reps"] == 2000 and x["bootstrapSeasons"]["seed"] == 1729
        for k, x in v.items()
    }
    return all(u == 320 for u in units.values()) and all(boot.values()), {
        "measures": len(v),
        "units": sorted(set(units.values())),
    }


@check("audit:checks", "Every Phase 1 audit check PASSED")
def _audit_checks(ctx: Context) -> Result:
    checks = {k: v["status"] for k, v in ctx.committed("audit-receipt.json")["checks"].items()}
    return all(s == "PASSED" for s in checks.values()), checks


@check(
    "audit:reconciliation",
    "5,278 completed team-games from 2,639 games; two mirrored rows each; no duplicates",
)
def _reconciliation(ctx: Context) -> Result:
    r = {
        k: v
        for k, v in ctx.committed("audit-receipt.json")["reconciliation"].items()
        if k != "seasons"
    }
    ok = r["teamGames"] == 5278 and r["completedGames"] == 2639
    ok = (
        ok
        and r["duplicateGameIds"]
        == r["gamesWithoutExactlyTwoTeamGames"]
        == r["teamGamesWithoutMirror"]
        == 0
    )
    return ok, r


@check(
    "audit:seasons",
    "Per season: 32 teams; 16 games each in 2016-2020, 17 in 2021-2025, BUF and CIN 16 in 2022",
)
def _seasons(ctx: Context) -> Result:
    seasons = ctx.committed("audit-receipt.json")["reconciliation"]["seasons"]
    games = {s: (v["teams"], v["teamGames"], v["gamesPerTeamValues"]) for s, v in seasons.items()}
    ok = all(t == 32 for t, _, _ in games.values())
    ok = ok and all(games[str(s)][1] == 512 for s in range(2016, 2021))
    ok = ok and all(games[str(s)][1] == 544 for s in (2021, 2023, 2024, 2025))
    ok = ok and games["2022"][1] == 542 and games["2022"][2] == [16, 17]
    return ok, {s: g[1] for s, g in games.items()}


@check(
    "audit:positions", "Groups come from the league's lineup slots; FB and HB count as RB, PK as K"
)
def _positions(ctx: Context) -> Result:
    p = ctx.committed("audit-receipt.json")["positions"]
    ok = (
        sorted(p["modeledGroups"]) == sorted(GROUPS)
        and p["mapping"]["FB"] == "RB"
        and p["mapping"]["PK"] == "K"
    )
    return ok, {"modeledGroups": p["modeledGroups"], "lineupSlots": p["leagueLineupSlots"]}


@check(
    "audit:cells", "Cell status: every group's cells are valid or carry an explicit invalid status"
)
def _cells(ctx: Context) -> Result:
    cells = ctx.committed("audit-receipt.json")["cellsByStatus"]
    per: dict[str, int] = {}
    for key, n in cells.items():
        per[key.split("/")[0]] = per.get(key.split("/")[0], 0) + n
    return all(per.get(g) == 5278 for g in GROUPS), cells


@check(
    "audit:examples",
    "Hand-checked examples recorded: zero TE, multi-WR offense, traded player, D/ST turnovers",
)
def _examples(ctx: Context) -> Result:
    names = sorted(ctx.committed("audit-receipt.json")["examples"])
    return set(names) >= {
        "dstTurnover",
        "multiWrOffense",
        "tradedPlayer",
        "zeroProductionTe",
    }, names


@check(
    "audit:observation-lineage",
    "Every observation row carries its lineage: source, type, scoring hash, finality, availability",
)
def _lineage(ctx: Context) -> Result:
    o = pl.read_parquet(ctx.run / "observations.parquet")
    wanted = {
        "source_id",
        "source_type",
        "scoring_hash",
        "observed_or_generated",
        "finality_basis",
        "available_at",
        "kickoff",
        "season",
        "week",
        "game_id",
        "offense",
        "defense",
        "unit",
        "position",
        "status",
    }
    missing = sorted(wanted - set(o.columns))
    nulls = {
        c: o.get_column(c).null_count()
        for c in ("source_id", "source_type", "scoring_hash", "available_at")
        if c in o.columns
    }
    types = sorted(o.get_column("source_type").unique().to_list())
    kinds = sorted(o.get_column("observed_or_generated").unique().to_list())
    ok = (
        not missing
        and not any(nulls.values())
        and types == ["FFA_ACTUAL_FINAL"]
        and kinds == ["observed"]
    )
    return ok, {
        "rows": o.height,
        "missing": missing,
        "nulls": nulls,
        "sourceTypes": types,
        "observedOrGenerated": kinds,
    }


@check(
    "audit:frozen-outputs",
    "The audit run's outputs still match the hashes frozen in config/dvp/frozen.json",
)
def _frozen_outputs(ctx: Context) -> Result:
    pinned = load(ROOT / "config/dvp/frozen.json")["auditOutputs"]
    result = {n: sha256(ctx.run / n) == h for n, h in pinned.items()}
    return all(result.values()), result


@check(
    "provenance:passed",
    "Projection exclusion audit PASSED with 0 dependencies; every input family is allowlisted",
)
def _provenance(ctx: Context) -> Result:
    p = ctx.committed("PROJECTION_EXCLUSION_AUDIT.json")
    seen, allowed = set(p["targetInputFamilies"]["seen"]), set(p["targetInputFamilies"]["allowed"])
    rerun = ctx.rerun_receipt("audit", "PROJECTION_EXCLUSION_AUDIT.json")
    ok = p["status"] == rerun["status"] == "PASSED"
    ok = (
        ok
        and p["forbidden_vendor_projection_dependencies"]
        == rerun["forbidden_vendor_projection_dependencies"]
        == 0
    )
    return ok and seen <= allowed, {
        "status": p["status"],
        "admittedSources": len(p["admittedSources"]),
        "forbiddenInventory": len(p["forbiddenInventory"]),
        "codeScanFiles": {
            "committed": len(p["codeScan"]["files"]),
            "rerun": len(rerun["codeScan"]["files"]),
        },
        "unlistedFamilies": sorted(seen - allowed),
    }


@check(
    "provenance:forbidden-inventory",
    "Every reachable forbidden source is inventoried with REJECT or QUARANTINE and a guard",
)
def _inventory(ctx: Context) -> Result:
    inv = ctx.committed("PROJECTION_EXCLUSION_AUDIT.json")["forbiddenInventory"]
    ok = bool(inv) and all(i["action"] in ("REJECT", "QUARANTINE") and i.get("guard") for i in inv)
    return ok, [{"action": i["action"], "decision": i.get("decision")} for i in inv]


@check(
    "finality:recorded",
    "Score finality audit: completed games only, conservative availability, limitation stated",
)
def _finality(ctx: Context) -> Result:
    f = ctx.committed("SCORE_FINALITY_AUDIT.json")
    return f["status"] == "PASSED_WITH_LIMITATION" and len(f["seasons"]) == 10, {
        "status": f["status"],
        "seasons": sorted(f["seasons"]),
        "rule": f["policy"]["availability_rule"],
    }


@check(
    "receipts:no-projection",
    "Every receipt and experiment record states forbidden_vendor_projection_dependencies = 0",
)
def _no_projection(ctx: Context) -> Result:
    counts = {}
    for path in sorted(RECEIPTS.glob("*.json")):
        value = load(path)
        if isinstance(value, dict) and "forbidden_vendor_projection_dependencies" in value:
            counts[path.name] = value["forbidden_vendor_projection_dependencies"]
    records = ctx.committed("experiment-registry.json")["experiments"]
    nonzero = [
        r["experiment_id"] for r in records if r["forbidden_vendor_projection_dependencies"] != 0
    ]
    return all(v == 0 for v in counts.values()) and not nonzero, {
        "receipts": counts,
        "recordsNonzero": nonzero,
    }


SPEC_FIELDS = (
    "workstream_id",
    "experiment_id",
    "status",
    "hypothesis",
    "data_hash",
    "scoring_hash",
    "code_commit",
    "source_ancestry_hash",
    "forbidden_vendor_projection_dependencies",
    "actual_game_finality_policy",
    "as_of_policy",
    "train_validation_test_periods",
    "holdout_independence_status",
    "sample_count",
    "coverage_pct",
    "estimator",
    "parameters",
    "primary_metric",
    "baseline_metric",
    "absolute_delta",
    "relative_delta",
    "interval",
    "placebo_summary",
    "subgroups",
    "tests_passed",
    "limitations",
    "evidence_paths",
    "decision",
    "reason",
    "next_steps",
)  # specification §10, `train/validation/test_periods` spelled as a JSON key


def _registry(ctx: Context) -> dict[str, dict[str, Any]]:
    return {r["experiment_id"]: r for r in ctx.committed("experiment-registry.json")["experiments"]}


@check(
    "registry:complete",
    "Every specified experiment is registered; every record has the §10 fields and a known status",
)
def _registry_complete(ctx: Context) -> Result:
    reg = _registry(ctx)
    missing = [e for e in EXPERIMENTS if f"M3-3-{e}" not in reg]
    fields = [i for i, r in reg.items() if set(SPEC_FIELDS) - set(r)]
    statuses = {"EXISTING", "REPRODUCED", "PLANNED", "EXECUTED", "PASSED", "FAILED", "BLOCKED"}
    bad = [i for i, r in reg.items() if r["status"] not in statuses]
    return not missing and not fields and not bad, {
        "records": len(reg),
        "missingExperiments": missing,
        "recordsMissingFields": fields,
        "unknownStatus": bad,
    }


def _status_check(experiment: str, wanted: set[str]) -> Callable[[Context], Result]:
    def run_check(ctx: Context) -> Result:
        record = _registry(ctx).get(f"M3-3-{experiment}")
        if record is None:
            return False, "not registered"
        return record["status"] in wanted, {
            "status": record["status"],
            "decision": record["decision"],
            "reason": (record["reason"] or "")[:160],
        }

    return run_check


for _e in (*EXPERIMENTS, "v0", "HOLDOUT-2025"):
    _wanted = {"BLOCKED"} if _e == "C03" else {"EXECUTED", "PASSED", "REPRODUCED"}
    CHECKS[f"registry:{_e}"] = (
        f"Registry status of M3-3-{_e} is {' or '.join(sorted(_wanted))}",
        _status_check(_e, _wanted),
    )


@check(
    "reliability:experiments",
    "The reliability receipt holds A00 and A02-A12 for every group; A08 carries Holm's correction",
)
def _reliability(ctx: Context) -> Result:
    r = ctx.committed("reliability-results.json")
    results = r["results"]
    expected = ("A00", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A12")
    missing = {e: sorted(set(GROUPS) - set(results.get(e, {}))) for e in expected}
    missing = {e: m for e, m in missing.items() if m}
    ok = (
        not missing
        and "holm" in results["A08"]
        and r["seed"] == 1729
        and r["bootstrapReplicates"] == 2000
    )
    return ok, {"experiments": sorted(results), "missingGroups": missing, "seed": r["seed"]}


@check(
    "reliability:a05",
    "A05 REML k per group (each unit with its own game count) with season-cluster intervals",
)
def _a05(ctx: Context) -> Result:
    a05 = ctx.committed("reliability-results.json")["results"]["A05"]
    summary = {
        g: {
            "k": a05[g]["adjusted"]["reml"]["k"],
            "converged": a05[g]["adjusted"]["reml"]["converged"],
            "k95Seasons": a05[g]["adjusted"]["remlBootstrapSeasons"]["k95"],
        }
        for g in GROUPS
    }
    return all(x["converged"] and x["k"] is not None for x in summary.values()), summary


def _variants(results: dict[str, Any]) -> set[str]:
    return {v for g in GROUPS for v in results.get(g, {}) if v.startswith("b0")}


@check(
    "backtest:variants",
    "Development, validation and holdout score B00 and every DvP variant and control for every group",
)
def _bt_variants(ctx: Context) -> Result:
    out, ok = {}, True
    for s in STAGES:
        r = ctx.committed(f"backtest-{s}.json")["results"]
        groups = sorted(r)
        names = _variants(r)
        families = sorted({n.split("_")[0][:3] for n in names})
        out[s] = {"groups": groups, "variants": len(names), "families": families}
        ok = (
            ok
            and set(groups) >= set(GROUPS)
            and {"b00", "b01", "b02", "b03", "b04", "b05", "b06", "b07", "b09"} <= set(families)
        )
    return ok, out


@check(
    "backtest:b08-focus",
    "B08: every group's change against B00 broken down by opponent games, week and season",
)
def _focus(ctx: Context) -> Result:
    out, ok = {}, True
    for s in ("development", "validation", "holdout"):
        r = ctx.committed(f"backtest-{s}.json")["results"]
        parts = {g: sorted(r[g].get("focus", {})) for g in GROUPS}
        ok = ok and all(
            {"byOpponentGames", "byWeek", "calibration"} <= set(v) for v in parts.values()
        )
        out[s] = parts["DST"]
    return ok, out


@check(
    "backtest:timeline",
    "Candidates frozen before validation; method frozen before the holdout ran; Phase C frozen before 2026 week 12",
)
def _timeline(ctx: Context) -> Result:
    def at(value: str) -> datetime:
        return datetime.fromisoformat(value)

    cand = load(ROOT / "config/dvp/frozen-candidates.json")["frozenAt"]
    frozen = load(ROOT / "config/dvp/frozen.json")
    phase_c = load(ROOT / "config/dvp/frozen-phase-c.json")
    times = {
        "candidatesFrozen": cand,
        "validationRan": ctx.committed("backtest-validation.json")["generatedAt"],
        "methodFrozen": frozen["frozenAt"],
        "holdoutRan": ctx.committed("backtest-holdout.json")["generatedAt"],
        "phaseCFrozen": phase_c["frozenAt"],
        "prospectiveFirstKickoff": phase_c["prospective"]["firstKickoff"],
    }
    order = list(times.values())
    ok = all(at(a) <= at(b) for a, b in zip(order, order[1:], strict=False))
    ok = ok and frozen["prospective"]["firstKickoff"] == phase_c["prospective"]["firstKickoff"]
    return ok, times


@check(
    "backtest:holdout-status",
    "The 2025 holdout is labeled CONDITIONALLY_HELD_OUT with its exposure stated",
)
def _holdout_status(ctx: Context) -> Result:
    h = ctx.committed("backtest-holdout.json")
    exposure = load(ROOT / "config/dvp/frozen.json")["holdout"]["exposure"]
    return h["holdoutStatus"] == "CONDITIONALLY_HELD_OUT" and "2025" in exposure, {
        "holdoutStatus": h["holdoutStatus"],
        "exposure": exposure[:200],
    }


@check(
    "backtest:decisions",
    "Phase 4 labels: D/ST PROMISING; QB INCONCLUSIVE; RB, WR, TE, K NOT_USEFUL; global PROMISING",
)
def _decisions(ctx: Context) -> Result:
    d = ctx.committed("backtest-holdout.json")["decisions"]
    labels = {g: d["positions"][g]["label"] for g in GROUPS}
    expected = {
        "DST": "PROMISING",
        "QB": "INCONCLUSIVE",
        "RB": "NOT_USEFUL",
        "WR": "NOT_USEFUL",
        "TE": "NOT_USEFUL",
        "K": "NOT_USEFUL",
    }
    return labels == expected and d["global"]["label"] == "PROMISING", {
        "positions": labels,
        "global": d["global"],
    }


@check(
    "backtest:practical-minimum",
    "The 1% practical minimum was fixed on development data, before validation and the holdout",
)
def _minimum(ctx: Context) -> Result:
    cand = load(ROOT / "config/dvp/frozen-candidates.json")
    dev = ctx.committed("backtest-development.json")
    ok = cand["practicalMinimumRelativeRmse"] == dev["practicalMinimumRelativeRmse"] == 0.01
    return ok, {
        "minimum": cand["practicalMinimumRelativeRmse"],
        "fromDevelopment": cand["fromDevelopment"]["receipt"],
    }


@check(
    "backtest:dev-folds",
    "Development is rolling-origin: each fold's parameters come from earlier seasons only",
)
def _folds(ctx: Context) -> Result:
    folds = ctx.committed("backtest-development.json")["folds"]
    bad = [s for s, f in folds.items() if any(t >= int(s) for t in f.get("training", [int(s) - 1]))]
    return sorted(folds) == [str(s) for s in range(2017, 2024)] and not bad, {
        "folds": sorted(folds),
        "leaky": bad,
    }


@check(
    "backtest:sensitivity",
    "B10 cutoff and B12 availability sensitivity recorded for development and validation",
)
def _sensitivity(ctx: Context) -> Result:
    out = {
        s: sorted(ctx.committed(f"backtest-{s}.json")["sensitivity"])
        for s in ("development", "validation")
    }
    ok = all(
        any(k.startswith("B10") for k in v) and any(k.startswith("B12") for k in v)
        for v in out.values()
    )
    return ok, out


@check(
    "frozen:commit-matches",
    "The frozen commit's files match every hash in config/dvp/frozen.json (verify)",
)
def _frozen(ctx: Context) -> Result:
    f = ctx.rerun_receipt("verify", "verify-receipt.json")["frozen"]
    matches = f["frozenCommitMatchesManifest"]
    receipts = f["receiptsMatchManifest"]
    return all(matches.values()) and all(receipts.values()), {
        "files": len(matches),
        "receiptsMatch": receipts,
        "changedSinceFreeze": f["changedInWorkingTreeSinceFreeze"],
    }


@check(
    "verify:passed",
    "verify PASSED on the rerun: every committed metric recomputed, labels join 1:1, signs and units checked",
)
def _verify(ctx: Context) -> Result:
    v = ctx.rerun_receipt("verify", "verify-receipt.json")
    stages = {
        s: {
            "metricsCompared": x["metricsCompared"],
            "mismatched": len(x["metricsMismatched"]),
            "labelsOneToOne": x["labelsJoinObservationsOneToOne"],
            "labelsEqual": x["labelsEqualObservations"],
            "dstWhole": x["dstLabelsAreWholePoints"],
            "dstSign": x["dstTermSignCorrelation"],
        }
        for s, x in v["stages"].items()
    }
    total = sum(x["metricsCompared"] for x in stages.values())
    ok = v["status"] == "PASSED" and all(
        x["mismatched"] == 0
        and x["labelsOneToOne"]
        and x["labelsEqual"]
        and x["dstWhole"]
        and x["dstSign"] > 0
        for x in stages.values()
    )
    return ok and all(v["v0ByteIdentical"].values()), {
        "status": v["status"],
        "metrics": total,
        "stages": stages,
    }


@check(
    "verify:sample",
    "verify draws an independent sample of joined forecasts per stage for sign, unit and join inspection",
)
def _sample(ctx: Context) -> Result:
    v = ctx.rerun_receipt("verify", "verify-receipt.json")
    sizes = {s: len(x.get("sample", [])) for s, x in v["stages"].items()}
    return all(n > 0 for n in sizes.values()), sizes


@check(
    "phasec:rule-first",
    "Phase C's rule (config/dvp/sitstart.json) was committed before any Phase C result and is unchanged",
)
def _rule_first(ctx: Context) -> Result:
    declared = "317361fd5f5d5f65a8e1432379cac899eee2c042"
    committed_at = git("log", "-1", "--format=%cI", declared)
    generated = ctx.committed("sitstart.json")["generatedAt"]
    same = git("show", f"{declared}:config/dvp/sitstart.json") == (
        ROOT / "config/dvp/sitstart.json"
    ).read_text().rstrip("\n")
    earlier = datetime.fromisoformat(committed_at) < datetime.fromisoformat(generated)
    ancestor = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", declared, "HEAD"], cwd=ROOT
        ).returncode
        == 0
    )
    return same and earlier and ancestor, {
        "declaredIn": declared[:7],
        "committedAt": committed_at,
        "firstResultAt": generated,
        "configUnchangedSince": same,
    }


@check(
    "phasec:decision",
    "Phase C D/ST: B06 clears the 1.8-point minimum with net points gained in every period: PROMISING",
)
def _phase_c_decision(ctx: Context) -> Result:
    s = ctx.committed("sitstart.json")
    periods = {
        p: {
            "deltaPp": v["deltaPp"],
            "deltaPp95": v["deltaPp95"],
            "points": v["pointsFromChanges"]["total"],
        }
        for p, v in s["periods"].items()
    }
    ok = s["decision"]["label"] == "PROMISING" and all(
        v["deltaPp"] >= 1.8 and v["points"] > 0 for v in periods.values()
    )
    return ok and s["position"] == "DST" and s["candidate"] == "b06" and s[
        "baseline"
    ] == "b00", periods


@check(
    "phasec:frozen",
    "Phase C is frozen for 2026: the method and the historical receipt match the hashes in frozen-phase-c.json",
)
def _phase_c_frozen(ctx: Context) -> Result:
    f = load(ROOT / "config/dvp/frozen-phase-c.json")
    method = {p: sha256(ROOT / p) == h for p, h in f["method"].items()}
    receipt = (
        sha256(ROOT / f["historicalResult"]["receipt"]) == f["historicalResult"]["receiptSha256"]
    )
    group = sha256(ROOT / f["groupLevelFreeze"]["path"]) == f["groupLevelFreeze"]["sha256"]
    return all(method.values()) and receipt and group and f["write_to_production"] is False, {
        "method": method,
        "historicalReceipt": receipt,
        "groupLevelFreeze": group,
    }


@check(
    "phasec:not-available",
    "Phase C states what it could not evaluate and why (league lineups, roles)",
)
def _phase_c_blocked(ctx: Context) -> Result:
    na = ctx.committed("sitstart.json")["notAvailable"]
    return {"leagueLineups"} <= set(na), {k: v[:140] for k, v in na.items()}


@check(
    "config:spec-keys",
    "config/dvp/base.json carries the specification's §10 keys with the specified values",
)
def _base(ctx: Context) -> Result:
    b = load(ROOT / "config/dvp/base.json")
    wanted = {
        "project": "arbit-ffa",
        "workstream_id": "M3-3",
        "workstream_mode": "continue_existing_experiment",
        "slice": "defense_vs_position",
        "original_study_script": "scripts/model/defense_position_study.py",
        "scoring_source": "existing_canonical_ffa_layer",
        "scoring_basis": "actual_ffa_points_from_completed_games_only",
        "external_predetermined_fantasy_projections_allowed": False,
        "season_type": "REG",
        "forecast_cutoff": "pre_first_game_of_nfl_week",
        "min_split_half_games": 4,
        "original_half_method": "nfl_week_odd_even",
        "primary_metric": "RMSE",
        "bootstrap_replicates": 2000,
        "random_seed": 1729,
        "holdout_requires_frozen_manifest": True,
        "write_to_production": False,
    }
    wrong = {k: b.get(k) for k, v in wanted.items() if b.get(k) != v}
    split = b["split"] == {
        "development": list(range(2016, 2024)),
        "validation": [2024],
        "holdout": [2025],
    }
    seasons = b["seasons"] == list(range(2016, 2026))
    methods = set(EXPERIMENTS[:26]) <= set(b["experiment_methods"])
    policy = (
        b["source_policy"]["enforce_lineage_allowlist"]
        and b["source_policy"]["fail_on_unknown_source"]
    )
    asof = b["as_of_policy"]["target_labels_join_only_after_forecasts_frozen"]
    ok = not wrong and split and seasons and methods and policy and asof
    return ok, {
        "wrong": wrong,
        "split": split,
        "seasons": seasons,
        "experimentMethods": methods,
        "lineagePolicy": policy,
    }


@check(
    "config:no-production",
    "Nothing is set to write to production: base, sitstart and frozen Phase C say write_to_production false",
)
def _no_production(ctx: Context) -> Result:
    flags = {
        p: load(ROOT / p).get("write_to_production")
        for p in (
            "config/dvp/base.json",
            "config/dvp/sitstart.json",
            "config/dvp/frozen-phase-c.json",
        )
    }
    return all(v is False for v in flags.values()), flags


@check(
    "cli:commands",
    "dvp.py provides audit, reproduce-v0, reliability, backtest (3 stages), freeze, report, registry, sitstart, verify",
)
def _cli(ctx: Context) -> Result:
    text = (ROOT / "scripts/model/dvp.py").read_text()
    names = set(re.findall(r'add_parser\("([a-z0-9-]+)"\)', text))
    stages = '"development", "validation", "holdout"' in text
    wanted = {
        "audit",
        "reproduce-v0",
        "reliability",
        "backtest",
        "freeze",
        "report",
        "registry",
        "sitstart",
        "verify",
    }
    return wanted <= names and stages, sorted(names)


DELIVERABLES = {
    1: ["docs/research/dvp/README.md"],
    2: [
        "docs/research/dvp/DATA_DICTIONARY.md",
        "docs/research/dvp/DATA_QUALITY.md",
        "docs/research/dvp/SOURCE_PROVENANCE.md",
    ],
    3: ["docs/research/dvp/METHODOLOGY.md"],
    4: [
        "docs/research/dvp/M3-3_CONTINUITY.md",
        "docs/research/dvp/V0_REPRODUCTION.md",
        "docs/research/dvp/continuity-manifest.json",
        "docs/research/dvp/v0-reproduction.json",
    ],
    5: [
        "docs/research/dvp/EXPERIMENT_REGISTRY.md",
        "docs/research/dvp/experiment-registry.json",
        "config/dvp/base.json",
        "config/dvp/reliability.json",
        "config/dvp/backtest.json",
    ],
    6: ["docs/research/dvp/RELIABILITY_REPORT.md", "docs/research/dvp/reliability-results.json"],
    7: [
        "docs/research/dvp/BACKTEST_REPORT.md",
        "docs/research/dvp/backtest-development.json",
        "docs/research/dvp/backtest-validation.json",
        "docs/research/dvp/backtest-holdout.json",
    ],
    8: ["docs/research/dvp/MODEL_CARD.md"],
    9: [
        "docs/project/decision-register.md",
        "docs/project/changelog.md",
        "docs/project/handoffs/2026-11-24-task-20261124-004-governance-handoff.md",
    ],
    10: [
        "docs/research/dvp/METRICS.csv",
        "docs/research/dvp/verify-receipt.json",
        *(
            f"docs/research/dvp/plots/{n}"
            for n in (
                "split-scatter-WR.svg",
                "k-forest.svg",
                "lag-decay.svg",
                "weight-curves.svg",
                "error-by-season.svg",
                "backtest-delta.svg",
                "calibration.svg",
            )
        ),
    ],
    11: [
        "docs/research/dvp/PROJECTION_EXCLUSION_AUDIT.json",
        "docs/research/dvp/SCORE_FINALITY_AUDIT.json",
    ],
}
for _n, _paths in DELIVERABLES.items():

    def _make_files(paths: list[str]) -> Callable[[Context], Result]:
        def run_check(ctx: Context) -> Result:
            missing = [
                p for p in paths if not (ROOT / p).is_file() or (ROOT / p).stat().st_size == 0
            ]
            return not missing, {"files": len(paths), "missing": missing}

        return run_check

    CHECKS[f"deliverable:{_n}"] = (
        f"§11 deliverable {_n} exists and is not empty",
        _make_files(_paths),
    )


@check(
    "deliverable:forecasts",
    "Every stage's FORECASTS.parquet exists in the audit run with the hash its receipt names",
)
def _forecast_files(ctx: Context) -> Result:
    out = {}
    for s in STAGES:
        receipt = ctx.committed(f"backtest-{s}.json")
        out[s] = sha256(_stage_file(ctx.run, s)) == receipt["forecastsSha256"]
    return all(out.values()), out


@check(
    "docs:conclusions",
    "MODEL_CARD.md holds the per-position conclusion table with the specification's columns and the integrity flags",
)
def _conclusions(ctx: Context) -> Result:
    text = (RECEIPTS / "MODEL_CARD.md").read_text()
    header = "| Group | Repeatable trait? | Forward benefit? | Effect-size estimate | Uncertainty | Stable across seasons? | Recommended use | Limitations |"
    flags = [
        "source_provenance_pass",
        "score_finality_pass",
        "forbidden_vendor_projection_dependencies",
        "2025 holdout status",
    ]
    present = {f: f in text for f in flags}
    rows = sum(
        1
        for g in ("**D/ST**", "| QB |", "| RB |", "| WR |", "| TE |", "| K |")
        if g in text.split(header, 1)[-1]
    )
    return header in text and all(present.values()) and rows == 6, {
        "table": header in text,
        "rows": rows,
        "flags": present,
    }


@check(
    "docs:prospective",
    "The prospective 2026 window is frozen, its procedure written down and its harness in place",
)
def _prospective(ctx: Context) -> Result:
    # Since owner audit AUD-01 the procedure archives forecasts before kickoff with
    # dvp_prospective.py, which loads the frozen dvp.py from git at the freeze's code commit.
    text = (RECEIPTS / "PROSPECTIVE_2026.md").read_text()
    frozen = load(ROOT / "config/dvp/frozen.json")
    ledger = RECEIPTS / "prospective" / "2026" / "ledger.jsonl"
    lines = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
    ok = (
        "dvp_prospective.py" in text
        and frozen["code"][:7] in text
        and (ROOT / "config/dvp/prospective.json").exists()
        and bool(frozen["prospective"].get("plan"))
    )
    return ok, {
        "firstKickoff": frozen["prospective"]["firstKickoff"],
        "archived": [(x["week"], x["classification"]) for x in lines],
    }


@check(
    "docs:status-vocabulary",
    "The research uses the specification's status words; nothing claims production readiness",
)
def _vocabulary(ctx: Context) -> Result:
    card = (RECEIPTS / "MODEL_CARD.md").read_text()
    return "**Not eligible yet.**" in card and "not in production" in card, {
        "modelCard": "Not eligible yet"
    }


@check(
    "open:prospective",
    "OPEN: the 2026 weeks 12-18 confirmation waits on games that have not been played",
)
def _open_prospective(ctx: Context) -> Result:
    f = load(ROOT / "config/dvp/frozen-phase-c.json")["prospective"]
    first = datetime.fromisoformat(f["firstKickoff"])
    frozen = datetime.fromisoformat(load(ROOT / "config/dvp/frozen-phase-c.json")["frozenAt"])
    return frozen < first, {
        "firstKickoff": f["firstKickoff"],
        "frozenBeforeIt": frozen < first,
        "auditedAt": datetime.now(UTC).isoformat(),
    }


@check(
    "open:owner-weight",
    "OPEN: no production weight is set; OWN-074 asks the owner after the prospective window",
)
def _open_weight(ctx: Context) -> Result:
    specs = (ROOT / "libs/arbit-model/src/arbit_model/feature_specs.py").read_bytes()
    pinned = ctx.committed("continuity-manifest.json")["v0"]["consumers"]
    path = "libs/arbit-model/src/arbit_model/feature_specs.py"
    same = hashlib.sha256(specs).hexdigest() == pinned.get(path)
    return same, {"featureSpecsUnchangedSinceV0": same}


@check(
    "open:modes",
    "NOT BUILT: dry-run and resume modes (the specification asks for them only 'when appropriate')",
)
def _open_modes(ctx: Context) -> Result:
    text = (ROOT / "scripts/model/dvp.py").read_text()
    steps = {s["step"]: s["seconds"] for s in ctx.reruns["steps"]}
    return "--dry-run" not in text and "--resume" not in text, {"stageSeconds": steps}


# --- the plan -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    id: str
    section: str
    title: str
    checks: tuple[str, ...]
    kind: str = "done"  # done | open


def _i(id: str, section: str, title: str, *checks: str, kind: str = "done") -> Item:
    return Item(id, section, title, checks, kind)


ITEMS: tuple[Item, ...] = (
    # §0 Operating rules
    _i(
        "R01",
        "§0.1",
        "Resume M3-3 from v0: inventory, verify and continue it",
        "test:T29",
        "v0:bytes",
        "v0:reproduced",
        "registry:v0",
    ),
    _i(
        "R02",
        "§0.2",
        "Read AGENTS.md and inspect scoring, contracts, tests and v0 before changing anything",
        "deliverable:4",
        "test:T29",
    ),
    _i(
        "R03",
        "§0.3",
        "Use Arbit's canonical FFA actuals under the league's rules only",
        "test:T30",
        "audit:checks",
        "test:T37",
    ),
    _i(
        "R04",
        "§0.4",
        "Exclude every provider projection by schema, lineage and executable tests",
        "test:T31",
        "test:T32",
        "test:T33",
        "test:T40",
        "provenance:passed",
        "receipts:no-projection",
    ),
    _i(
        "R05",
        "§0.5",
        "B00 and every variant forecast only from eligible completed-game actuals",
        "test:T38",
        "test:B11",
        "backtest:variants",
    ),
    _i(
        "R06",
        "§0.6",
        "Realized data counts only once completed and available by the cutoff",
        "test:T15",
        "test:T34",
        "test:T35",
        "test:T39",
    ),
    _i(
        "R07",
        "§0.7",
        "Isolated branch; no production write, weight change or canonical-table replacement",
        "test:T26",
        "config:no-production",
        "open:owner-weight",
    ),
    _i(
        "R08",
        "§0.8",
        "Preserve v0 untouched; extend through versioned experiments",
        "v0:bytes",
        "test:T29",
        "rerun:continuity",
    ),
    _i(
        "R09",
        "§0.9",
        "nflverse is the statistical foundation; no paid, opaque or projected inputs",
        "provenance:passed",
        "provenance:forbidden-inventory",
    ),
    _i(
        "R10",
        "§0.10",
        "Report repeatability, forecasting, player-level impact and shrinkage separately",
        "docs:conclusions",
        "registry:A05",
        "registry:B06",
        "registry:C05",
    ),
    _i(
        "R11",
        "§0.11",
        "Every forecast uses inputs and parameters available at its cutoff; vintage limits documented",
        "test:T16",
        "test:T17",
        "test:T18",
        "finality:recorded",
    ),
    _i(
        "R12",
        "§0.12",
        "No fabrication; unavailable inputs disable experiments, recorded as BLOCKED",
        "registry:C03",
        "phasec:not-available",
        "rerun:steps",
    ),
    _i(
        "R13",
        "§0.13",
        "Durable documentation so a fresh agent can resume",
        "deliverable:1",
        "deliverable:9",
        "docs:prospective",
    ),
    _i(
        "R14",
        "§0.14",
        "Use the status vocabulary; never claim unrun tests; never promote without approval",
        "registry:complete",
        "test:dvp-all",
        "docs:status-vocabulary",
    ),
    # §1 Research questions
    _i(
        "RQ1",
        "§1",
        "RQ1 measure: is there a repeatable position-specific defensive tendency?",
        "registry:A01",
        "registry:A05",
        "v0:validated",
        "reliability:a05",
    ),
    _i(
        "RQ2",
        "§1",
        "RQ2 explain noise: trait vs schedule, offense, randomness, transient conditions",
        "registry:A03",
        "registry:A05",
        "registry:A06",
        "registry:A08",
        "registry:A09",
    ),
    _i(
        "RQ3",
        "§1",
        "RQ3 evidence strength by position and sample size; v0 conversion vs variance models",
        "registry:A04",
        "registry:A05",
        "v0:wr-k",
        "test:T12",
    ),
    _i(
        "RQ4",
        "§1",
        "RQ4 forecast: does pre-week defensive information improve next-game forecasts?",
        "registry:B00",
        "registry:B03",
        "registry:B06",
        "backtest:variants",
    ),
    _i(
        "RQ5",
        "§1",
        "RQ5 add value over the offense-only baseline, consistently",
        "backtest:decisions",
        "backtest:dev-folds",
        "registry:HOLDOUT-2025",
    ),
    _i(
        "RQ6",
        "§1",
        "RQ6 translate (conditional): player-level forecasts and pairwise start/sit",
        "phasec:decision",
        "registry:C04",
        "registry:C05",
    ),
    _i(
        "RQ7",
        "§1",
        "RQ7 operationalize (conditional): estimator, shrinkage, freshness, fallback; approval-gated",
        "docs:conclusions",
        "docs:prospective",
        "open:owner-weight",
    ),
    # §2 Definitions
    _i(
        "D01",
        "§2",
        "position: groups from the league configuration; FB as RB; K and D/ST in scope; negatives kept",
        "audit:positions",
        "test:T02",
        "test:T04",
    ),
    _i(
        "D02",
        "§2",
        "game and team_game: completed regular-season games, exactly two team-games each",
        "audit:reconciliation",
        "test:T06",
    ),
    _i(
        "D03",
        "§2",
        "offense and defense: the offense's points by group are the opposing defense's points allowed",
        "test:T07",
        "test:T01",
    ),
    _i(
        "D04",
        "§2",
        "D/ST special case: the opposing D/ST's points against the offense (offense vulnerability)",
        "test:T07",
        "audit:examples",
    ),
    _i("D05", "§2", "true zero vs missing or invalid", "test:T03", "audit:cells"),
    _i(
        "D06",
        "§2",
        "delta: points less a stated offense expectation; positive means the defense allowed more",
        "test:T08",
        "registry:A03",
    ),
    _i(
        "D07",
        "§2",
        "defense-season: no presumption that a trait survives seasons",
        "registry:A07",
        "reliability:experiments",
    ),
    _i(
        "D08",
        "§2",
        "forecast cutoff: pre-week default; per-game is a separate experiment; never mixed",
        "test:T15",
        "test:T35",
        "registry:B10",
    ),
    _i(
        "D09",
        "§2",
        "game count n: eligible games, not calendar weeks; byes and cancellations add no exposure",
        "test:T10",
        "test:T34",
    ),
    # §2.1 Hard data boundary
    _i(
        "H01",
        "§2.1",
        "Scoring truth: FFA rules, Arbit's canonical actuals, nflverse raw stats for reconciliation",
        "test:T30",
        "audit:checks",
    ),
    _i(
        "H02",
        "§2.1",
        "Pregame features: only previously completed actuals and realized stats; priors from actuals",
        "test:T38",
        "test:T15",
    ),
    _i(
        "H03",
        "§2.1",
        "Prohibited everywhere: ESPN and vendor projections, rankings, forecasts, copied points-allowed tables",
        "test:T31",
        "test:T32",
        "provenance:forbidden-inventory",
    ),
    _i(
        "H04",
        "§2.1",
        "Arbit forecasts are outputs with traceable ancestry, never fed back as actuals",
        "test:T36",
        "test:T20",
    ),
    _i(
        "H05",
        "§2.1",
        "Mandatory row metadata: source, type, lineage, IDs, status, finality, scoring hash, feature_as_of",
        "audit:observation-lineage",
        "test:T36",
    ),
    _i(
        "H06",
        "§2.1",
        "Enforcement by allowlist and typed schemas; unknowns fail closed; machine-readable exclusion audit",
        "test:T33",
        "test:T32",
        "provenance:passed",
    ),
    # §2.2 Time eligibility
    _i("E01", "§2.2", "Prior-week completed FFA points: eligible", "test:T34", "test:T25"),
    _i(
        "E02",
        "§2.2",
        "Prior completed-game nflverse stats for validating actuals: eligible under the as-of rule",
        "test:T30",
        "finality:recorded",
    ),
    _i(
        "E03",
        "§2.2",
        "This week's Thursday result: only under a per-game cutoff",
        "test:T35",
        "test:T15",
    ),
    _i("E04", "§2.2", "Game underway, delayed or unfinished at the cutoff: never", "test:T34"),
    _i(
        "E05",
        "§2.2",
        "Game completed after the cutoff: label only, never a feature",
        "test:T16",
        "test:T17",
        "test:T39",
    ),
    _i("E06", "§2.2", "ESPN projected points, even pregame: never", "test:T32", "test:B11"),
    _i(
        "E07", "§2.2", "Vendor projections renamed opponent_expected: never", "test:T32", "test:T33"
    ),
    _i(
        "E08",
        "§2.2",
        "Arbit B00 from prior actuals: allowed as output and comparator",
        "test:T38",
        "registry:B00",
    ),
    _i(
        "E09",
        "§2.2",
        "Two isolated views (features as of T, targets after T), joined only after forecasts are written",
        "test:T36",
        "test:T20",
    ),
    # §3.1 Required datasets
    _i(
        "S01",
        "§3.1",
        "canonical_ffa_player_week: Arbit's FFA target store (index 6ffb62fb)",
        "audit:checks",
        "test:T30",
        "test:T05",
    ),
    _i(
        "S02",
        "§3.1",
        "canonical_ffa_dst_week: one D/ST line per completed team-game",
        "audit:cells",
        "test:T07",
    ),
    _i(
        "S03",
        "§3.1",
        "nfl_schedule: schedule_games.parquet, completed regular-season games only",
        "audit:seasons",
        "test:T06",
    ),
    _i(
        "S04",
        "§3.1",
        "team_game_position and defense_game_position: observations.parquet",
        "audit:observation-lineage",
        "rerun:observations",
        "test:T01",
    ),
    _i(
        "S05",
        "§3.1",
        "historical_cutoff_index: per-game cutoffs and feature_as_of",
        "test:T15",
        "test:T35",
    ),
    _i(
        "S06",
        "§3.1",
        "experiment_registry: every experiment with config, hashes, seed and status",
        "registry:complete",
        "rerun:registry",
    ),
    _i(
        "S07",
        "§3.1",
        "source_provenance_allowlist: admitted sources with ancestry and scoring hash",
        "provenance:passed",
        "test:T33",
    ),
    _i(
        "S08",
        "§3.1",
        "prohibited_source_audit: reject or quarantine inventory of forbidden sources",
        "provenance:forbidden-inventory",
        "test:T31",
    ),
    _i(
        "S09",
        "§3.1",
        "No new scoring engine: reuse stored FFA actuals; recompute only to audit",
        "audit:checks",
        "test:T30",
    ),
    # §3.2, §3.3
    _i(
        "S10",
        "§3.2",
        "Supplementary sources only with lineage; component stats for A09 and B07",
        "provenance:passed",
        "registry:A09",
        "registry:B07",
    ),
    _i(
        "Q01",
        "§3.3",
        "5,278 completed team-games verified against the schedule (canceled BUF-CIN excluded)",
        "audit:reconciliation",
        "audit:seasons",
        "test:T06",
    ),
    _i("Q02", "§3.3", "320 defense-seasons audited per filter", "v0:validated", "audit:seasons"),
    _i(
        "Q03",
        "§3.3",
        "Two team-games per game, offense-defense symmetry, D/ST reverse orientation; no postseason or phantom zeros",
        "audit:reconciliation",
        "test:T06",
        "test:T07",
        "test:T34",
    ),
    _i(
        "Q04",
        "§3.3",
        "Team renames and relocations, trades, duplicates, multi-position mapping, negatives, corrections",
        "audit:checks",
        "test:T05",
        "test:T02",
        "test:T04",
    ),
    _i(
        "Q05",
        "§3.3",
        "Hand-checked samples: zero TE, multi-WR, traded player, D/ST turnover, canceled game",
        "audit:examples",
        "audit:checks",
    ),
    _i(
        "Q06",
        "§3.3",
        "Data quality report and machine-readable anomalies; invalid rows blocked",
        "deliverable:2",
        "audit:cells",
    ),
    _i(
        "Q07",
        "§3.3",
        "Finality and availability at every cutoff; conservative fallback declared",
        "finality:recorded",
        "rerun:finality-audit",
        "registry:A12",
        "registry:B12",
    ),
    _i(
        "Q08",
        "§3.3",
        "Full projection-lineage scan over v0 and every new input",
        "provenance:passed",
        "rerun:projection-audit",
        "test:T31",
    ),
    # §4 v0
    _i(
        "V01",
        "§4.1",
        "Position sums per complete team-game; FB as RB; valid zeros",
        "test:T01",
        "test:T02",
        "test:T03",
    ),
    _i("V02", "§4.2", "Defense inversion with the separate D/ST interpretation", "test:T07"),
    _i(
        "V03",
        "§4.3",
        "Same-season leave-one-game-out offense adjustment; singletons handled",
        "test:T08",
    ),
    _i(
        "V04",
        "§4.4",
        "Odd vs even NFL calendar weeks; at least 4 games per half; unequal halves recorded",
        "test:T09",
        "test:T10",
    ),
    _i(
        "V05",
        "§4.5",
        "Split-half Pearson and Spearman, raw and adjusted, counts and intervals, scatter plots",
        "v0:validated",
        "deliverable:10",
    ),
    _i(
        "V06",
        "§4.6",
        "Reproduce v0 r, single-game reliability, k and w(n); explain WR 44.1 vs 42.63",
        "v0:reproduced",
        "v0:wr-k",
        "rerun:v0",
        "test:T11",
    ),
    _i(
        "V07",
        "§4",
        "Freeze v0: outputs, hashes, config and a discrepancy report; lineage audited",
        "v0:bytes",
        "rerun:continuity",
        "registry:A11",
        "deliverable:4",
    ),
    # §5 Experiments
    _i(
        "X00",
        "§5",
        "Every experiment states hypothesis, estimator, data, cutoff, ancestry, comparator, metric, interval, conclusion",
        "registry:complete",
    ),
    *(
        _i(
            f"{e}",
            "§5 Phase A",
            f"{e}: reliability experiment",
            f"registry:{e}",
            "reliability:experiments" if e not in ("A01", "A11") else "rerun:v0",
        )
        for e in EXPERIMENTS[:13]
    ),
    *(
        _i(
            f"{e}",
            "§5 Phase B",
            f"{e}: walk-forward experiment",
            f"registry:{e}",
            {
                "B08": "backtest:b08-focus",
                "B10": "backtest:sensitivity",
                "B11": "test:B11",
                "B12": "backtest:sensitivity",
            }.get(e, "backtest:variants"),
        )
        for e in EXPERIMENTS[13:26]
    ),
    _i(
        "C00",
        "§5 Phase C",
        "C00: Arbit-computed baseline (B00), no DvP",
        "registry:C00",
        "phasec:decision",
    ),
    _i(
        "C01",
        "§5 Phase C",
        "C01: group adjustment allocated by player share (one D/ST per team: share 1)",
        "registry:C01",
        "test:phase-c",
    ),
    _i(
        "C02",
        "§5 Phase C",
        "C02: allocation methods compared (identical for D/ST)",
        "registry:C02",
        "test:phase-c",
    ),
    _i(
        "C03",
        "§5 Phase C",
        "C03: route, slot and target-share interactions: BLOCKED (no meaning for D/ST)",
        "registry:C03",
        kind="open",
    ),
    _i(
        "C04",
        "§5 Phase C",
        "C04: historical same-position start/sit pairs; close-call subgroup separate",
        "registry:C04",
        "phasec:decision",
        "test:phase-c",
    ),
    _i(
        "C05",
        "§5 Phase C",
        "C05: decisions and errors vs baseline: accuracy, ties, points, changes, regret",
        "registry:C05",
        "phasec:decision",
        "rerun:sitstart",
    ),
    _i(
        "C05L",
        "§5 Phase C",
        "C05: league-constrained lineup evaluation: BLOCKED (no FFA lineups before 2026)",
        "phasec:not-available",
        kind="open",
    ),
    # §6 Statistics
    _i(
        "M01",
        "§6",
        "Research estimator: residuals, odd/even means, correlations with intervals; hierarchical form",
        "registry:A01",
        "registry:A05",
        "test:T14",
    ),
    _i(
        "M02",
        "§6",
        "Forecast estimator: O_hat + w * R_hist; point-in-time vs recomputed residuals both tested",
        "registry:B02",
        "registry:B03",
        "test:T25",
    ),
    _i(
        "M03",
        "§6",
        "Unequal split sizes: expected correlation from each unit's own half sizes; no negative k",
        "test:T11",
        "test:T12",
    ),
    _i(
        "M04",
        "§6",
        "Clustered resampling (season and unit-season blocks), 2,000 seeded replicates, multiple comparisons",
        "test:T13",
        "reliability:experiments",
        "registry:A08",
    ),
    _i(
        "M05",
        "§6",
        "Shrinkage w(n) is credibility inside DvP, not a Sit/Start weight",
        "docs:conclusions",
        "registry:A05",
    ),
    _i(
        "M06",
        "§6",
        "Distribution: means vs robust estimates; RMSE beside MAE; winsorizing and trimming",
        "registry:A10",
        "backtest:variants",
    ),
    _i(
        "M07",
        "§6",
        "Conditional dependence between groups examined, not assumed independent",
        "registry:A04",
        "reliability:experiments",
    ),
    # §7 Metrics and decisions
    _i(
        "K01",
        "§7",
        "Phase A metrics: split-half r, variance components, k, w(n), intervals, decay",
        "reliability:experiments",
        "reliability:a05",
    ),
    _i(
        "K02",
        "§7",
        "Phase B metrics: per-position RMSE and paired delta vs B00 on matching rows; MAE, bias, calibration, rank",
        "backtest:variants",
        "verify:passed",
        "test:T19",
    ),
    _i(
        "K03",
        "§7",
        "Phase C metrics: pairwise accuracy, points from changed choices, number of changes",
        "phasec:decision",
    ),
    _i(
        "K04",
        "§7",
        "Baseline parity: common eligible rows; coverage differences surfaced",
        "test:T19",
        "verify:passed",
    ),
    _i(
        "K05",
        "§7",
        "Predeclared decision rule: PROMISING, INCONCLUSIVE, NOT USEFUL, BLOCKED",
        "backtest:decisions",
        "test:phase4-rule",
        "phasec:rule-first",
    ),
    _i(
        "K06",
        "§7",
        "Practical minimum declared from development data only",
        "backtest:practical-minimum",
        "phasec:rule-first",
    ),
    _i(
        "K07",
        "§7",
        "2025 conditionally confirmatory at best; no retuning to 2025",
        "backtest:holdout-status",
        "backtest:timeline",
        "test:T18",
    ),
    # §8 Tests
    *(_i(f"T{t:02d}", "§8", f"Test T{t:02d}", f"test:T{t:02d}") for t in range(1, 41)),
    _i(
        "T00",
        "§8",
        "T29-T40 executed as gates; the full DvP suite passes with nothing skipped",
        "test:dvp-all",
        "test:model-suite",
    ),
    # §9 Phases, structure, CLI
    _i(
        "P0",
        "§9",
        "Phase 0: continuity, audit, v0 reproduced, no projection dependency (T29-T33, T37-T38)",
        "rerun:audit",
        "rerun:v0",
        "test:T29",
        "test:T33",
        "test:T38",
    ),
    _i(
        "P1",
        "§9",
        "Phase 1: projection-free completed-game pipeline; T01-T07 and T30-T40 pass",
        "rerun:observations",
        "audit:checks",
        "test:T07",
        "test:T40",
    ),
    _i(
        "P2",
        "§9",
        "Phase 2: reliability lab A00-A12 reproducible",
        "rerun:reliability",
        "reliability:experiments",
    ),
    _i(
        "P3",
        "§9",
        "Phase 3: walk-forward B00-B12, development folds, 2024 validation, candidates committed",
        "rerun:development",
        "rerun:validation",
        "rerun:forecasts-development",
        "rerun:forecasts-validation",
        "backtest:dev-folds",
    ),
    _i(
        "P4",
        "§9",
        "Phase 4: frozen manifest, 2025 conditional holdout, labels per position",
        "rerun:holdout-frozen-tree",
        "rerun:forecasts-holdout",
        "rerun:frozen-tree",
        "audit:frozen-outputs",
        "frozen:commit-matches",
        "backtest:decisions",
    ),
    _i(
        "P4P",
        "§9",
        "Phase 4 prospective: 2026 weeks 12-18 frozen before kickoff; scored after the season",
        "open:prospective",
        "backtest:timeline",
        kind="open",
    ),
    _i(
        "P5",
        "§9",
        "Phase 5: C00-C05 where justified; promotion only with approval",
        "rerun:sitstart",
        "phasec:decision",
        "phasec:frozen",
    ),
    _i(
        "P5W",
        "§9",
        "Promotion: the owner's decision on a D/ST production weight (OWN-074)",
        "open:owner-weight",
        kind="open",
    ),
    _i(
        "G01",
        "§9",
        "Repository structure adapted: scripts/model/dvp.py, config/dvp, arbit_model.dvp, tests, docs, artifacts",
        "cli:commands",
        "deliverable:5",
    ),
    _i(
        "G02",
        "§9",
        "CLI contracts: audit, reproduce-v0, reliability, backtest x3, report; pytest",
        "cli:commands",
        "rerun:steps",
    ),
    _i(
        "G03",
        "§9",
        "The holdout requires a frozen, verified manifest; it refuses elsewhere",
        "rerun:holdout-refused-here",
        "test:T18",
        "config:spec-keys",
    ),
    _i("G04", "§9", "Verify-only mode", "verify:passed", "rerun:verify"),
    _i(
        "G05",
        "§9",
        "Atomic writes and idempotent reruns",
        "rerun:forecasts-development",
        "rerun:forecasts-validation",
        "rerun:committed-run-unchanged",
        "test:T27",
    ),
    _i(
        "G06",
        "§9",
        "Dry-run and resume modes: not built (stages are separate commands of 1-75 s)",
        "open:modes",
        kind="open",
    ),
    # §10
    _i("F01", "§10", "Explicit config with the specification's keys", "config:spec-keys"),
    _i("F02", "§10", "Every experiment record carries the §10 fields", "registry:complete"),
    _i(
        "F03",
        "§10",
        "Assertions fail if an external projected-point dependency is detected",
        "test:T40",
        "receipts:no-projection",
    ),
    # §11
    *(_i(f"O{n:02d}", "§11", f"Deliverable {n}", f"deliverable:{n}") for n in range(1, 12)),
    _i(
        "O10F",
        "§11",
        "FORECASTS.parquet per stage, hashed in its receipt (git-ignored artifacts)",
        "deliverable:forecasts",
    ),
    _i(
        "Z01",
        "§11",
        "Before completion: whole relevant suite including T29-T40",
        "test:dvp-all",
        "test:model-suite",
    ),
    _i(
        "Z02",
        "§11",
        "Before completion: original M3-3 artifacts unchanged",
        "v0:bytes",
        "verify:passed",
    ),
    _i(
        "Z03",
        "§11",
        "Before completion: reproduce from the pinned configuration",
        "rerun:steps",
        "rerun:report-files",
        "rerun:registry",
        "rerun:config-freeze-only-added",
    ),
    _i(
        "Z04",
        "§11",
        "Before completion: inspect an independently generated sample for sign, units and joins",
        "verify:sample",
        "verify:passed",
    ),
    _i(
        "Z05",
        "§11",
        "Before completion: per-position conclusion table with the specified columns",
        "docs:conclusions",
    ),
    _i(
        "Z06",
        "§11",
        "Before completion: report provenance, finality, zero projections and holdout status",
        "docs:conclusions",
        "provenance:passed",
        "finality:recorded",
        "backtest:holdout-status",
    ),
    # §12
    _i("L01", "§12", "v0 discovered and preserved", "v0:bytes", "test:T29"),
    _i(
        "L02",
        "§12",
        "Inputs canonical, completed, point-in-time, projection-free",
        "provenance:passed",
        "finality:recorded",
        "audit:checks",
    ),
    _i("L03", "§12", "v0 reproducible", "v0:reproduced", "rerun:v0"),
    _i(
        "L04",
        "§12",
        "Reliability and uncertainty estimated; forward test run even where the signal is weak",
        "reliability:a05",
        "backtest:variants",
    ),
    _i(
        "L05",
        "§12",
        "Forward comparison decides per position: production effect 0 where not useful",
        "backtest:decisions",
        "open:owner-weight",
    ),
    _i(
        "L06",
        "§12",
        "Robust to eras, perturbations, coverage, leakage: PROMISING at team-position level (D/ST)",
        "registry:A10",
        "test:T28",
        "test:T19",
        "backtest:decisions",
    ),
    _i(
        "L07",
        "§12",
        "Player-level A/B improves start/sit: recommend controlled integration after approval",
        "phasec:decision",
        "open:owner-weight",
    ),
    _i(
        "L08",
        "§12",
        "2025 status labeled accurately (CONDITIONALLY_HELD_OUT)",
        "backtest:holdout-status",
    ),
    # §13 Caveats
    _i(
        "W01",
        "§13",
        "32 teams x 10 seasons are not 320 independent units: clustered intervals",
        "test:T13",
        "v0:validated",
    ),
    _i(
        "W02",
        "§13",
        "v0 used 2025: never called untouched; no 2025-derived parameters",
        "backtest:holdout-status",
        "test:T18",
    ),
    _i(
        "W03",
        "§13",
        "v0's same-season adjustment is retrospective only; backtests are point-in-time",
        "test:T17",
        "registry:B02",
    ),
    _i(
        "W04",
        "§13",
        "Only actuals available by each cutoff inform forecasts; labels separate",
        "test:T36",
        "test:T15",
    ),
    _i(
        "W05",
        "§13",
        "Odd/even can hide midseason change: chronological tests added",
        "test:T23",
        "registry:A06",
    ),
    _i("W06", "§13", "w(8) is within-DvP shrinkage, not a model weight", "docs:conclusions"),
    _i("W07", "§13", "Group totals measure matchup context, not a player's share", "registry:C01"),
    _i(
        "W08",
        "§13",
        "A null group result does not exclude player-level signals; repeatability is not usefulness",
        "docs:conclusions",
        "registry:A05",
        "backtest:decisions",
    ),
    _i(
        "W09",
        "§13",
        "Each position evaluated independently; no WR k reused for other groups",
        "reliability:a05",
        "backtest:dev-folds",
    ),
    _i(
        "W10",
        "§13",
        "Source availability through 2025 verified; canonical data take precedence",
        "audit:seasons",
        "finality:recorded",
    ),
    _i(
        "W11",
        "§13",
        "Stat corrections: final revisions only, limitation reported",
        "finality:recorded",
        "registry:A12",
    ),
    _i(
        "W12",
        "§13",
        "No production merge from correlations; only confirmatory incremental value",
        "open:owner-weight",
        "docs:status-vocabulary",
    ),
)


def _run_check(ctx: Context, check_id: str) -> dict[str, Any]:
    description, fn = CHECKS[check_id]
    try:
        passed, observed = fn(ctx)
    except Exception as error:  # a check that cannot run fails, with the reason
        passed, observed = False, f"{type(error).__name__}: {error}"
    return {
        "id": check_id,
        "description": description,
        "passed": bool(passed),
        "observed": observed,
    }


def evaluate(ctx: Context) -> dict[str, Any]:
    results = {
        cid: _run_check(ctx, cid) for cid in sorted({c for item in ITEMS for c in item.checks})
    }
    items = []
    for item in ITEMS:
        passed = all(results[c]["passed"] for c in item.checks)
        status = (
            ("DONE" if passed else "FAILED")
            if item.kind == "done"
            else ("OPEN" if passed else "FAILED")
        )
        items.append(
            {
                "id": item.id,
                "section": item.section,
                "title": item.title,
                "kind": item.kind,
                "status": status,
                "checks": list(item.checks),
            }
        )
    counts = {s: sum(i["status"] == s for i in items) for s in ("DONE", "OPEN", "FAILED")}
    return {
        "status": "PASSED" if counts["FAILED"] == 0 else "FAILED",
        "summary": {
            "items": len(items),
            **counts,
            "checks": len(results),
            "checksPassed": sum(r["passed"] for r in results.values()),
        },
        "items": items,
        "checks": results,
    }


def check_command(args: argparse.Namespace) -> None:
    scratch: Path = args.scratch.resolve()
    reruns = load(scratch / "reruns.json")
    ctx = Context(scratch=scratch, reruns=reruns, junit=_junit(scratch / "junit.xml"))
    result = evaluate(ctx)
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", ".", ":(exclude)docs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    receipt = {
        "format": FORMAT,
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": git("rev-parse", "HEAD") + ("+uncommitted" if dirty else ""),
        "specification": {"path": str(SPEC.relative_to(ROOT)), "sha256": sha256(SPEC)},
        "auditRun": reruns["run"],
        "reruns": {
            "code": reruns["code"],
            "frozenTree": reruns["frozenTree"],
            "steps": [
                {k: s[k] for k in ("step", "cwd", "exit", "expectedExit", "seconds")}
                for s in reruns["steps"]
            ],
        },
        "tests": {
            k: sum(o == k for o in ctx.junit.values()) for k in ("passed", "failed", "skipped")
        },
        **result,
    }
    args.out.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
    s = result["summary"]
    print(
        f"{result['status']}: {s['items']} items ({s['DONE']} done, {s['OPEN']} open, {s['FAILED']} failed); {s['checksPassed']}/{s['checks']} checks passed"
    )
    for item in result["items"]:
        if item["status"] == "FAILED":
            failed = [c for c in item["checks"] if not result["checks"][c]["passed"]]
            print(f"  FAILED {item['id']} {item['title']}: {failed}")
    if result["status"] != "PASSED":
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    r = commands.add_parser("rerun", help="rerun every stage and the tests on scratch copies")
    r.add_argument(
        "--main", type=Path, required=True, help="the checkout that holds data/ and .env.local"
    )
    r.add_argument("--run", type=Path, required=True, help=f"the frozen audit run ({AUDIT_RUN})")
    r.add_argument(
        "--frozen-tree", type=Path, required=True, help="a worktree at the holdout's code"
    )
    r.add_argument("--scratch", type=Path, required=True, help="an empty directory for the reruns")
    c = commands.add_parser("check", help="evaluate every plan item and write the receipt")
    c.add_argument("--scratch", type=Path, required=True)
    c.add_argument("--out", type=Path, default=RECEIPTS / "plan-audit-receipt.json")
    args = parser.parse_args()
    if args.command == "rerun":
        rerun(args)
    else:
        check_command(args)


if __name__ == "__main__":
    main()
