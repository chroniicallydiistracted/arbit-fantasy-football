"""AUD-07: the frozen thresholds' derivation and a descriptive sensitivity analysis.

config/dvp/threshold-sensitivity-v1.json declares it. Nothing here changes a frozen threshold, a
frozen label or the 2026 confirmation rules.

  POLARS_MAX_THREADS=2 uv run python scripts/model/dvp_thresholds.py --main <main>

Reads the committed receipts and, for D1 only, the frozen audit run's development forecasts and
observations (hash-checked against config/dvp/frozen.json). Writes
docs/research/dvp/threshold-sensitivity-v1.json.
"""

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from arbit_model.dvp import decisions
from arbit_model.dvp import walkforward as wf

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/threshold-sensitivity-v1.json"
RECEIPTS = ROOT / "docs/research/dvp"
CLOSE, POOL, TOP = 1.0, (9, 24), 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accuracy(rho: float) -> float:
    """P(a forecast orders a random pair as the outcome does) for a bivariate normal."""
    return 0.5 + math.asin(rho) / math.pi


def rho_after(rho: float, cut: float) -> float:
    """The correlation a calibrated forecast needs for an RMSE cut of `cut` (MSE = var(1-rho^2))."""
    return math.sqrt(1 - (1 - cut) ** 2 * (1 - rho**2))


def implied_pp(rho: float, cut: float) -> float:
    return 100 * (accuracy(rho_after(rho, cut)) - accuracy(rho))


def d1(main: Path) -> dict[str, Any]:
    frozen = json.loads((ROOT / "config/dvp/frozen.json").read_text())
    run = main / "artifacts/dvp" / frozen["auditRun"]
    for name, digest in frozen["auditOutputs"].items():
        if (run / name).exists() and sha256(run / name) != digest:
            raise SystemExit(f"BLOCKED: {name} of the frozen audit run changed")
    rho_s = 0.1448
    original = {
        "rho": rho_s,
        "rhoAfter1Percent": round(rho_after(rho_s, 0.01), 4),
        "accuracyBefore": round(100 * accuracy(rho_s), 2),
        "accuracyAfter": round(100 * accuracy(rho_after(rho_s, 0.01)), 2),
        "impliedPp": round(implied_pp(rho_s, 0.01), 3),
    }
    pearson_from_spearman = 2 * math.sin(math.pi * rho_s / 6)
    forecasts = pl.read_parquet(run / "backtest-development/forecasts.parquet")
    observations = pl.read_parquet(run / "observations.parquet")
    labels = observations.select("game_id", "offense", "position", "season", "points", "status")
    joined = forecasts.drop(
        [c for c in ("points", "status", "season") if c in forecasts.columns]
    ).join(labels, on=["game_id", "offense", "position"], how="inner")
    dst = joined.filter((pl.col("position") == "DST") & (pl.col("status") == "valid"))
    y, b00 = dst.get_column("points").to_numpy(), dst.get_column("b00").to_numpy()
    pearson = float(np.corrcoef(b00, y)[0, 1])
    spearman = float(
        np.corrcoef(pl.Series(b00).rank().to_numpy(), pl.Series(y).rank().to_numpy())[0, 1]
    )
    # Recalibration: the best linear map of B00 to the outcome. Same order, lower RMSE.
    beta, alpha = np.polyfit(b00, y, 1)
    calibrated = joined.with_columns((alpha + beta * pl.col("b00")).alias("b00cal"))

    def rmse(forecast: np.ndarray) -> float:
        return float(np.sqrt(((forecast - y) ** 2).mean()))

    cut_cal = 1 - rmse(alpha + beta * b00) / rmse(b00)

    def pairwise(frame: pl.DataFrame, model: str) -> dict[str, Any]:
        table = decisions.units(frame, observations, ("b00", model))
        pairs = decisions.pairs(table, ("b00", model), "b00")
        m = decisions.metrics(
            table, pairs, "b00", model, close=CLOSE, pool=POOL, top=TOP, reps=20, seed=1729
        )
        return {"deltaPp": m["deltaPp"], "accuracyB00": m["accuracy"]["b00"], "pairs": m["pairs"]}

    recal = pairwise(calibrated, "b00cal")
    development = json.loads((RECEIPTS / "backtest-development.json").read_text())["results"]["DST"]
    observed = []
    for variant, entry in sorted(development.items()):
        if not isinstance(entry, dict) or "relativeDelta" not in entry or variant == "b00":
            continue
        if variant not in joined.columns:
            continue
        rel = entry["relativeDelta"]
        got = pairwise(joined, variant)
        observed.append(
            {
                "variant": variant,
                "relativeRmseChange": rel,
                "deltaPp": got["deltaPp"],
                "formulaImpliedPp": round(implied_pp(spearman, -rel), 3) if rel < 0 else None,
            }
        )
    return {
        "original": original,
        "assumptions": [
            "forecast and outcome bivariate normal (the arcsine law for pair concordance)",
            "a calibrated forecast: MSE = var(y)(1 - rho^2), which holds for the best linear predictor only",
            "independent random pairs; the real pairs are within weeks and outcomes are integers with ties",
            "Spearman's 0.1448 used where the formula needs Pearson's correlation",
        ],
        "pearsonVersusSpearman": {
            "bivariateNormalPearsonFromSpearman": round(pearson_from_spearman, 4),
            "impliedPpWithThatPearson": round(implied_pp(pearson_from_spearman, 0.01), 3),
            "actualDevelopmentPearsonB00": round(pearson, 4),
            "actualDevelopmentSpearmanB00": round(spearman, 4),
            "impliedPpWithActualPearson": round(implied_pp(pearson, 0.01), 3),
            "formulaAccuracyAtActualPearson": round(100 * accuracy(pearson), 2),
            "actualPairwiseAccuracyB00": recal["accuracyB00"],
        },
        "nonUniqueness": {
            "recalibration": {"alpha": round(float(alpha), 4), "beta": round(float(beta), 4)},
            "rmseCut": round(cut_cal, 5),
            "pairwiseAccuracyChangePp": recal["deltaPp"],
            "reading": "A linear recalibration of B00 lowers RMSE but keeps every pair's order, so pairwise accuracy moves by 0 points: an RMSE change does not determine a ranking change.",
        },
        "observedRelation": observed,
        "rows": dst.height,
    }


