"""Summaries, acceptance and plots for the AUD-06 simulation suite (dvp_simulate.py summarize)."""

import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from arbit_model.dvp import svg

SHRUNK = ("b03", "b03r", "b04", "b05", "b06", "b07")


def family(variant: str) -> str:
    for prefix in ("b04", "b05", "b09"):
        if variant.startswith(prefix):
            return prefix
    return variant


def rate(hits: int, n: int) -> dict[str, Any]:
    """A frequency with its Monte Carlo standard error and Wilson 95% interval."""
    if n == 0:
        return {"rate": None, "n": 0}
    p = hits / n
    z = 1.959964
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "rate": round(p, 4),
        "hits": hits,
        "n": n,
        "se": round(math.sqrt(p * (1 - p) / n), 4),
        "ci95": [round(centre - half, 4), round(centre + half, 4)],
    }


def load(folder: Path) -> dict[str, list[dict[str, Any]]]:
    out = {}
    for path in sorted(folder.glob("*.jsonl")):
        out[path.stem] = [
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        ]
    return out


def q(values: list[float], p: float) -> float | None:
    return None if not values else round(float(np.quantile(values, p)), 4)


def summarize_e1(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for scenario, reps in results.items():
        ok = [r for r in reps if "failed" not in r]
        entry: dict[str, Any] = {"reps": len(reps), "failed": len(reps) - len(ok), "positions": {}}
        positions = sorted({p for r in ok for p in r["positions"]})
        for p in positions:
            rows = [r["positions"][p] for r in ok]
            k_true = rows[0]["kTrue"]
            reml = [x["kReml"] for x in rows if x["kReml"] is not None]
            split = [
                x["kSplitHalf"] for x in rows if x["kSplitHalf"] is not None and x["kSplitHalf"] > 0
            ]
            tau2 = [x["tau2"] for x in rows]
            sigma2 = [x["sigma2"] for x in rows]
            t2 = rows[0]["tau2True"]
            e: dict[str, Any] = {
                "kTrue": k_true,
                "tau2True": t2,
                "sigma2True": rows[0]["sigma2True"],
                "converged": rate(sum(x["converged"] for x in rows), len(rows)),
                "unidentified": rate(sum(x["kReml"] is None for x in rows), len(rows)),
                "reml": {"median": q(reml, 0.5), "q25": q(reml, 0.25), "q75": q(reml, 0.75)},
                "splitHalf": {
                    "median": q(split, 0.5),
                    "q25": q(split, 0.25),
                    "q75": q(split, 0.75),
                },
                "tau2": {
                    "mean": round(float(np.mean(tau2)), 4),
                    "bias": round(float(np.mean(tau2)) - t2, 4),
                    "variance": round(float(np.var(tau2)), 5),
                    "mse": round(float(np.mean([(x - t2) ** 2 for x in tau2])), 5),
                },
                "sigma2": {"mean": round(float(np.mean(sigma2)), 3)},
                "iccTrue": round(t2 / (t2 + rows[0]["sigma2True"]), 4),
                "iccMean": round(float(np.mean([x["icc"] for x in rows])), 4),
            }
            if k_true is not None:
                rel = [abs(k / k_true - 1) for k in reml]
                logs = [math.log(k / k_true) for k in reml]
                rel_s = [abs(k / k_true - 1) for k in split]
                e["remlMedianRelativeError"] = q(rel, 0.5)
                e["remlLogBias"] = round(float(np.mean(logs)), 4) if logs else None
                e["remlLogMse"] = round(float(np.mean([v * v for v in logs])), 4) if logs else None
                e["splitHalfMedianRelativeError"] = q(rel_s, 0.5)
                intervals = [x["k95"] for x in rows if x.get("k95")]
                e["k95Coverage"] = rate(
                    sum(lo <= k_true <= hi for lo, hi in intervals), len(intervals)
                )
                e["k95MedianWidth"] = q([hi - lo for lo, hi in intervals], 0.5)
            else:
                e["splitHalfAbove100"] = rate(sum(k > 100 for k in split), len(rows))
                intervals = [x for x in rows if "k95" in x]
                e["bootBoundaryShareMean"] = (
                    round(float(np.mean([x["bootBoundaryShare"] for x in intervals])), 4)
                    if intervals
                    else None
                )
            entry["positions"][p] = e
        opp = [r["opportunity"] for r in ok if "opportunity" in r]
        if opp:
            entry["opportunity"] = {
                p: {
                    m: {
                        "medianK": q([o[p][m]["k"] for o in opp if o[p][m]["k"] is not None], 0.5),
                        "unidentified": rate(sum(o[p][m]["k"] is None for o in opp), len(opp)),
                    }
                    for m in ("points", "volume", "efficiency")
                }
                for p in opp[0]
            }
        out[scenario] = entry
    return out


def summarize_e2(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for scenario, reps in results.items():
        ok = [r for r in reps if "failed" not in r]
        entry: dict[str, Any] = {
            "reps": len(reps),
            "failed": len(reps) - len(ok),
            "failures": sorted({r["failed"][:120] for r in reps if "failed" in r})[:3],
            "secondsMedian": q([r["seconds"] for r in ok], 0.5),
            "positions": {},
        }
        positions = sorted({p for r in ok for p in r["positions"]})
        for p in positions:
            rows = [r["positions"][p] for r in ok]
            n = len(rows)
            labels = Counter(x["label"] for x in rows)
            candidates = [x["selection"] for x in rows if x["selection"]["candidate"] != "b00"]
            fams = Counter(family(x["selection"]["bestDvp"]) for x in rows)
            dev_best = [x["selection"]["bestRelativeDelta"] for x in rows]
            val_best = [x["validation"].get(x["selection"]["bestDvp"]) for x in rows]
            curse = [d - v for d, v in zip(dev_best, val_best, strict=True) if v is not None]
            variants = sorted({v for x in rows for v in x["development"]})
            means = {
                v: {
                    stage: round(
                        float(np.mean([x[stage][v] for x in rows if x[stage].get(v) is not None])),
                        5,
                    )
                    for stage in ("development", "validation", "holdout")
                    if any(x[stage].get(v) is not None for x in rows)
                }
                for v in variants
            }
            controls = {
                v: rate(sum((x["development"].get(v) or 0) <= -0.01 for x in rows), n)
                for v in variants
                if v.startswith("b09")
            }
            entry["positions"][p] = {
                "labels": {
                    k: rate(labels.get(k, 0), n)
                    for k in ("PROMISING", "INCONCLUSIVE", "NOT_USEFUL")
                },
                "candidateSelected": rate(len(candidates), n),
                "selectedFamily": dict(sorted(fams.items())),
                "shrunkAmongCandidates": rate(
                    sum(family(c["bestDvp"]) in SHRUNK for c in candidates), len(candidates)
                ),
                "developmentBestMean": round(float(np.mean(dev_best)), 5),
                "winnersCurseMean": round(float(np.mean(curse)), 5) if curse else None,
                "variantMeans": means,
                "controlsCutting1Percent": controls,
                "oracle": means.get("oracle"),
            }
        dst = [r["phaseC"] for r in ok if "phaseC" in r]
        if dst:
            labels = Counter(x["label"] for x in dst)
            both = sum(
                r["positions"]["DST"]["label"] == "PROMISING"
                and r["phaseC"]["label"] == "PROMISING"
                for r in ok
                if "phaseC" in r
            )
            entry["phaseC"] = {
                "labels": {
                    k: rate(labels.get(k, 0), len(dst))
                    for k in ("PROMISING", "INCONCLUSIVE", "NOT_USEFUL")
                },
                "deltaPpMean": {
                    k: round(float(np.mean([x["periods"][k]["deltaPp"] for x in dst])), 3)
                    for k in ("development", "validation", "holdout")
                },
                "phaseBandPhaseCPromising": rate(both, len(dst)),
            }
        entry["anyPositionPromising"] = rate(
            sum(any(r["positions"][p]["label"] == "PROMISING" for p in positions) for r in ok),
            len(ok),
        )
        entry["anyPositionCandidate"] = rate(
            sum(
                any(r["positions"][p]["selection"]["candidate"] != "b00" for p in positions)
                for r in ok
            ),
            len(ok),
        )
        fold_k = {
            p: [
                r["params"]["2025"]["kDvp"][p]
                for r in ok
                if r["params"]["2025"]["kDvp"][p] is not None
            ]
            for p in positions
        }
        entry["kDvp2025Fold"] = {
            p: {"median": q(v, 0.5), "unidentified": rate(len(ok) - len(v), len(ok))}
            for p, v in fold_k.items()
        }
        out[scenario] = entry
    return out


def summarize_e3(results: dict[str, list[dict[str, Any]]], truth: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for case, reps in results.items():
        ok = [r for r in reps if "failed" not in r]
        entry: dict[str, Any] = {"reps": len(reps), "failed": len(reps) - len(ok)}
        for kind in ("start", "stream"):
            true_value = truth[case][kind]
            rows = [r[kind] for r in ok]
            m: dict[str, Any] = {
                "truth": round(true_value, 3),
                "truthSe": round(truth[case][f"{kind}Se"], 3),
                "meanPoints": round(float(np.mean([x["points"] for x in rows])), 3),
                "meanChanged": round(float(np.mean([x["changed"] for x in rows])), 2),
                "meanZeroChangeWeeks": round(
                    float(np.mean([x["zeroChangeWeeks"] for x in rows])), 2
                ),
            }
            for method in ("allWeeks95", "changedWeeks95", "naive95"):
                ints = [x[method] for x in rows if x[method]]
                m[method] = {
                    "excludesZero": rate(sum(lo > 0 or hi < 0 for lo, hi in ints), len(ints)),
                    "coversTruth": rate(sum(lo <= true_value <= hi for lo, hi in ints), len(ints)),
                    "medianWidth": q([hi - lo for lo, hi in ints], 0.5),
                }
            entry[kind] = m
        out[case] = entry
    return out


def summarize_u(results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cond, reps in results.items():
        ok = [r for r in reps if "failed" not in r]
        out[cond] = {
            "reps": len(reps),
            "failed": len(reps) - len(ok),
            "blocks": ok[0]["blocks"] if ok else None,
            "truth": round(ok[0]["truth"], 5) if ok else None,
            "coverage": rate(sum(r["covered"] for r in ok), len(ok)),
            "meanEstimateMinusTruth": round(
                float(np.mean([r["estimate"] - r["truth"] for r in ok])), 5
            ),
            "medianWidth": q([r["high"] - r["low"] for r in ok], 0.5),
        }
    return out


def verdict(
    value: dict[str, Any], *, at_most: float | None = None, at_least: float | None = None
) -> str:
    """PASS, FAIL, or INCONCLUSIVE when the Monte Carlo interval straddles the threshold."""
    if value.get("rate") is None:
        return "INCONCLUSIVE"
    lo, hi = value["ci95"]
    if at_most is not None:
        return "PASS" if hi <= at_most else ("FAIL" if lo > at_most else "INCONCLUSIVE")
    assert at_least is not None
    return "PASS" if lo >= at_least else ("FAIL" if hi < at_least else "INCONCLUSIVE")


def acceptance(
    e1: dict[str, Any], e2: dict[str, Any], e3: dict[str, Any], u: dict[str, Any]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    null = e2.get("SIM-01", {})
    out["A1"] = {
        "perPosition": {
            p: verdict(v["labels"]["PROMISING"], at_most=0.05)
            for p, v in null.get("positions", {}).items()
        },
        "phaseBandC": verdict(
            null.get("phaseC", {}).get("phaseBandPhaseCPromising", {}), at_most=0.05
        ),
    }
    out["A2"] = verdict(e2.get("SIM-16", {}).get("anyPositionPromising", {}), at_most=0.10)
    strong = e2.get("SIM-04", {}).get("positions", {})
    out["A3"] = {p: verdict(v["labels"]["PROMISING"], at_least=0.80) for p, v in strong.items()}
    a4 = {}
    for scenario in ("SIM-03", "SIM-04"):
        for p, v in e1.get(scenario, {}).get("positions", {}).items():
            err = v.get("remlMedianRelativeError")
            a4[f"{scenario}/{p}"] = {
                "medianRelativeError": err,
                "relativeError": "PASS" if err is not None and err <= 0.25 else "FAIL",
                "convergence": verdict(v["converged"], at_least=0.95),
            }
    out["A4"] = a4
    out["A5"] = {p: verdict(v["shrunkAmongCandidates"], at_least=0.90) for p, v in strong.items()}
    a6 = {}
    for scenario in ("SIM-01", "SIM-04"):
        for p, v in e2.get(scenario, {}).get("positions", {}).items():
            for control, value in v["controlsCutting1Percent"].items():
                a6[f"{scenario}/{p}/{control}"] = verdict(value, at_most=0.05)
    out["A6"] = a6
    matched = ("independent", "weekShock", "sharedGame", "unequalExposure")
    out["A7"] = {
        c: ("PASS" if 0.92 <= u[c]["coverage"]["rate"] <= 0.98 else "FAIL")
        for c in matched
        if c in u
    } | {
        f"{c} (limitation, not a criterion)": u[c]["coverage"]["rate"]
        for c in u
        if c not in matched
    }
    a8 = {}
    for case in ("SIM-17-null", "SIM-18-null"):
        for kind in ("start", "stream"):
            if case in e3:
                a8[f"{case}/{kind}/falsePositive"] = verdict(
                    e3[case][kind]["allWeeks95"]["excludesZero"], at_most=0.07
                )
    for case in e3:
        for kind in ("start", "stream"):
            cov = e3[case][kind]["allWeeks95"]["coversTruth"]["rate"]
            a8[f"{case}/{kind}/coverage"] = (
                "PASS" if cov is not None and 0.90 <= cov <= 0.98 else "FAIL"
            )
    out["A8"] = a8
    return out


def plots(
    folder: Path, e1: dict[str, Any], e2: dict[str, Any], e3: dict[str, Any], u: dict[str, Any]
) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    rows = []
    for scenario in sorted(e2):
        for p, v in sorted(e2[scenario]["positions"].items()):
            r = v["labels"]["PROMISING"]
            if r.get("rate") is not None:
                rows.append((f"{scenario} {p}", p, r["rate"], r["ci95"][0], r["ci95"][1]))
    (folder / "promising-rate.svg").write_text(
        svg.forest(
            "Phase B PROMISING rate by scenario (Monte Carlo 95%)",
            rows,
            xlabel="share of repetitions",
            xlim=(0.0, 1.0),
            note="Null scenarios should sit near 0; strong signals near 1.",
            log=False,
        )
    )
    written.append("promising-rate.svg")
    rows = []
    for scenario in sorted(e1):
        for p, v in sorted(e1[scenario]["positions"].items()):
            if v["kTrue"] and v["reml"]["median"]:
                rows.append(
                    (
                        f"{scenario} {p}",
                        p,
                        v["reml"]["median"] / v["kTrue"],
                        (v["reml"]["q25"] or 0) / v["kTrue"],
                        (v["reml"]["q75"] or 0) / v["kTrue"],
                    )
                )
    (folder / "k-recovery.svg").write_text(
        svg.forest(
            "REML k / true k (median and interquartile range)",
            rows,
            xlabel="k estimate / true k",
            xlim=(0.25, 4.0),
            note="1 is exact recovery.",
            log=True,
        )
    )
    written.append("k-recovery.svg")
    rows = [
        (c, "DST", v["coverage"]["rate"], v["coverage"]["ci95"][0], v["coverage"]["ci95"][1])
        for c, v in sorted(u.items())
    ]
    (folder / "bootstrap-coverage.svg").write_text(
        svg.forest(
            "walkforward.metrics 95% interval coverage",
            rows,
            xlabel="coverage",
            xlim=(0.5, 1.0),
            note="Nominal 0.95.",
            log=False,
        )
    )
    written.append("bootstrap-coverage.svg")
    rows = []
    for case in sorted(e3):
        for kind in ("start", "stream"):
            for method in ("allWeeks95", "changedWeeks95", "naive95"):
                c = e3[case][kind][method]["coversTruth"]
                rows.append(
                    (
                        f"{case} {kind} {method[:-2]}",
                        "WR" if method == "allWeeks95" else "K",
                        c["rate"],
                        c["ci95"][0],
                        c["ci95"][1],
                    )
                )
    (folder / "league-coverage.svg").write_text(
        svg.forest(
            "League bootstrap coverage of the true gain",
            rows,
            xlabel="coverage",
            xlim=(0.5, 1.0),
            note="Nominal 0.95; all-weeks (orange) is the corrected method.",
            log=False,
        )
    )
    written.append("league-coverage.svg")
    return written


def main(root: Path, config: Path, out: Path) -> None:
    e1 = summarize_e1(load(out / "E1"))
    e2 = summarize_e2(load(out / "E2"))
    truth = json.loads((out / "league-truth.json").read_text())
    e3 = summarize_e3(load(out / "E3"), truth)
    u = summarize_u(load(out / "U"))
    receipt = {
        "format": "arbit-dvp-m3-3-simulation-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
        ).stdout.strip(),
        "config": {
            "path": "config/dvp/simulation-v1.json",
            "sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        },
        "rawResults": "artifacts/dvp/simulation-v1/<experiment>/<scenario>.jsonl (local)",
        "E1": e1,
        "E2": e2,
        "E3": e3,
        "U": u,
        "leagueTruth": truth,
        "acceptance": acceptance(e1, e2, e3, u),
        "plots": plots(root / "docs/research/dvp/plots/simulation", e1, e2, e3, u),
        "write_to_production": False,
    }
    target = root / "docs/research/dvp/simulation-v1.json"
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps(receipt["acceptance"], indent=1)[:3000])
