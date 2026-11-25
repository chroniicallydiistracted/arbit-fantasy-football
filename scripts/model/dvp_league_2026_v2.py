"""C05L-2026-EXP v2: the corrected exploratory league-constrained D/ST evaluation, from pinned inputs.

Owner final directive PB-AUD-02 to -06 and -08. The rule is config/dvp/league-2026-exploratory-v2.json,
committed and pushed before this ran. Reads only the pinned league bundle
(artifacts/dvp/league-2026/inputs-v1, every file hash-checked against
docs/research/ffa-2026-league-inputs-v1.json) and the week-12 archive's hash-checked 2026 inputs:
never the live database. EXPLORATORY and RETROSPECTIVE; never a confirmation. v1
(league-2026-exploratory.json) is preserved and compared.

  POLARS_MAX_THREADS=2 ARBIT_NFLVERSE_PATH=<main>/data/nflverse uv run --env-file <main>/.env.local \\
    python scripts/model/dvp_league_2026_v2.py --main <main>

Writes docs/research/dvp/league-2026-exploratory-v2.json.
"""

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from arbit_model import ffa_history as fh
from arbit_model.dvp import league

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/dvp/league-2026-exploratory-v2.json"
PINNED = ROOT / "docs/research/ffa-2026-league-inputs-v1.json"
V1 = ROOT / "docs/research/dvp/league-2026-exploratory.json"
SEASON = 2026
CAPACITY = 16  # non-IR players: lineup slots less IR; never exceeded in 1,522 snapshots
DST_POSITION_LIMIT = "16"  # rosterSettings.positionLimits key for D/ST
VERIFY_WINDOW = timedelta(hours=6)
PROCESSING_DAYS = ("MONDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")
HOLDOUT_FROM = datetime(2026, 11, 22, tzinfo=UTC)
OBSERVED = {"free_agent": fh.FREE_AGENT, "waivers": fh.WAIVERS}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/model/{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_pinned(main: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """The pinned bundle, every file verified against the committed manifest."""
    committed = json.loads(PINNED.read_text())
    bundle = main / "artifacts/dvp/league-2026/inputs-v1"
    if sha256(bundle / "manifest.json") != committed["manifestSha256"]:
        raise SystemExit("BLOCKED: the pinned bundle's manifest differs from the committed one")
    data: dict[str, Any] = {}
    for name, meta in committed["files"].items():
        if sha256(bundle / name) != meta["sha256"]:
            raise SystemExit(f"BLOCKED: pinned {name} does not match its manifest")
        if name.endswith(".json"):
            data[name.split(".")[0]] = json.loads((bundle / name).read_text())
            continue
        table = pl.read_parquet(bundle / name)
        data[name.split(".")[0]] = table.with_columns(
            pl.col(c).dt.convert_time_zone("UTC")
            for c, t in table.schema.items()
            if isinstance(t, pl.Datetime) and t.time_zone is not None
        )
    return data, committed


def transactions(table: pl.DataFrame) -> list[dict[str, Any]]:
    out = []
    for r in table.iter_rows(named=True):
        out.append(r | {"items": json.loads(r["items"])})
    return out


def kickoffs_by_code(schedule: pl.DataFrame) -> dict[str, list[datetime]]:
    out: dict[str, list[datetime]] = {}
    for g in schedule.iter_rows(named=True):
        for side in ("home", "away"):
            out.setdefault(g[side], []).append(g["kickoff"])
    return {k: sorted(v) for k, v in out.items()}


def validate_availability(
    data: dict[str, Any],
    moves: list[fh.Move],
    hold: timedelta,
    moments: list[datetime],
    kickoffs: dict[str, list[datetime]],
    code: dict[str, str],
) -> dict[str, Any]:
    """Rule v2 and the v1 rule against ESPN's reported state of every unowned D/ST in every
    snapshot, at the snapshot's own time, with ownership from the same snapshot (PB-AUD-03)."""
    snapshots = data["snapshots"]
    owned = (
        data["snapshot_rosters"]
        .filter(pl.col("player").is_in(list(code)))
        .group_by("snapshot_id")
        .agg(pl.col("player"))
    )
    owned_by = dict(zip(owned.get_column("snapshot_id"), owned.get_column("player"), strict=True))
    reported = data["snapshot_dst"]
    by_snapshot: dict[str, dict[str, str]] = {}
    for r in reported.iter_rows(named=True):
        by_snapshot.setdefault(r["snapshot_id"], {})[r["unit"]] = r["availability"]
    unit_kickoffs = {u: kickoffs.get(c, []) for u, c in code.items()}
    wednesdays = [m for m in moments if m.astimezone(fh.PACIFIC).weekday() == 2]
    tables: dict[str, Counter[tuple[str, str]]] = {
        k: Counter() for k in ("design", "holdout", "decisionMoments")
    }
    old: dict[str, Counter[tuple[str, str]]] = {k: Counter() for k in tables}
    for snap in snapshots.iter_rows(named=True):
        at: datetime = snap["observed_at"]
        held = set(owned_by.get(snap["snapshot_id"], []))
        states = by_snapshot.get(snap["snapshot_id"], {})
        unowned = sorted(u for u in code if u not in held)
        rebuilt = fh.availability_v2(unowned, {}, moves, at, hold, moments, unit_kickoffs)
        legacy = fh.availability(unowned, {}, moves, at, hold)
        split = "design" if at < HOLDOUT_FROM else "holdout"
        last_wednesday = max((m for m in wednesdays if m <= at), default=None)
        upcoming = min((k for ks in unit_kickoffs.values() for k in ks if k > at), default=None)
        decision_moment = (
            last_wednesday is not None
            and upcoming is not None
            and not any(last_wednesday < k <= at for ks in unit_kickoffs.values() for k in ks)
        )
        for unit in unowned:
            seen = OBSERVED.get(str(states.get(unit)), "OTHER:" + str(states.get(unit)))
            pair = (seen, rebuilt[unit][0])
            tables[split][pair] += 1
            old[split][(seen, legacy[unit])] += 1
            if decision_moment:
                tables["decisionMoments"][pair] += 1
                old["decisionMoments"][(seen, legacy[unit])] += 1

    def summary(counts: Counter[tuple[str, str]]) -> dict[str, Any]:
        total = sum(counts.values())
        agree = sum(v for (o, r), v in counts.items() if o == r)
        false_claimable = counts[(fh.WAIVERS, fh.FREE_AGENT)]
        restrictive = sum(v for (o, r), v in counts.items() if o == fh.FREE_AGENT and r != o)
        uncertain = sum(v for (o, r), v in counts.items() if r == fh.UNCERTAIN)
        return {
            "unitMoments": total,
            "agreement": round(agree / total, 4) if total else None,
            "falseClaimable": false_claimable,
            "falseClaimableRate": round(false_claimable / total, 4) if total else None,
            "overRestrictive": restrictive,
            "uncertain": uncertain,
            "table": {f"observed {o} / rebuilt {r}": v for (o, r), v in sorted(counts.items())},
        }

    out: dict[str, Any] = {
        "ruleV2": {k: summary(v) for k, v in tables.items()},
        "ruleV1": {k: summary(v) for k, v in old.items()},
        "snapshots": {
            "design": int(snapshots.filter(pl.col("observed_at") < HOLDOUT_FROM).height),
            "holdout": int(snapshots.filter(pl.col("observed_at") >= HOLDOUT_FROM).height),
        },
    }
    holdout = out["ruleV2"]["holdout"]
    accepted = (
        holdout["unitMoments"] > 0
        and holdout["agreement"] >= 0.99
        and holdout["falseClaimableRate"] <= 0.01
    )
    out["acceptance"] = {
        "criterion": "holdout agreement >= 0.99 and false-claimable rate <= 0.01",
        "passed": accepted,
        "class": "RECONSTRUCTED" if accepted else "ESTIMATED",
    }
    return out


def verify_every_snapshot(
    draft: list[tuple[str, str]], moves: list[fh.Move], data: dict[str, Any]
) -> dict[str, Any]:
    """The replay at each snapshot's own observation time against that snapshot's rosters."""
    rosters = data["snapshot_rosters"].group_by("snapshot_id").agg("player", "team")
    held = {
        r["snapshot_id"]: dict(zip(r["player"], r["team"], strict=True))
        for r in rosters.iter_rows(named=True)
    }
    disagreements = []
    agreed = 0
    for snap in data["snapshots"].iter_rows(named=True):
        state = fh.replay(draft, moves, until=snap["observed_at"]).owners
        observed = held.get(snap["snapshot_id"], {})
        if state == observed:
            agreed += 1
        else:
            diff = {p for p in set(state) | set(observed) if state.get(p) != observed.get(p)}
            disagreements.append(
                {
                    "snapshot": snap["snapshot_id"],
                    "observedAt": snap["observed_at"].isoformat(),
                    "players": len(diff),
                }
            )
    return {
        "snapshots": data["snapshots"].height,
        "agree": agreed,
        "disagree": len(disagreements),
        "disagreements": disagreements[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/dvp/league-2026-exploratory-v2.json"
    )
    args = parser.parse_args()
    main_root = args.main.resolve()
    config = json.loads(CONFIG.read_text())
    weeks: list[int] = config["weeks"]
    base, candidate = config["models"]["baseline"], config["models"]["candidate"]
    v1_script = script("dvp_league_2026")
    h = script("dvp_prospective")
    inventory = script("ffa_2026_inventory")
    fz = h.load_frozen()
    frame, season_rows, lineage = v1_script.forecasts(h, fz, main_root, weeks)
    data, pinned = load_pinned(main_root)
    league_doc = data["league"]
    rules = league_doc["rules"]
    hold = timedelta(hours=int(rules["waiverHours"]))
    dst_limit = int(rules["positionLimits"][DST_POSITION_LIMIT])
    code = dict(zip(data["dst"].get_column("unit"), data["dst"].get_column("code"), strict=True))
    unit_of = {c: u for u, c in code.items()}

    # Ownership: validated draft, fail-closed moves, every period and every snapshot.
    draft = [(p["player"], p["team"]) for p in league_doc["draftPicks"]]
    problems = fh.validate_draft(draft, league_doc["teams"])
    if problems:
        raise SystemExit("BLOCKED: draft: " + "; ".join(problems))
    moves = fh.moves(transactions(data["transactions"]))
    captures = data["lineup_captures"].sort("captured_at").group_by("scoring_period").last()
    latest = dict(
        zip(captures.get_column("scoring_period"), captures.get_column("capture_id"), strict=True)
    )
    entries = data["lineup_entries"]
    captured = {
        int(p): {
            (r["player"], r["team"])
            for r in entries.filter(pl.col("capture_id") == cid).iter_rows(named=True)
        }
        for p, cid in latest.items()
    }
    periods = fh.verify_periods(draft, moves, captured)
    if not all(periods[w]["verified"] for w in weeks):
        raise SystemExit("BLOCKED: the replay does not reproduce every captured period roster")
    snapshot_check = verify_every_snapshot(draft, moves, data)

    archive = main_root / "artifacts/dvp/prospective/2026/week-12/inputs"
    schedule = pl.read_parquet(archive / "schedule-season.parquet")
    cut = inventory.cutoffs(schedule)
    kickoffs = kickoffs_by_code(schedule)
    first = min(m.when for m in moves).date() - timedelta(days=7)
    moments = fh.processing_moments(first, datetime(2027, 1, 20).date(), PROCESSING_DAYS)
    validation = validate_availability(data, moves, hold, moments, kickoffs, code)
    rebuilt_class = validation["acceptance"]["class"]

    snapshots = data["snapshots"]
    reported = data["snapshot_dst"]
    dst = frame.filter(pl.col("position") == "DST")
    labels = season_rows.filter((pl.col("position") == "DST") & (pl.col("status") == "valid"))
    canonical = {
        (int(r["week"]), r["defense"]): float(r["points"]) for r in labels.iter_rows(named=True)
    }
    kinds = ("start", "streamClaimable", "streamWithWaivers", "unownedPool")
    rows: dict[str, list[dict[str, Any]]] = {k: [] for k in kinds}
    availability_at_cutoff: dict[str, Any] = {}
    for week in weeks:
        cutoff = cut[week]
        week_forecasts = dst.filter(pl.col("week") == week)
        playing = set(week_forecasts.get_column("defense").to_list())
        forecasts = {
            m: dict(
                zip(week_forecasts.get_column("defense"), week_forecasts.get_column(m), strict=True)
            )
            for m in (base, candidate)
        }
        points = {u: p for (w, u), p in canonical.items() if w == week}
        rebuilt = fh.replay(draft, moves, until=cutoff)
        if rebuilt.problems:
            raise SystemExit(f"BLOCKED: replay problems at week {week}: {rebuilt.problems[:3]}")
        owners = rebuilt.owners
        unowned = [u for u in code if u not in owners]
        unit_kickoffs = {u: kickoffs.get(code[u], []) for u in code}
        states = fh.availability_v2(unowned, {}, moves, cutoff, hold, moments, unit_kickoffs)
        # VERIFIED: a snapshot within 6 hours before the cutoff with nothing in between.
        before = snapshots.filter(
            (pl.col("observed_at") < cutoff) & (pl.col("observed_at") >= cutoff - VERIFY_WINDOW)
        ).sort("observed_at")
        evidence: dict[str, Any] = {"cutoff": cutoff.isoformat(), "class": rebuilt_class}
        classes = {u: rebuilt_class for u in unowned}
        if before.height:
            snap = before.row(-1, named=True)
            between_moves = [
                m for m in moves if snap["observed_at"] < m.when <= cutoff and m.player in code
            ]
            between_runs = [m for m in moments if snap["observed_at"] < m <= cutoff]
            if not between_moves and not between_runs:
                seen = {
                    r["unit"]: OBSERVED.get(str(r["availability"]))
                    for r in reported.filter(
                        pl.col("snapshot_id") == snap["snapshot_id"]
                    ).iter_rows(named=True)
                }
                for u in unowned:
                    if seen.get(u) is not None:
                        states[u] = (str(seen[u]), "observed in the snapshot")
                        classes[u] = "VERIFIED"
                evidence |= {
                    "class": "VERIFIED",
                    "snapshot": snap["snapshot_id"],
                    "snapshotObservedAt": snap["observed_at"].isoformat(),
                    "minutesBeforeCutoff": round(
                        (cutoff - snap["observed_at"]).total_seconds() / 60, 1
                    ),
                }
            else:
                evidence["nearestSnapshotNotUsed"] = {
                    "observedAt": snap["observed_at"].isoformat(),
                    "movesBetween": len(between_moves),
                    "processingBetween": len(between_runs),
                }
        free = sorted(code[u] for u in unowned if states[u][0] == fh.FREE_AGENT)
        waivers = sorted(code[u] for u in unowned if states[u][0] == fh.WAIVERS)
        evidence |= {
            "owned": len(owners.keys() & set(code)),
            "freeAgents": len(free),
            "waivers": len(waivers),
            "states": {
                code[u]: [states[u][0], classes[u], states[u][1]]
                for u in sorted(unowned, key=lambda x: code[x])
            },
        }
        availability_at_cutoff[str(week)] = evidence
        holdings: dict[str, list[str]] = {t: [] for t in league_doc["teams"]}
        roster_size: dict[str, int] = {t: 0 for t in league_doc["teams"]}
        for player, team in owners.items():
            roster_size[team] = roster_size.get(team, 0) + 1
            if player in code:
                holdings.setdefault(team, []).append(code[player])
        # IR: count only non-IR players against capacity (the captured lineup's IR slot).
        cid = latest.get(week)
        ir = Counter(
            r["team"]
            for r in entries.filter(
                (pl.col("capture_id") == cid) & (pl.col("slot") == "IR")
            ).iter_rows(named=True)
        )
        starters = {
            r["team"]: code.get(r["player"])
            for r in entries.filter(
                (pl.col("capture_id") == cid) & (pl.col("slot") == "DST")
            ).iter_rows(named=True)
        }
        pools = {
            "start": ([], league.START),
            "streamClaimable": (free, league.STREAM),
            "streamWithWaivers": (free + waivers, league.STREAM),
            "unownedPool": (sorted(code[u] for u in unowned), league.STREAM),
        }
        for kind, (pool, decision) in pools.items():
            decided = league.decide(week, holdings, pool, playing, forecasts, points, decision)
            skipped = league.without_decision(holdings, pool, playing, decision)
            for r in decided:
                team = r["team"]
                held = sorted(u for u in holdings[team] if u in playing)
                options = (
                    held if decision == league.START else sorted(set(held) | (set(pool) & playing))
                )
                starter = starters.get(team)
                r |= {
                    "decisionTime": cutoff.isoformat(),
                    "held": sorted(holdings[team]),
                    "optionUnits": options,
                    "optionEvidence": {
                        u: ("HELD", "on the roster at the cutoff")
                        if u in held
                        else (states[unit_of[u]][0], classes[unit_of[u]])
                        for u in options
                    },
                    "actualStarter": starter,
                    "starterAmongOptions": starter in options,
                    "starterHeldAtCutoff": starter in holdings[team],
                }
                for model in (base, candidate):
                    pick = r[f"pick_{model}"]
                    r[f"feasibility_{model}"] = league.feasibility(
                        pick,
                        holdings[team],
                        roster_size[team] - ir.get(team, 0),
                        CAPACITY,
                        dst_limit,
                    )
                    unit = unit_of[pick]
                    kick = min((k for k in kickoffs.get(pick, []) if k >= cutoff), default=None)
                    at_game = fh.replay(draft, moves, until=kick).owners.get(unit) if kick else None
                    r[f"ownerAtGame_{model}"] = (
                        "this team"
                        if at_game == team
                        else ("another team" if at_game else "nobody")
                    )
            rows[kind] += decided
            for team, reason in skipped.items():
                rows.setdefault(f"{kind}Skipped", []).append(
                    {"week": week, "team": team, "reason": reason}
                )

    tables = {k: pl.DataFrame(rows[k]) for k in kinds}
    reps, seed = 2000, 1729
    results = {
        k: league.summarize(t, base, candidate, reps, seed, weeks=weeks) for k, t in tables.items()
    }
    v1_method = {
        k: league.summarize(t, base, candidate, reps, seed, blocks=league.CHANGED_WEEKS)
        for k, t in tables.items()
    }
    feasibility = {
        k: {m: dict(Counter(r[f"feasibility_{m}"] for r in rows[k])) for m in (base, candidate)}
        for k in kinds
        if k != "start"
    }
    collision = {
        k: {m: league.collisions(rows[k], m) for m in (base, candidate)}
        for k in kinds
        if k != "start"
    }
    starts = rows["start"]
    comparable = [r for r in starts if r["starterAmongOptions"] and r["labelled"]]
    other = [r for r in starts if not r["starterAmongOptions"]]

    def manager_summary(part: list[dict[str, Any]]) -> dict[str, Any]:
        found = [(r, canonical.get((r["week"], r["actualStarter"]))) for r in part]
        scored: list[tuple[dict[str, Any], float]] = [(r, p) for r, p in found if p is not None]
        if not scored:
            return {"decisions": 0}
        return {
            "decisions": len(scored),
            "managerPoints": round(sum(p for _, p in scored), 2),
            "modelPoints": {
                m: round(sum(r[f"points_{m}"] or 0.0 for r, _ in scored), 2)
                for m in (base, candidate)
            },
            "managerHitRate": round(
                sum(abs(r["best"] - p) < 1e-9 for r, p in scored) / len(scored), 4
            ),
            "agreesWith": {
                m: round(
                    sum(r["actualStarter"] == r[f"pick_{m}"] for r, _ in scored) / len(scored), 4
                )
                for m in (base, candidate)
            },
        }

    lineups = pl.DataFrame(
        [
            {"week": w, "team": r["team"], "slot": r["slot"], "points": r["official_points"]}
            for w, cid in latest.items()
            if w in weeks
            for r in entries.filter(pl.col("capture_id") == cid).iter_rows(named=True)
            if r["player"] in code
        ]
    )
    matchups = league.matchup_effects_v2(
        starts, lineups, league_doc["matchups"], canonical, base, candidate
    )

    # v1 against v2: samples and outcomes.
    v1 = json.loads(V1.read_text())
    pairs = {
        "start": "start",
        "stream": "streamClaimable",
        "streamIncludingWaivers": "streamWithWaivers",
    }
    comparison: dict[str, Any] = {}
    for old_kind, new_kind in pairs.items():
        old_rows = {(r["week"], r["team"]): r for r in v1["decisions"][old_kind]}
        new_rows = {(r["week"], r["team"]): r for r in rows[new_kind]}
        changed_picks = [
            {
                "week": k[0],
                "team": k[1][:8],
                "v1": [old_rows[k][f"pick_{m}"] for m in (base, candidate)],
                "v2": [new_rows[k][f"pick_{m}"] for m in (base, candidate)],
                "v1Options": old_rows[k]["options"],
                "v2Options": new_rows[k]["options"],
            }
            for k in sorted(old_rows.keys() & new_rows.keys())
            if any(old_rows[k][f"pick_{m}"] != new_rows[k][f"pick_{m}"] for m in (base, candidate))
            or old_rows[k]["options"] != new_rows[k]["options"]
        ]
        comparison[new_kind] = {
            "v1Kind": old_kind,
            "v1Decisions": len(old_rows),
            "v2Decisions": len(new_rows),
            "added": sorted([k[0], k[1][:8]] for k in new_rows.keys() - old_rows.keys()),
            "removed": sorted([k[0], k[1][:8]] for k in old_rows.keys() - new_rows.keys()),
            "sameTeamWeekDifferentOptionsOrPicks": changed_picks,
            "v1": {
                x: v1["results"][old_kind].get(x)
                for x in (
                    "changed",
                    "pointsFromChanges",
                    "pointsFromChanges95",
                    "candidateRightWhenChanged",
                )
            },
            "v2": {
                x: results[new_kind].get(x)
                for x in (
                    "changed",
                    "pointsFromChanges",
                    "pointsFromChanges95",
                    "candidateRightWhenChanged",
                )
            },
        }
    week_totals = {
        k: {
            str(w): round(
                sum(
                    (r[f"points_{candidate}"] or 0) - (r[f"points_{base}"] or 0)
                    for r in rows[k]
                    if r["week"] == w
                    and r["labelled"]
                    and r[f"pick_{base}"] != r[f"pick_{candidate}"]
                ),
                2,
            )
            for w in weeks
        }
        for k in kinds
    }
    receipt = {
        "format": "arbit-dvp-m3-3-league-2026-v2",
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": h.code_version(),
        "config": {"path": "config/dvp/league-2026-exploratory-v2.json", "sha256": sha256(CONFIG)},
        "classification": config["classification"],
        "pinnedInputs": {
            "manifest": "docs/research/ffa-2026-league-inputs-v1.json",
            "manifestSha256": pinned["manifestSha256"],
            "filesVerified": len(pinned["files"]),
            "liveDatabaseRead": False,
        },
        "frozen": fz.verification,
        "forecastLineage": lineage,
        "ownership": {
            "draftValid": True,
            "moves": len(moves),
            "failClosed": "no unsupported ownership change or waiver without a processing time",
            "periods": {str(w): periods[w] for w in weeks},
            "everySnapshot": snapshot_check,
        },
        "availabilityValidation": validation,
        "availabilityAtCutoff": availability_at_cutoff,
        "coverage": {
            k: {"decisions": len(rows[k]), "teamsWithoutDecision": len(rows.get(f"{k}Skipped", []))}
            for k in kinds
        },
        "results": results,
        "resultsV1Method": {k: v.get("pointsFromChanges95") for k, v in v1_method.items()},
        "weeklyPointsFromChanges": week_totals,
        "feasibility": feasibility,
        "collisions": collision,
        "managers": {
            "strictlyComparable": manager_summary(comparable),
            "differentDecisionTime": manager_summary(other),
            "differentDecisionTimeCount": len(other),
        },
        "matchups": matchups,
        "comparisonWithV1": comparison,
        "decisions": rows,
        "decisionRule": "none: descriptive and exploratory",
        "forbidden_vendor_projection_dependencies": 0,
        "write_to_production": False,
    }
    args.out.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {
                k: {
                    x: results[k].get(x)
                    for x in ("decisions", "changed", "pointsFromChanges", "pointsFromChanges95")
                }
                for k in kinds
            }
        )
    )


if __name__ == "__main__":
    main()