def d2() -> dict[str, Any]:
    config = json.loads(CONFIG.read_text())
    dev = json.loads((RECEIPTS / "backtest-development.json").read_text())
    val = json.loads((RECEIPTS / "backtest-validation.json").read_text())
    hold = json.loads((RECEIPTS / "backtest-holdout.json").read_text())
    sit = json.loads((RECEIPTS / "sitstart.json").read_text())
    phase_b: dict[str, Any] = {}
    for position, chosen in dev["selection"]["positions"].items():
        best = chosen["bestDvp"]
        periods = {
            "development": dev["results"][position],
            "validation": val["results"][position],
            "holdout": hold["results"][position],
        }
        rel = {k: v[best]["relativeDelta"] for k, v in periods.items()}
        interval = {
            k: [round(x / v["b00"]["rmse"], 5) for x in v[best]["delta95"]]
            if "b00" in v and v["b00"].get("rmse")
            else None
            for k, v in periods.items()
        }
        rows = {}
        for t in config["D2"]["phaseBGrid"]:
            candidate = best if rel["development"] <= -t else "b00"
            decision = wf.decide(
                candidate, rel["development"], rel["validation"], rel["holdout"], t
            )
            rows[f"{t:.4f}"] = {
                "candidate": candidate,
                "label": decision["label"],
                "periodsMeeting": sum(decision["meetsMinimum"].values()),
            }
        phase_b[position] = {
            "bestDvp": best,
            "relativeChange": rel,
            "relative95": interval,
            "allPeriodsImprove": all(v < 0 for v in rel.values()),
            "byThreshold": rows,
        }
    periods = sit["periods"]
    phase_c = {}
    for t in config["D2"]["phaseCGrid"]:
        label, reason = decisions.decide(periods, t)
        phase_c[f"{t:.1f}"] = {"label": label}
    joint = {
        f"B{tb:.4f}|C{tc:.1f}": {
            "phaseB": phase_b["DST"]["byThreshold"][f"{tb:.4f}"]["label"],
            "phaseC": phase_c[f"{tc:.1f}"]["label"],
        }
        for tb in config["D2"]["phaseBGrid"]
        for tc in config["D2"]["phaseCGrid"]
    }
    context = {
        k: {
            "deltaPp": v["deltaPp"],
            "netPoints": v["pointsFromChanges"]["total"],
            "perWeek95": v["pointsFromChanges"]["perWeek95"],
            "pairs": v["pairs"],
            "changedShare": v["changed"]["share"],
            "candidateRightWhenChanged": v["changed"]["candidateRightWhenChanged"],
        }
        for k, v in periods.items()
    }
    return {"phaseB": phase_b, "phaseC": {"DST": phase_c, "periods": context}, "jointDST": joint}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=RECEIPTS / "threshold-sensitivity-v1.json")
    args = parser.parse_args()
    d1_out, d2_out = d1(args.main.resolve()), d2()
    receipt: dict[str, Any] = {
        "format": "arbit-dvp-m3-3-threshold-sensitivity-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "config": {"path": "config/dvp/threshold-sensitivity-v1.json", "sha256": sha256(CONFIG)},
        "frozenThresholds": {"phaseBRelativeRmse": 0.01, "phaseCPp": 1.8},
        "D1": d1_out,
        "D2": d2_out,
        "classification": "DESCRIPTIVE: never used to choose a threshold; frozen rules unchanged",
        "write_to_production": False,
    }
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {
                "D1": d1_out["original"],
                "phaseB": {
                    p: v["byThreshold"]["0.0100"]["label"] for p, v in d2_out["phaseB"].items()
                },
            }
        )
    )


if __name__ == "__main__":
    main()
