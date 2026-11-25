"""Remediation 7: the final directive's requirements, semantic checks and negative controls.

Loaded by scripts/model/dvp_plan_audit.py, which it extends (owner final directive §12): it
registers checks into the same registry, adds items to the same catalog, and defines the negative
controls that prove the audit detects incomplete or incorrect work. Checks here verify behaviour:
they rerun experiments from pinned inputs and compare receipts, call the real functions on
constructed cases, and inspect the live prospective archive and timer. None trusts a flag alone.
"""

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

Result = tuple[bool, Any]
EVIDENCE_PREFIXES = ("open:", "na:", "evidence:", "owner:")
CLAIMABLE = ("HELD", "FREE_AGENT")


def _harness(audit: Any) -> Any:
    spec = importlib.util.spec_from_file_location(
        "dvp_prospective_audit", audit.ROOT / "scripts/model/dvp_prospective.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _main(ctx: Any) -> Path:
    return Path(ctx.reruns.get("mainPath") or Path(ctx.reruns["runPath"]).parents[2])


def _receipt(ctx: Any, name: str) -> Any:
    path = ctx.scratch / "receipts" / "directive" / name
    return json.loads(path.read_text())


def _present(obj: Any, path: str) -> bool:
    for part in [p for p in path.split("/") if p]:
        if not isinstance(obj, dict) or part not in obj:
            return False
        obj = obj[part]
    return True


def _compare(
    audit: Any, committed: Any, rerun: Any, allowed: set[str], *, additions: bool = False
) -> Result:
    """Rerun against committed: only the allowed fields may differ. With `additions`, fields the
    rerun adds (written by code newer than the committed receipt) are reported but allowed; a
    removed or changed committed value is never allowed."""
    differ, unexpected = audit.unexpected_differences(committed, rerun, allowed)
    added = [p for p in unexpected if additions and not _present(committed, p)]
    unexpected = [p for p in unexpected if p not in added]
    return not unexpected, {
        "differ": len(differ),
        "added": len(added),
        "unexpected": unexpected[:12],
    }


def _parquet_hashes() -> set[str]:
    """Parquet byte hashes may differ (row order of parallel group-bys); content is compared."""
    return {f"/stages/{s}/forecastsSha256" for s in ("development", "validation", "holdout")}


def register(audit: Any) -> tuple[Any, ...]:
    """Register the directive's checks and return its items."""
    check: Callable[[str, str], Callable[[Callable[[Any], Result]], Callable[[Any], Result]]]
    check = audit.check
    _i: Callable[..., Any] = audit._i

    # --- reruns from pinned inputs --------------------------------------------------------------
    @check("rerun:explore-v2", "Exploratory v2 rerun from scratch equals its committed receipt")
    def _explore_v2(ctx: Any) -> Result:
        return _compare(
            audit,
            audit.load(audit.RECEIPTS / "explore-v2.json"),
            _receipt(ctx, "explore-v2.json"),
            {"/code", "/generatedAt", "/run", *_parquet_hashes()},
            additions=True,
        )

    @check("rerun:explore-v3", "Exploratory v3 (opportunity) rerun equals its committed receipt")
    def _explore_v3(ctx: Any) -> Result:
        return _compare(
            audit,
            audit.load(audit.RECEIPTS / "explore-v3.json"),
            _receipt(ctx, "explore-v3.json"),
            {"/code", "/generatedAt", "/run", *_parquet_hashes()},
            additions=True,
        )

    @check(
        "rerun:league-v2",
        "The corrected C05L-2026-EXP v2, rerun from the pinned league inputs, equals its receipt",
    )
    def _league_v2(ctx: Any) -> Result:
        return _compare(
            audit,
            audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json"),
            _receipt(ctx, "league-2026-exploratory-v2.json"),
            {"/code", "/generatedAt"},
        )

    @check("rerun:thresholds", "AUD-07's threshold analysis rerun equals its receipt")
    def _thresholds(ctx: Any) -> Result:
        return _compare(
            audit,
            audit.load(audit.RECEIPTS / "threshold-sensitivity-v1.json"),
            _receipt(ctx, "threshold-sensitivity-v1.json"),
            {"/code", "/generatedAt"},
        )

    @check(
        "rerun:simulation-sample",
        "A deterministic sample of every AUD-06 experiment and scenario reruns identically",
    )
    def _sim_sample(ctx: Any) -> Result:
        raw = _main(ctx) / "artifacts/dvp/simulation-v1"
        sample = ctx.scratch / "sim"
        compared = mismatched = 0
        bad = []
        for path in sorted(sample.glob("*/*.jsonl")):
            stored = {
                json.loads(line)["rep"]: json.loads(line)
                for line in (raw / path.parent.name / path.name).read_text().splitlines()
                if line.strip()
            }
            for line in path.read_text().splitlines():
                rerun = json.loads(line)
                original = stored[rerun["rep"]]
                compared += 1
                if _without_seconds(rerun) != _without_seconds(original):
                    mismatched += 1
                    bad.append(f"{path.parent.name}/{path.stem}/{rerun['rep']}")
        return compared > 0 and mismatched == 0, {
            "compared": compared,
            "mismatched": mismatched,
            "examples": bad[:5],
        }

    @check(
        "rerun:simulation-summary",
        "The AUD-06 receipt regenerated from the raw results equals the committed receipt",
    )
    def _sim_summary(ctx: Any) -> Result:
        return _compare(
            audit,
            audit.load(audit.RECEIPTS / "simulation-v1.json"),
            _receipt(ctx, "simulation-v1.json"),
            {"/code", "/generatedAt"},
        )

    # --- prospective operations (AUD-01a-d, PB-AUD-07, DEC-02/03) ------------------------------
    @check(
        "aud01a:evidence",
        "Every prospective archive is intact and has a verified external commitment before its cutoff",
    )
    def _evidence(ctx: Any) -> Result:
        log = (ctx.scratch / "logs" / "prospective-verify.log").read_text().strip().splitlines()
        verdict = json.loads(log[-1])
        root = _main(ctx) / "artifacts/dvp/prospective/2026"
        ledger = [json.loads(x) for x in (root / "ledger.jsonl").read_text().splitlines() if x]
        pubs = [json.loads(x) for x in (root / "publications.jsonl").read_text().splitlines() if x]
        branch = {
            p["ledgerEntrySha256"]
            for p in pubs
            if p.get("kind") == "github-branch" and p.get("verified") and p.get("beforeCutoff")
        }
        prospective = [e for e in ledger if e["classification"] == "PROSPECTIVE"]
        missing = [e["week"] for e in prospective if e["entrySha256"] not in branch]
        ok = not verdict["problems"] and not verdict["withoutPreCutoffCommitment"] and not missing
        return ok and bool(prospective), {
            "verify": verdict,
            "prospectiveWeeks": [e["week"] for e in prospective],
            "withoutBranchCommitment": missing,
        }

    @check(
        "aud01b:readiness",
        "Per-game readiness: week 12's archived inputs are ready at its forecast time; a game "
        "missing cells blocks",
    )
    def _readiness(ctx: Any) -> Result:
        from arbit_model.dvp import window

        inputs = _main(ctx) / "artifacts/dvp/prospective/2026/week-12"
        manifest = json.loads((inputs / "manifest.json").read_text())
        rows = pl.read_parquet(inputs / "inputs/observations-season.parquet")
        schedule = pl.read_parquet(inputs / "inputs/schedule-season.parquet")
        at = datetime.fromisoformat(manifest["generatedAt"])
        ready, detail = window.game_readiness(
            schedule, rows, 2026, 12, at, timedelta(days=4), at, at
        )
        a_game = rows.get_column("game_id")[0]
        broken = rows.filter(pl.col("game_id") != a_game)
        late = at  # the held file postdates the game: missing cells are an integrity failure
        blocked, detail_b = window.game_readiness(
            schedule, broken, 2026, 12, at, timedelta(days=4), late, late
        )
        ok = ready and not blocked and window.DATA_INTEGRITY_FAILURE in detail_b["blocking"]
        return ok, {
            "week12Ready": ready,
            "states": detail["states"],
            "brokenBlocking": list(detail_b["blocking"]),
        }

    @check(
        "aud01c:gate",
        "The completion gate: first-game-only, unfinished games, missing labels, a missed week, a "
        "retrospective for a missed week, timing and integrity failures and subsets never confirm",
    )
    def _gate(ctx: Any) -> Result:
        return _gate_cases()

    @check(
        "aud01d:archive",
        "Archive transaction: crashes at each step are recovered without regeneration; a "
        "concurrent run is refused",
    )
    def _archive(ctx: Any) -> Result:
        return _archive_cases(ctx.scratch)

    @check(
        "timer:operational",
        "The owner-authorized timer is enabled, bounded to the research window, and its last run "
        "succeeded within 13 hours",
    )
    def _timer(ctx: Any) -> Result:
        enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", "arbit-dvp-prospective.timer"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        unit = Path.home() / ".config/systemd/user/arbit-dvp-prospective.timer"
        calendar = [
            line for line in unit.read_text().splitlines() if line.startswith("OnCalendar=")
        ]
        bounded = all(re.search(r"20(26|27)-", c) and c.endswith("UTC") for c in calendar)
        status = json.loads((_main(ctx) / "artifacts/dvp/prospective/2026/status.json").read_text())
        age = datetime.now(UTC) - datetime.fromisoformat(status["run"])
        ok = (
            enabled == "enabled"
            and bounded
            and status["outcome"] == "OK"
            and age < timedelta(hours=13)
        )
        return ok, {
            "enabled": enabled,
            "calendar": calendar,
            "lastRun": status["run"],
            "lastOutcome": status["outcome"],
        }

    @check(
        "timer:retires",
        "The sweep disables the timer once every week is final and committed (DEC-02), and not before",
    )
    def _retires(ctx: Any) -> Result:
        return _retire_cases(audit, ctx.scratch)

    @check(
        "pb07:capture",
        "Decision-time league captures: chained, ESPN's observed availability for all 32 D/STs and "
        "every team; week 12's supplement recorded",
    )
    def _capture(ctx: Any) -> Result:
        from arbit_model.dvp import shadow

        root = _main(ctx) / "artifacts/dvp/prospective/2026"
        records = [json.loads(x) for x in (root / "captures.jsonl").read_text().splitlines() if x]
        problems = shadow.verify_ledger(records)
        for r in records:
            data = (root / r["file"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != r["sha256"]:
                problems.append(f"{r['file']} hash")
            capture = json.loads(data)
            states = set(capture["availability"].values())
            if capture["units"] != 32 or len(capture["teams"]) != 8:
                problems.append(f"{r['file']}: universe or teams")
            if not states <= {"OWNED", "FREE_AGENT", "WAIVERS", "UNKNOWN"}:
                problems.append(f"{r['file']}: states {states}")
        supplements = [
            json.loads(x) for x in (root / "supplements.jsonl").read_text().splitlines() if x
        ]
        return bool(records) and not problems and any(s["week"] == 12 for s in supplements), {
            "captures": len(records),
            "problems": problems,
            "supplements": [s["file"] for s in supplements],
        }

    @check(
        "dec:frozen-unchanged",
        "The frozen methods verify by hash, the original prospective declaration is unchanged, and "
        "the week-12 archive matches its ledger (DEC-03)",
    )
    def _frozen_unchanged(ctx: Any) -> Result:
        harness = _harness(audit)
        frozen = harness.load_frozen()  # raises on any mismatch
        amendment = audit.load(audit.ROOT / "config/dvp/prospective-amendment-1.json")
        same = (
            audit.sha256(audit.ROOT / "config/dvp/prospective.json")
            == amendment["amends"]["sha256"]
        )
        root = _main(ctx) / "artifacts/dvp/prospective/2026"
        entry = json.loads((root / "ledger.jsonl").read_text().splitlines()[0])
        intact = harness.files_match(root / entry["folder"], entry["files"])
        return frozen.verification["allMatch"] and same and intact, {
            "frozenFilesVerified": frozen.verification["filesVerified"],
            "originalDeclarationUnchanged": same,
            "week12ArchiveIntact": intact,
        }

    # --- Phase B corrections (PB-AUD-01..08) -----------------------------------------------------
    @check(
        "pb01:content",
        "Live content re-read: every stored transaction content-equal and located; lineups equal "
        "in their historical fields",
    )
    def _content(ctx: Any) -> Result:
        live = _receipt(ctx, "ffa-2026-inventory-content.json")
        tx = live["liveContent"]["transactions"]
        lineups = live["liveContent"]["lineups"]
        historical = [
            p
            for p, v in lineups.items()
            if v.get("fieldDifferences", {}).get("historicalLineupDiffers")
        ]
        ok = not tx["contentDiffers"] and not tx["storedNotLive"] and not historical
        return ok, {
            "contentEqual": tx["contentEqual"],
            "storedNotLive": len(tx["storedNotLive"]),
            "liveNotStored (new source records)": len(tx["liveNotStored"]),
            "lineupsWithHistoricalDifferences": historical,
        }

    @check(
        "pb02:fail-closed",
        "The ownership replay refuses an executed trade and a waiver without a processing time, "
        "and equals every archived snapshot",
    )
    def _fail_closed(ctx: Any) -> Result:
        from arbit_model import ffa_history as fh

        t0 = datetime(2026, 9, 1, tzinfo=UTC)
        trade = {
            "espn_id": "x",
            "type": "TRADE_ACCEPT",
            "status": "EXECUTED",
            "scoring_period": 3,
            "proposed_at": t0,
            "processed_at": t0,
            "items": [{"type": "TRADE", "player_id": "p", "from_team_id": "a", "to_team_id": "b"}],
        }
        waiver = trade | {
            "type": "WAIVER",
            "processed_at": None,
            "items": [{"type": "ADD", "player_id": "p", "to_team_id": "a"}],
        }
        refused = []
        for case in (trade, waiver):
            try:
                fh.moves([case])
            except fh.UnsupportedHistory:
                refused.append(case["type"])
        every = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")["ownership"][
            "everySnapshot"
        ]
        ok = refused == ["TRADE_ACCEPT", "WAIVER"] and every["disagree"] == 0 and every["agree"] > 0
        return ok, {
            "refused": refused,
            "snapshotsAgree": every["agree"],
            "disagree": every["disagree"],
        }

    @check(
        "pb03:availability",
        "Rule v2 passed its predeclared holdout test; cutoff classes are VERIFIED or RECONSTRUCTED",
    )
    def _availability(ctx: Any) -> Result:
        receipt = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")
        acceptance = receipt["availabilityValidation"]["acceptance"]
        holdout = receipt["availabilityValidation"]["ruleV2"]["holdout"]
        classes = {w: e["class"] for w, e in receipt["availabilityAtCutoff"].items()}
        consistent = acceptance["passed"] == (
            holdout["agreement"] >= 0.99 and holdout["falseClaimableRate"] <= 0.01
        )
        ok = (
            acceptance["passed"]
            and consistent
            and set(classes.values()) <= {"VERIFIED", "RECONSTRUCTED"}
        )
        return ok, {
            "holdout": {k: holdout[k] for k in ("agreement", "falseClaimableRate")},
            "classes": classes,
        }

    @check(
        "pb04:all-weeks",
        "The league bootstrap resamples every evaluated week, zero-change weeks included",
    )
    def _all_weeks(ctx: Any) -> Result:
        results = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")["results"]
        bad = {
            k: v.get("bootstrap")
            for k, v in results.items()
            if v.get("bootstrap", {}).get("method") != "all_weeks"
            or v["bootstrap"]["blocks"] != v["evaluatedWeeks"]
        }
        start = results["start"]
        ok = (
            not bad
            and set(start["zeroChangeWeeks"]) == {7, 8}
            and start["bootstrap"]["blocks"] == 11
        )
        return ok, {"bad": bad, "startZeroChangeWeeks": start["zeroChangeWeeks"]}

    @check(
        "pb05:feasibility",
        "Streaming recommendations carry feasibility classes and collisions for every decision",
    )
    def _feasibility(ctx: Any) -> Result:
        receipt = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")
        out = {}
        ok = True
        for kind, models in receipt["feasibility"].items():
            for model, counts in models.items():
                total = sum(counts.values())
                out[f"{kind}/{model}"] = total
                ok &= total == receipt["coverage"][kind]["decisions"]
        ok &= all(kind in receipt["collisions"] for kind in receipt["feasibility"])
        return ok, out

    @check(
        "pb06:eligible-options",
        "Every option of a claimable decision was held or a free agent at the cutoff; managers "
        "split into comparable and different-time sets",
    )
    def _eligible(ctx: Any) -> Result:
        receipt = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")
        wrong = [
            (r["week"], r["team"][:8], u)
            for r in receipt["decisions"]["streamClaimable"]
            for u, (state, _) in r["optionEvidence"].items()
            if state not in CLAIMABLE
        ]
        managers = receipt["managers"]
        split = (
            managers["strictlyComparable"].get("decisions", 0)
            + managers["differentDecisionTimeCount"]
        )
        return not wrong and split == receipt["coverage"]["start"]["decisions"], {
            "ineligibleOptions": wrong[:5],
            "managersSplit": split,
        }

    @check(
        "pb08:pinned",
        "The pinned league bundle matches its committed manifest file by file; the corrected run "
        "read no live database",
    )
    def _pinned(ctx: Any) -> Result:
        committed = audit.load(audit.ROOT / "docs/research/ffa-2026-league-inputs-v1.json")
        bundle = _main(ctx) / "artifacts/dvp/league-2026/inputs-v1"
        mismatched = [
            n
            for n, meta in committed["files"].items()
            if not (bundle / n).is_file() or audit.sha256(bundle / n) != meta["sha256"]
        ]
        manifest_ok = (bundle / "manifest.json").is_file() and audit.sha256(
            bundle / "manifest.json"
        ) == committed["manifestSha256"]
        receipt = audit.load(audit.RECEIPTS / "league-2026-exploratory-v2.json")
        offline = receipt["pinnedInputs"]["liveDatabaseRead"] is False
        return not mismatched and manifest_ok and offline, {
            "files": len(committed["files"]),
            "mismatched": mismatched,
            "liveDatabaseRead": not offline,
        }

    # --- AUD-06, AUD-07, eligibility, findings ---------------------------------------------------
    @check(
        "aud06:acceptance",
        "The simulation suite ran every declared scenario with no failed repetition; acceptance "
        "recorded as declared",
    )
    def _aud06(ctx: Any) -> Result:
        receipt = audit.load(audit.RECEIPTS / "simulation-v1.json")
        config = audit.load(audit.ROOT / "config/dvp/simulation-v1.json")
        e2 = set(config["experiments"]["E2"]["scenarios"])
        e1 = set(config["experiments"]["E1"]["scenarios"])
        failed = sum(
            v["failed"] for part in ("E1", "E2", "E3", "U") for v in receipt[part].values()
        )
        reps = all(v["reps"] == 300 for v in receipt["E2"].values())
        ok = e2 == set(receipt["E2"]) and e1 == set(receipt["E1"]) and failed == 0 and reps
        return ok, {
            "E2": sorted(receipt["E2"]),
            "failed": failed,
            "acceptance": list(receipt["acceptance"]),
        }

    @check(
        "aud07:frozen-thresholds",
        "The 1% grid row reproduces every frozen label; the frozen thresholds are unchanged",
    )
    def _aud07(ctx: Any) -> Result:
        receipt = audit.load(audit.RECEIPTS / "threshold-sensitivity-v1.json")
        holdout = audit.load(audit.RECEIPTS / "backtest-holdout.json")["decisions"]["positions"]
        grid = {p: v["byThreshold"]["0.0100"]["label"] for p, v in receipt["D2"]["phaseB"].items()}
        frozen_c = audit.load(audit.ROOT / "config/dvp/frozen-phase-c.json")[
            "practicalMinimumAccuracyPp"
        ]
        frozen_b = audit.load(audit.ROOT / "config/dvp/backtest.json")[
            "practical_minimum_relative_rmse"
        ]
        same = grid == {p: v["label"] for p, v in holdout.items()}
        return same and frozen_c == 1.8 and frozen_b == 0.01, {
            "grid1Percent": grid,
            "derivationPp": receipt["D1"]["original"]["impliedPp"],
        }

    @check(
        "elig:registry",
        "The research eligibility registry loads, classifies as directed, makes nothing "
        "production-eligible, and the gate refuses DvP features in production",
    )
    def _eligibility(ctx: Any) -> Result:
        from arbit_model import eligibility as el

        entries = el.load()
        refused = []
        for feature in ("b06", "opp_dvp_RB_adj_shrunk", "dvp_unregistered"):
            try:
                el.check_assembly([feature], purpose="production")
            except el.IneligibleFeature:
                refused.append(feature)
        ok = (
            not any(e.production_eligible for e in entries.values())
            and entries["M3-3.DST.B06"].classification == "PROMISING_HISTORICAL_CANDIDATE"
            and len(refused) == 3
        )
        return ok, {"entries": len(entries), "refusedInProduction": refused}

    @check(
        "findings:reconciled",
        "Every external finding has a disposition, reasoning, remediation and evidence, and is closed",
    )
    def _findings(ctx: Any) -> Result:
        register = audit.load(audit.RECEIPTS / "audit-findings.json")
        open_ = [
            f["id"]
            for f in register["findings"]
            if f["status"] not in ("RESOLVED_VERIFIED", "RESOLVED_PENDING_FUTURE_DATA")
        ]
        incomplete = [
            f["id"]
            for f in register["findings"]
            if f["disposition"] not in register["dispositions"]
            or not f.get("reasoning")
            or not f.get("evidence")
        ]
        return not open_ and not incomplete, {
            "findings": len(register["findings"]),
            "open": open_,
            "incomplete": incomplete,
        }

    @check(
        "code:no-projection",
        "No file in the DvP code scan imports a provider projection or a provider-league reader",
    )
    def _code(ctx: Any) -> Result:
        from arbit_model.dvp.provenance import scan_code

        dvp = _dvp_module(audit)
        findings = [f for p in dvp.SCANNED for f in scan_code(audit.ROOT / p)]
        return not findings, {"files": len(dvp.SCANNED), "findings": findings[:5]}

    @check(
        "na:c03-dst-only",
        "Evidence for C03 not applicable: Phase C ran for D/ST only, the one group past Phase B",
    )
    def _c03(ctx: Any) -> Result:
        sit = audit.load(audit.RECEIPTS / "sitstart.json")
        candidates = audit.load(audit.ROOT / "config/dvp/frozen-candidates.json")["positions"]
        past = sorted(p for p, v in candidates.items() if v["candidate"] != "b00")
        return sit.get("position") == "DST" and past == ["DST"], {
            "phaseCPosition": sit.get("position"),
            "groupsPastPhaseB": past,
        }

    @check(
        "g06:modes",
        "Modes where appropriate: verify-only commands exist; long runs resume without repeating work",
    )
    def _modes(ctx: Any) -> Result:
        log = (ctx.scratch / "logs" / "sim-resume.log").read_text()
        second = [json.loads(x) for x in log.splitlines() if x.startswith('{"experiment"')]
        resumed = len(second) >= 2 and second[-1]["jobs"] == 0
        dvp_cli = (audit.ROOT / "scripts/model/dvp.py").read_text()
        harness = (audit.ROOT / "scripts/model/dvp_prospective.py").read_text()
        verify = 'add_parser("verify"' in dvp_cli or "verify" in dvp_cli
        return resumed and verify and 'commands.add_parser("verify")' in harness, {
            "simulationResumed": resumed,
        }

    # --- items: the reconciled inventory of the final directive ---------------------------------
    return (
        _i(
            "AUD-01",
            "Final directive",
            "AUD-01: the 2026 confirmation is truly prospective (remediation 1)",
            "aud01c:gate",
            "aud01a:evidence",
            "dec:frozen-unchanged",
        ),
        _i(
            "AUD-01a",
            "Final directive",
            "AUD-01a: external archival evidence, published and verified before each cutoff",
            "aud01a:evidence",
        ),
        _i(
            "AUD-01b",
            "Final directive",
            "AUD-01b: data readiness established per game with stated causes",
            "aud01b:readiness",
        ),
        _i(
            "AUD-01c",
            "Final directive",
            "AUD-01c: the completion gate never confirms an incomplete window",
            "aud01c:gate",
        ),
        _i(
            "AUD-01d",
            "Final directive",
            "AUD-01d: archival transactions recover without regeneration",
            "aud01d:archive",
        ),
        _i(
            "AUD-02",
            "Final directive",
            "AUD-02: opportunity volume and efficiency (exploratory v3) reproduce",
            "rerun:explore-v3",
        ),
        _i(
            "AUD-03",
            "Final directive",
            "AUD-03: rolling windows and split-half k (exploratory v2) reproduce",
            "rerun:explore-v2",
        ),
        _i(
            "AUD-04",
            "Final directive",
            "AUD-04: row contract and provenance enforced wherever observations are used",
            "provenance:passed",
            "code:no-projection",
        ),
        _i(
            "AUD-05",
            "Final directive",
            "AUD-05: decoupled historical stages reproduce v1 on valid rows",
            "rerun:explore-v2",
        ),
        _i(
            "AUD-06",
            "Final directive",
            "AUD-06: the simulation suite executed, reproducible from its raw results and seeds",
            "aud06:acceptance",
            "rerun:simulation-sample",
            "rerun:simulation-summary",
        ),
        _i(
            "AUD-07",
            "Final directive",
            "AUD-07: threshold derivation qualified; sensitivity reproduces; thresholds frozen",
            "aud07:frozen-thresholds",
            "rerun:thresholds",
        ),
        _i(
            "PB-AUD-01",
            "Final directive",
            "PB-AUD-01: live content-level reconciliation",
            "pb01:content",
        ),
        _i(
            "PB-AUD-02",
            "Final directive",
            "PB-AUD-02: fail-closed ownership replay verified at every snapshot",
            "pb02:fail-closed",
        ),
        _i(
            "PB-AUD-03",
            "Final directive",
            "PB-AUD-03: availability reconstruction validated against observed states",
            "pb03:availability",
        ),
        _i(
            "PB-AUD-04", "Final directive", "PB-AUD-04: all-week bootstrap blocks", "pb04:all-weeks"
        ),
        _i(
            "PB-AUD-05",
            "Final directive",
            "PB-AUD-05: streaming feasibility and collisions reported",
            "pb05:feasibility",
        ),
        _i(
            "PB-AUD-06",
            "Final directive",
            "PB-AUD-06: exact eligible decision sets; comparable manager decisions",
            "pb06:eligible-options",
        ),
        _i(
            "PB-AUD-07",
            "Final directive",
            "PB-AUD-07: observed availability captured at decision time",
            "pb07:capture",
        ),
        _i(
            "PB-AUD-08",
            "Final directive",
            "PB-AUD-08: immutable league inputs; the corrected evaluation reruns from them",
            "pb08:pinned",
            "rerun:league-v2",
        ),
        _i(
            "PB-B1B2",
            "Phase B",
            "B1-B2: eligible ESPN league data used through the existing integration, no projections",
            "pb01:content",
            "code:no-projection",
        ),
        _i(
            "PB-B6",
            "Phase B",
            "B6: C05L split; the corrected exploratory evaluation reproduces",
            "rerun:league-v2",
            "owner:inaugural-season",
        ),
        _i(
            "PB-B8",
            "Phase B",
            "B8: no projections, production writes, weight changes or league changes",
            "code:no-projection",
            "elig:registry",
            "receipts:no-projection",
        ),
        _i(
            "P4P-INFRA",
            "§9",
            "Prospective collection infrastructure operational: timer, gate, archive, evidence",
            "timer:operational",
            "timer:retires",
            "aud01a:evidence",
            "aud01c:gate",
            "aud01d:archive",
        ),
        _i(
            "C05L-2026-PRO-INFRA",
            "§5 Phase C",
            "C05L-2026-PRO collection: decision-time league captures with observed availability",
            "pb07:capture",
        ),
        _i(
            "DEC-01",
            "Owner decisions",
            "DEC-01: inaugural season; pre-2026 league evaluation not applicable",
            "owner:inaugural-season",
        ),
        _i(
            "DEC-02",
            "Owner decisions",
            "DEC-02: the research timer installed, safeguarded and bounded",
            "timer:operational",
            "timer:retires",
        ),
        _i(
            "DEC-03",
            "Owner decisions",
            "DEC-03: frozen methods, candidates, thresholds and window preserved",
            "dec:frozen-unchanged",
            "aud07:frozen-thresholds",
        ),
        _i(
            "DEC-04",
            "Owner decisions",
            "DEC-04: exact research inputs preserved; versioning deferred",
            "pb08:pinned",
        ),
        _i(
            "DEC-05",
            "Owner decisions",
            "DEC-05: unsupported ownership changes refused",
            "pb02:fail-closed",
        ),
        _i(
            "DEC-06",
            "Owner decisions",
            "DEC-06: realistic decision sets; unowned never assumed claimable",
            "pb03:availability",
            "pb06:eligible-options",
        ),
        _i(
            "DEC-07",
            "Owner decisions",
            "DEC-07: B06 kept as the promising historical candidate; no production influence",
            "elig:registry",
        ),
        _i(
            "DEC-08",
            "Owner decisions",
            "DEC-08: AUD-06 and AUD-07 implemented and executed",
            "aud06:acceptance",
            "rerun:thresholds",
        ),
        _i(
            "DEC-09",
            "Owner decisions",
            "DEC-09: remediation 7 and eligibility metadata complete",
            "elig:registry",
            "findings:reconciled",
        ),
        _i(
            "DEC-10",
            "Owner decisions",
            "DEC-10: scope controlled; leads recorded, not expanded",
            "elig:registry",
        ),
        _i(
            "ELIG",
            "§11 eligibility",
            "Research eligibility registry with fail-closed production gate",
            "elig:registry",
        ),
        _i(
            "FINDINGS",
            "§3 reconciliation",
            "Every external finding independently reconciled and closed",
            "findings:reconciled",
        ),
    )


def _without_seconds(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "seconds"}


def _dvp_module(audit: Any) -> Any:
    spec = importlib.util.spec_from_file_location(
        "dvp_cli_audit", audit.ROOT / "scripts/model/dvp.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dvp_cli_audit"] = module
    spec.loader.exec_module(module)
    return module


def _gate_cases() -> Result:
    """The completion gate on the directive's cases (window.py), called directly."""
    from arbit_model.dvp import window as w

    cut = {wk: datetime(2026, 11, 26, 1, tzinfo=UTC) + timedelta(weeks=wk - 12) for wk in (12, 13)}
    late = datetime(2027, 2, 1, tzinfo=UTC)

    def entry(week: int, **kw: Any) -> dict[str, Any]:
        return {
            "week": week,
            "classification": "PROSPECTIVE",
            "folder": f"week-{week}",
            "generatedAt": (cut[week] - timedelta(days=1)).isoformat(),
            "archivedAt": (cut[week] - timedelta(days=1)).isoformat(),
            "entrySha256": f"e{week}",
        } | kw

    def pub(week: int, hours: int = 20) -> dict[str, Any]:
        return {
            "ledgerEntrySha256": f"e{week}",
            "verified": True,
            "externalTimestamp": (cut[week] - timedelta(hours=hours)).isoformat(),
        }

    def found(
        week: int,
        entries: list[dict[str, Any]] | None = None,
        match: bool = True,
        pubs: list[dict[str, Any]] | None = None,
    ) -> Any:
        es = entries if entries is not None else [entry(week)]
        return w.WeekArchive(
            week,
            cut[week],
            es,
            {e["folder"]: match for e in es if "folder" in e},
            pubs if pubs is not None else [pub(week)],
        )

    def games(week: int, final: int, total: int = 2) -> pl.DataFrame:
        return pl.DataFrame(
            [
                {
                    "week": week,
                    "game_id": f"g{week}{i}",
                    "kickoff": cut[week] + timedelta(hours=i),
                    "available_at": cut[week] + timedelta(days=1),
                    "status": "completed" if i < final else "not_completed",
                }
                for i in range(total)
            ]
        )

    def labelled(week: int, total: int = 2, missing: int = 0) -> pl.DataFrame:
        rows = [
            {"week": week, "game_id": f"g{week}{g}", "label_status": "valid"}
            for g in range(total)
            for _ in range(12)
        ]
        for r in rows[:missing]:
            r["label_status"] = "missing"
        return pl.DataFrame(rows)

    def window_of(
        archives: dict[int, Any],
        labels: dict[int, Any],
        weeks: list[int] | None = None,
        now: datetime = late,
    ) -> str:
        ws = weeks or [12, 13]
        a = {k: w.archive_state(archives[k], now) for k in ws}
        return str(w.window_state(ws, [12, 13], a, {k: labels[k] for k in ws})["status"])

    full = {
        wk: w.label_state(wk, games(wk, 2), labelled(wk), late, timedelta(days=4))
        for wk in (12, 13)
    }
    good = {wk: found(wk) for wk in (12, 13)}
    early = cut[12] + timedelta(days=1, hours=2)
    cases = {
        "complete window": window_of(good, full) == w.COMPLETE,
        "first game only": w.label_state(
            12, games(12, 1, 3), labelled(12, 3), early, timedelta(days=4)
        )["status"]
        == w.AWAITING_GAMES,
        "labels missing": w.label_state(
            12, games(12, 2), labelled(12, missing=2), late, timedelta(days=4)
        )["status"]
        == w.LABELS_INCOMPLETE,
        "missed week": window_of(good | {13: found(13, entries=[], pubs=[])}, full)
        == w.INCOMPLETE_WINDOW,
        "retrospective for missed": window_of(
            good
            | {
                13: found(
                    13,
                    entries=[
                        {"week": 13, "classification": "MISSED", "reason": "x"},
                        entry(13, classification="RETROSPECTIVE", folder="r13"),
                    ],
                    pubs=[],
                )
            },
            full,
        )
        == w.INCOMPLETE_WINDOW,
        "commitment after cutoff": w.archive_state(found(12, pubs=[pub(12, hours=-2)]), late)[
            "status"
        ]
        == w.MISSED,
        "integrity failure": window_of(good | {12: found(12, match=False)}, full) == w.BLOCKED,
        "subset": window_of(good, full, weeks=[12]) == w.INTERIM,
    }
    return all(cases.values()), cases


def _archive_cases(scratch: Path) -> Result:
    from arbit_model.dvp import archive

    folder = scratch / "archive-cases"
    folder.mkdir(parents=True, exist_ok=True)

    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    cutoff = datetime(2026, 12, 4, 1, 15, tzinfo=UTC)
    now = cutoff - timedelta(days=1)
    csv, league = b"g,b00\n1,2\n", b"{}\n"
    manifest = json.dumps(
        {
            "classification": "PROSPECTIVE",
            "generatedAt": now.isoformat(),
            "cutoff": cutoff.isoformat(),
            "code": "x",
            "forecasts": {
                "csvSha256": digest(csv),
                "parquetSha256": digest(b"P"),
                "contentSha256": "c",
            },
            "league": {"sha256": digest(league)},
            "inputs": {},
        }
    ).encode()
    files = {
        "forecasts.parquet": b"P",
        "forecasts.csv": csv,
        "manifest.json": manifest,
        "league.json": league,
    }

    class Crash(Exception):
        pass

    def crash(point: str) -> Callable[[str], None]:
        def fault(where: str) -> None:
            if where == point:
                raise Crash(where)

        return fault

    results: dict[str, Any] = {}
    for point, expected in (("before_rename", "removed-staging"), ("after_rename", "recover")):
        root = folder / point
        root.mkdir()
        try:
            archive.commit(root / "week-13", files, lambda: now, fault=crash(point))
        except Crash:
            pass
        actions = archive.recover(root, [], {}, now)
        results[point] = [a["action"] for a in actions] == [expected]
    late_root = folder / "late"
    late_root.mkdir()
    archive.commit(late_root / "week-13", files, lambda: now)
    results["after the cutoff"] = (
        archive.recover(late_root, [], {}, cutoff + timedelta(minutes=1))[0]["action"]
        == "missed-unproven"
    )
    with archive.exclusive(folder):
        try:
            with archive.exclusive(folder):
                results["concurrent refused"] = False
        except archive.Busy:
            results["concurrent refused"] = True
    return all(results.values()), results


def _retire_cases(audit: Any, scratch: Path) -> Result:
    harness = _harness(audit)
    root = scratch / "retire-cases" / "2026"
    root.mkdir(parents=True, exist_ok=True)
    past = datetime(2026, 1, 1, tzinfo=UTC)
    lines = [
        harness.append_ledger(
            root / "ledger.jsonl",
            {"week": 12, "classification": "PROSPECTIVE", "cutoff": past.isoformat()},
        ),
    ]
    args = type("A", (), {"archive": scratch / "retire-cases", "main": scratch, "season": 2026})()
    before = harness.retire_if_done(args, 2026, [12])  # no verified commitment yet
    harness.append_ledger(
        root / "publications.jsonl",
        {"kind": "github-branch", "ledgerEntrySha256": lines[0]["entrySha256"], "verified": True},
    )
    after = harness.retire_if_done(args, 2026, [12])
    open_week = harness.retire_if_done(args, 2026, [12, 13])  # week 13 not final
    return before == "OPEN" and after == "COMPLETE" and open_week == "OPEN", {
        "beforeCommitment": before,
        "complete": after,
        "weekStillOpen": open_week,
    }


# --- negative controls ----------------------------------------------------------------------------


@contextmanager
def _receipts_copy(audit: Any, mutate: Callable[[Path], None]) -> Iterator[None]:
    original = audit.RECEIPTS
    with tempfile.TemporaryDirectory() as tmp:
        copy_root = Path(tmp) / "dvp"
        shutil.copytree(original, copy_root, ignore=shutil.ignore_patterns("plots", "prospective"))
        mutate(copy_root)
        audit.RECEIPTS = copy_root
        try:
            yield
        finally:
            audit.RECEIPTS = original


def _edit_json(path: Path, change: Callable[[Any], None]) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


@contextmanager
def _patched(target: Any, name: str, value: Any) -> Iterator[None]:
    original = getattr(target, name)
    setattr(target, name, value)
    try:
        yield
    finally:
        setattr(target, name, original)


def controls(audit: Any, ctx: Any) -> list[dict[str, Any]]:
    """Plant each defect the directive lists and confirm the audit catches it (§12 F5)."""
    from arbit_model import eligibility as el
    from arbit_model import ffa_history as fh
    from arbit_model.dvp import window

    def failed(check_id: str) -> bool:
        return not audit._run_check(ctx, check_id)["passed"]

    out: list[dict[str, Any]] = []

    def record(control: str, check_id: str, detected: bool) -> None:
        out.append({"control": control, "detectedBy": check_id, "detected": bool(detected)})

    def drop_variant(root: Path) -> None:
        _edit_json(root / "backtest-development.json", lambda d: d["results"]["DST"].pop("b04_k8"))

    with _receipts_copy(audit, drop_variant):
        record(
            "missing required estimator variant", "backtest:variants", failed("backtest:variants")
        )

    def drop_position(root: Path) -> None:
        _edit_json(root / "backtest-validation.json", lambda d: d["results"].pop("TE"))

    with _receipts_copy(audit, drop_position):
        record("missing position or stage", "backtest:variants", failed("backtest:variants"))

    def not_run(root: Path) -> None:
        def change(d: Any) -> None:
            d["experiments"][0]["status"] = "NOT_RUN"

        _edit_json(root / "experiment-registry.json", change)

    with _receipts_copy(audit, not_run):
        record("required experiment not executed", "registry:complete", failed("registry:complete"))

    skipped = dict(ctx.junit)
    victim = next(k for k in skipped if "test_t26" in k.lower() or "t26" in k)
    skipped[victim] = "skipped"
    with _patched(ctx, "junit", skipped):
        record("required test skipped", "test:T26", failed("test:T26"))

    def stale(root: Path) -> None:
        def change(d: Any) -> None:
            d["results"]["A05"]["DST"]["adjusted"]["reml"]["k"] = 99.0

        _edit_json(root / "reliability-results.json", change)

    with _receipts_copy(audit, stale):
        record("stale receipt", "rerun:reliability", failed("rerun:reliability"))

    real = audit.sha256
    with _patched(
        audit, "sha256", lambda p: "0" * 64 if str(p).endswith("observations.parquet") else real(p)
    ):
        record("modified frozen artifact", "audit:frozen-outputs", failed("audit:frozen-outputs"))

    dvp = _dvp_module(audit)
    with tempfile.TemporaryDirectory() as tmp:
        planted = Path(tmp) / "planted.py"
        planted.write_text("from arbit_data.espn import projections\nx = row['projected_points']\n")
        original_loader = _dvp_module
        patched = copy.copy(dvp)
        patched.SCANNED = (*dvp.SCANNED, str(planted))
        globals()["_dvp_module"] = lambda a: patched
        try:
            record(
                "prohibited provider projection dependency",
                "code:no-projection",
                failed("code:no-projection"),
            )
        finally:
            globals()["_dvp_module"] = original_loader

    with tempfile.TemporaryDirectory() as tmp:
        fake_run = Path(tmp) / "run"
        fake_run.mkdir()
        observations = pl.read_parquet(ctx.run / "observations.parquet")
        observations.with_columns(
            pl.when(pl.int_range(pl.len()) == 0)
            .then(pl.lit("PROVIDER_PROJECTION"))
            .otherwise(pl.col("source_type"))
            .alias("source_type")
        ).write_parquet(fake_run / "observations.parquet")
        moved = audit.Context(ctx.scratch, ctx.reruns | {"runPath": str(fake_run)}, ctx.junit)
        result = audit._run_check(moved, "audit:observation-lineage")
        record("incorrect source lineage", "audit:observation-lineage", not result["passed"])

    def ownership(root: Path) -> None:
        def change(d: Any) -> None:
            d["ownership"]["everySnapshot"]["disagree"] = 3

        _edit_json(root / "league-2026-exploratory-v2.json", change)

    with _receipts_copy(audit, ownership):
        record("incorrect historical ownership", "pb02:fail-closed", failed("pb02:fail-closed"))

    def availability(root: Path) -> None:
        def change(d: Any) -> None:
            states = d["availabilityAtCutoff"]["5"]["states"]
            unit = next(u for u, s in states.items() if s[0] == "WAIVERS")
            states[unit][0] = "FREE_AGENT"

        _edit_json(root / "league-2026-exploratory-v2.json", change)

    with _receipts_copy(audit, availability):
        record(
            "incorrect availability classification", "rerun:league-v2", failed("rerun:league-v2")
        )

    def option(root: Path) -> None:
        def change(d: Any) -> None:
            row = d["decisions"]["streamClaimable"][0]
            row["optionEvidence"]["ZZZ"] = ["WAIVERS", "RECONSTRUCTED"]

        _edit_json(root / "league-2026-exploratory-v2.json", change)

    with _receipts_copy(audit, option):
        record(
            "ineligible decision option", "pb06:eligible-options", failed("pb06:eligible-options")
        )

    def zero_weeks(root: Path) -> None:
        def change(d: Any) -> None:
            d["results"]["start"]["bootstrap"] = {"method": "changed_weeks", "blocks": 9}

        _edit_json(root / "league-2026-exploratory-v2.json", change)

    with _receipts_copy(audit, zero_weeks):
        record(
            "zero-change weeks omitted from the bootstrap",
            "pb04:all-weeks",
            failed("pb04:all-weeks"),
        )

    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "artifacts/dvp/league-2026/inputs-v1"
        shutil.copytree(_main(ctx) / "artifacts/dvp/league-2026/inputs-v1", bundle)
        (bundle / "transactions.parquet").chmod(0o644)
        (bundle / "transactions.parquet").unlink()
        moved = audit.Context(ctx.scratch, ctx.reruns | {"mainPath": tmp}, ctx.junit)
        result = audit._run_check(moved, "pb08:pinned")
        record("missing normalized league input artifact", "pb08:pinned", not result["passed"])

    def any_final(week: int, schedule: pl.DataFrame, *args: Any, **kw: Any) -> dict[str, Any]:
        done = schedule.filter((pl.col("week") == week) & (pl.col("status") == "completed")).height
        return {"status": window.LABELLED if done else window.AWAITING_GAMES, "reasons": []}

    with _patched(window, "label_state", any_final):
        record("incorrect prospective week completion", "aud01c:gate", failed("aud01c:gate"))

    real_state = window.window_state

    def lenient(weeks: Any, declared: Any, archives: Any, labels: Any) -> dict[str, Any]:
        softened = {
            k: (v | {"status": window.PROSPECTIVE} if v["status"] == window.MISSED else v)
            for k, v in archives.items()
        }
        return real_state(weeks, declared, softened, labels)

    with _patched(window, "window_state", lenient):
        record("missed forecast classified as prospective", "aud01c:gate", failed("aud01c:gate"))

    real_moves = fh.moves

    def ignoring(transactions: Any) -> Any:
        kept = [t for t in transactions if t["type"] in fh.MOVE_TYPES and t.get("processed_at")]
        return real_moves(kept)

    with _patched(fh, "moves", ignoring):
        record(
            "unsupported ownership-changing transaction",
            "pb02:fail-closed",
            failed("pb02:fail-closed"),
        )

    blocked = audit.Item(
        "X-BLOCKED",
        "control",
        "blocked without evidence",
        ("findings:reconciled",),
        "blocked_external",
    )
    with _patched(audit, "ITEMS", (blocked,)):
        status = audit.evaluate(ctx)["items"][0]["status"]
    record("blocked requirement without evidence", "evaluate (evidence rule)", status == "FAILED")

    with tempfile.TemporaryDirectory() as tmp:
        data = json.loads(el.REGISTRY.read_text())
        data["entries"][0]["productionEligible"] = True
        registry = Path(tmp) / "registry.json"
        registry.write_text(json.dumps(data))
        with _patched(el, "REGISTRY", registry):
            real_load = el.load
            with _patched(el, "load", lambda path=registry: real_load(path)):
                record(
                    "research factor marked production-eligible",
                    "elig:registry",
                    failed("elig:registry"),
                )
    return out
