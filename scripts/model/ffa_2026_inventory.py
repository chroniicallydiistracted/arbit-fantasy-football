"""FFA 2026 data inventory: capabilities, coverage by scoring period, validation, ownership replay.

Owner audit Phase B (B1-B5; docs/research/dvp/AUDIT_REMEDIATION_AND_COMPLETION_REQUIREMENTS_PHASE-B.md).
2026 is FFA's inaugural season (OWN-076), so the inventory covers 2026 only.

Reads the database read-only. With `--live` it also re-verifies through the existing guarded ESPN
integration, storing nothing:
- `scoring_audit.audit_scoring` reconciles each finished period's lineups with Arbit's scorer;
- `league_history.fetch_transactions` re-reads each period's transactions to compare with the
  stored ones.
Writes docs/research/ffa-2026-inventory.json.

  uv run --env-file <main>/.env.local python scripts/model/ffa_2026_inventory.py --main <main> [--live]
"""

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl
from arbit_model import ffa_history as fh
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
SEASON = 2026
FORMAT = "arbit-ffa-2026-inventory-v1"
ESPN_TO_FRANCHISE = {"LAR": "LA", "WSH": "WAS"}
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "DST": 1, "K": 1}
FLEX_POSITIONS = {"RB", "WR", "TE"}


def rows(c: Any, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in c.execute(text(sql), params)]


def code_version() -> str:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", ".", ":(exclude)docs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return head + ("+uncommitted" if dirty else "")


def load(engine: Any) -> dict[str, Any]:
    with engine.connect() as c:
        current = c.execute(
            text(
                "select s.id, s.observed_at, d.payload, r.payload as rules from league_snapshot s "
                "join current_snapshot c on c.snapshot_id = s.id "
                "join league_document d on d.snapshot_id = s.id "
                "join rule_version r on r.hash = d.rules_hash"
            )
        ).one()
        return {
            "current": current,
            "captures": rows(
                c,
                "select id::text, scoring_period, matchup_period, captured_at, content_hash, "
                "verification from fantasy_lineup_capture where season = :s order by scoring_period, "
                "captured_at",
                s=SEASON,
            ),
            "entries": rows(
                c,
                "select c.scoring_period, c.id::text capture_id, e.team_id::text team, "
                "e.player_id::text player, e.slot, e.position, e.official_points from "
                "fantasy_lineup_capture c join fantasy_lineup_entry e on e.capture_id = c.id where "
                "c.season = :s",
                s=SEASON,
            ),
            "transactions": rows(
                c,
                "select espn_id, type, status, scoring_period, team_id::text team, proposed_at, "
                "processed_at, related_espn_id, items, first_observed_at, last_changed_at, "
                "content_hash from fantasy_transaction where season = :s",
                s=SEASON,
            ),
            "reads": rows(
                c,
                "select scoring_period, last_read_at, transaction_count from fantasy_transaction_read "
                "where season = :s order by 1",
                s=SEASON,
            ),
            "snapshots": rows(
                c,
                "select id::text, observed_at from league_snapshot where season = :s order by observed_at",
                s=SEASON,
            ),
            "dst": rows(
                c,
                "select e.id::text entity, n.abbreviation from canonical_entity e join team_affiliation a "
                "on a.entity_id = e.id and a.valid_to is null join nfl_team n on n.entity_id = a.team_id "
                "where e.kind = 'defense_unit'",
            ),
            "health": rows(
                c,
                "select source, last_success_at, consecutive_failures, error_code from source_health "
                "where source like 'espn%' order by 1",
            ),
        }


def snapshot_owners(
    engine: Any, snapshot_id: str
) -> tuple[datetime, dict[str, str], dict[str, str]]:
    """Owners and availability states in one archived snapshot (its league document)."""
    with engine.connect() as c:
        row = c.execute(
            text(
                "select s.observed_at, d.payload from league_snapshot s join league_document d on "
                "d.snapshot_id = s.id where s.id = :i"
            ),
            {"i": snapshot_id},
        ).one()
    players = row.payload["players"]
    owners = {p["id"]: p["team_id"] for p in players if p.get("team_id")}
    status = {p["id"]: p.get("availability") for p in players}
    return row.observed_at, owners, status


def gap_days(days: Counter[str]) -> list[str]:
    """Calendar days between the first and last snapshot with no snapshot at all."""
    first, last = datetime.fromisoformat(min(days)), datetime.fromisoformat(max(days))
    span = (first + timedelta(days=i) for i in range((last - first).days + 1))
    return [d.date().isoformat() for d in span if d.date().isoformat() not in days]


def cutoffs(schedule: pl.DataFrame) -> dict[int, datetime]:
    first = schedule.group_by("week").agg(pl.col("kickoff").min()).sort("week")
    return {int(w): k for w, k in first.iter_rows()}


def lineup_checks(
    data: dict[str, Any], matchups: list[dict[str, Any]], slots: dict[str, int]
) -> dict[str, Any]:
    """Per finished period: identity, slot structure, flex eligibility and starter totals against
    the official matchup totals."""
    latest: dict[int, str] = {}
    for cap in data["captures"]:
        latest[cap["scoring_period"]] = cap["id"]
    official: dict[tuple[int, str], Decimal] = {}
    for m in matchups:
        if len(m["scoring_periods"]) != 1:
            continue
        for side in ("home", "away"):
            s = m.get(side)
            if s and s.get("official_points") is not None and m.get("winner"):
                official[(m["scoring_periods"][0], s["team_id"])] = Decimal(s["official_points"])
    out: dict[str, Any] = {}
    for period, capture in sorted(latest.items()):
        entries = [e for e in data["entries"] if e["capture_id"] == capture]
        teams: dict[str, list[dict[str, Any]]] = {}
        for e in entries:
            teams.setdefault(e["team"], []).append(e)
        problems: list[str] = []
        totals_equal = 0
        for team, roster in teams.items():
            counts = Counter(e["slot"] for e in roster)
            for slot, n in STARTERS.items():
                if counts.get(slot, 0) > n:
                    problems.append(f"{team[:8]} has {counts[slot]} {slot}")
            if counts.get("BENCH", 0) > slots.get("BENCH", 7) + 0 or counts.get(
                "IR", 0
            ) > slots.get("IR", 1):
                problems.append(f"{team[:8]} bench or IR over limit")
            for e in roster:
                if e["slot"] == "FLEX" and e["position"] not in FLEX_POSITIONS:
                    problems.append(f"{team[:8]} FLEX holds {e['position']}")
                if e["slot"] not in ("BENCH", "IR", "FLEX") and e["slot"] != e["position"]:
                    problems.append(f"{team[:8]} {e['position']} in {e['slot']}")
            starters = sum(
                (
                    Decimal(e["official_points"])
                    for e in roster
                    if e["slot"] not in ("BENCH", "IR") and e["official_points"] is not None
                ),
                Decimal(0),
            )
            if official.get((period, team)) == starters.quantize(Decimal("0.01")):
                totals_equal += 1
        captures = [c for c in data["captures"] if c["scoring_period"] == period]
        out[str(period)] = {
            "captures": len(captures),
            "capturedAt": str(captures[-1]["captured_at"]),
            "matchupPeriodEqualsScoringPeriod": captures[-1]["matchup_period"] == period,
            "teams": len(teams),
            "entries": len(entries),
            "slots": dict(sorted(Counter(e["slot"] for e in entries).items())),
            "starterTotalsEqualOfficial": totals_equal,
            "storedVerification": captures[-1]["verification"],
            "problems": problems,
        }
    return out


def transaction_checks(data: dict[str, Any]) -> dict[str, Any]:
    tx = data["transactions"]
    matrix = Counter((t["type"], t["status"]) for t in tx)
    executed_trades = [
        t
        for t in tx
        if "TRADE" in t["type"] and t["status"] == "EXECUTED" and t["type"] != "TRADE_DECLINE"
    ]
    signature = Counter(
        (t["type"], t["status"], str(t["proposed_at"]), json.dumps(t["items"], sort_keys=True))
        for t in tx
    )
    return {
        "records": len(tx),
        "uniqueEspnIds": len({t["espn_id"] for t in tx}),
        "byTypeAndStatus": {f"{a}/{b}": n for (a, b), n in sorted(matrix.items())},
        "completedTrades": len(executed_trades),
        "tradeProposals": sum(t["type"] == "TRADE_PROPOSAL" for t in tx),
        "tradeDeclines": sum(t["type"] == "TRADE_DECLINE" for t in tx),
        "waiverClaims": {
            s: sum(t["type"] == "WAIVER" and t["status"] == s for t in tx)
            for s in sorted({t["status"] for t in tx if t["type"] == "WAIVER"})
        },
        "freeAgentAdds": sum(
            t["type"] == "FREEAGENT"
            and t["status"] == "EXECUTED"
            and any(i["type"] == "ADD" for i in t["items"])
            for t in tx
        ),
        "drops": sum(
            1 for t in tx if t["status"] == "EXECUTED" for i in t["items"] if i["type"] == "DROP"
        ),
        "timestamps": {
            "proposed": sum(t["proposed_at"] is not None for t in tx),
            "processed": sum(t["processed_at"] is not None for t in tx),
            "processedExactlyOnDecidedWaiverClaims": all(
                (t["processed_at"] is not None)
                == (t["type"] == "WAIVER" and t["status"] != "CANCELED")
                for t in tx
            ),
            "firstObserved": sum(t["first_observed_at"] is not None for t in tx),
        },
        "duplicateContentUnderDifferentIds": sum(n - 1 for n in signature.values() if n > 1),
        "revisedAfterFirstObservation": sum(
            t["last_changed_at"] > t["first_observed_at"] for t in tx
        ),
        "storage": "One row per ESPN transaction id; a changed record is updated in place (content hash and "
        "last_changed_at), so earlier versions are not kept.",
    }


def _aliases(engine: Any, refs: set[Any]) -> dict[Any, Any]:
    """Native ESPN references to Arbit's canonical ids, read-only (resolve_native would create a
    missing identity; this reports it instead)."""
    if not refs:
        return {}
    with engine.connect() as c:
        rows = c.execute(
            text(
                "select provider, kind, scope, external_id, entity_id from entity_alias "
                "where valid_to is null"
            )
        ).all()
    found = {(r.provider, r.kind, r.scope, r.external_id): r.entity_id for r in rows}
    return {
        ref: found[(ref.provider, ref.entity_kind, ref.scope, ref.external_id)]
        for ref in refs
        if (ref.provider, ref.entity_kind, ref.scope, ref.external_id) in found
    }


def live_content_checks(
    engine: Any, data: dict[str, Any], periods: list[int], read_through: int
) -> dict[str, Any]:
    """Content-level re-verification through the existing guarded integration (final directive
    PB-AUD-01); nothing is stored.

    - Transactions: every period's page is read and the pages' union taken. Each live record is
      normalized exactly as Arbit stores it (league_history.store_transactions: type, status,
      period, team, proposed and processed times, related id, items with players, teams and
      slots) using read-only identity lookups, and its content hash compared with the stored
      one; a mismatch is compared field by field. Each stored record is positively located on a
      page.
    - Lineups: each finished period is read as the capture reads it, its rows built by the
      capture's own function and hashed, and compared with the stored capture's content hash
      (team, player, slot, points, name, position, NFL team of every starter, bench and IR
      entry)."""
    from arbit_data.espn.client import EspnClient
    from arbit_data.espn.endpoints import Endpoint, EndpointOptions
    from arbit_data.espn.normalize import native_ref
    from arbit_data.espn.transport import EspnTransport
    from arbit_data.league_history import (
        LINEUP_VIEWS,
        _hash,
        _items,
        _kind,
        _lineup_rows,
        _when,
        fetch_transactions,
    )

    client = EspnClient(EspnTransport())
    started = datetime.now(UTC)
    stored = {t["espn_id"]: t for t in data["transactions"]}
    union: dict[str, tuple[int, Any]] = {}
    pages: dict[str, Any] = {}
    located: dict[str, list[int]] = {}
    for period in range(1, read_through + 1):
        page, receipt = fetch_transactions(client, SEASON, period)
        pages[str(period)] = {"records": len(page.transactions), "receiptSha256": receipt}
        for t in page.transactions:
            union.setdefault(t.id, (period, t))
            located.setdefault(t.id, []).append(period)
    refs = set()
    for _, t in union.values():
        if t.team_id > 0:
            refs.add(native_ref("fantasy_team", t.team_id, SEASON))
        for item in t.items:
            if item.player_id != 0:
                refs.add(native_ref(_kind(item.player_id), item.player_id, SEASON))
            for team in (item.from_team_id, item.to_team_id):
                if team > 0:
                    refs.add(native_ref("fantasy_team", team, SEASON))
    ids = _aliases(engine, refs)
    unknown_identities = len(refs - set(ids))
    equal = 0
    differ: list[dict[str, Any]] = []
    unresolved = 0
    for espn_id, (_, t) in sorted(union.items()):
        if espn_id not in stored:
            continue
        try:
            values = {
                "scoring_period": t.scoring_period_id,
                "type": t.type,
                "status": t.status,
                "team_id": ids[native_ref("fantasy_team", t.team_id, SEASON)]
                if t.team_id > 0
                else None,
                "proposed_at": _when(t.proposed_date),
                "processed_at": _when(t.process_date),
                "related_espn_id": t.related_transaction_id,
                "items": _items(t, ids, SEASON),
            }
        except KeyError:
            unresolved += 1
            continue
        if _hash(values) == stored[espn_id]["content_hash"]:
            equal += 1
            continue
        mine = stored[espn_id]
        fields = [
            k
            for k in ("scoring_period", "type", "status", "proposed_at", "processed_at")
            if values[k] != mine[k]
        ]
        if json.loads(json.dumps(values["items"], default=str)) != mine["items"]:
            fields.append("items")
        differ.append({"espnId": espn_id, "type": t.type, "fields": fields})
    future = {i: located.get(i, []) for i, t in stored.items() if t["type"] == "FUTURE_ROSTER"}
    transactions = {
        "pagesRead": pages,
        "liveRecords": len(union),
        "storedRecords": len(stored),
        "contentEqual": equal,
        "contentDiffers": differ,
        "unresolvedIdentities": unresolved,
        "unknownIdentityRefs": unknown_identities,
        "liveNotStored": sorted(set(union) - set(stored)),
        "storedNotLive": sorted(set(stored) - set(union)),
        "futureRosterRecordsLocatedOnPages": future,
        "note": "A page also carries the next period's lineup moves (FUTURE_ROSTER); each record is "
        "located on the pages that returned it.",
    }
    captures = {}
    for cap in data["captures"]:
        captures[int(cap["scoring_period"])] = cap
    lineups: dict[str, Any] = {}
    for period in periods:
        cap = captures[period]
        response = client.fetch(
            Endpoint.LEAGUE,
            EndpointOptions(
                season=SEASON,
                views=LINEUP_VIEWS,
                scoring_period=period,
                matchup_period=int(cap["matchup_period"]),
            ),
        )
        if not isinstance(response.payload, dict):
            raise SystemExit(f"period {period}: the lineup read returned no league document")
        rows = _lineup_rows(response.payload, SEASON, period, int(cap["matchup_period"]))
        slots = Counter(r["slot"] for r in rows)
        equal = _hash(rows) == cap["content_hash"]
        lineups[str(period)] = {
            "liveEntries": len(rows),
            "slots": dict(sorted(slots.items())),
            "contentEqualToCapture": equal,
            "receiptSha256": response.receipt.sha256,
        }
        if not equal:
            lineups[str(period)]["fieldDifferences"] = _lineup_field_differences(
                engine, cap["id"], rows, native_ref, _kind
            )
    return {
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(UTC).isoformat(),
        "transactions": transactions,
        "lineups": lineups,
        "requests": read_through + len(periods),
    }


def _lineup_field_differences(
    engine: Any, capture_id: str, rows: list[dict[str, Any]], native_ref: Any, kind: Any
) -> dict[str, Any]:
    """Field by field: the live rows against the stored capture's entries. Membership, slot and
    points are the historical lineup; the display name and NFL team are read as of now (ESPN
    returns a player's current name and team even for a past period)."""
    with engine.connect() as c:
        stored = {
            (str(r.team_id), str(r.player_id)): r
            for r in c.execute(
                text(
                    "select team_id, player_id, slot, official_points, display_name, position, "
                    "nfl_team_espn_id from fantasy_lineup_entry where capture_id = :c"
                ),
                {"c": capture_id},
            )
        }
    refs = {native_ref("fantasy_team", r["team"], SEASON) for r in rows} | {
        native_ref(kind(r["player"]), r["player"], SEASON) for r in rows
    }
    ids = _aliases(engine, refs)
    live = {}
    for r in rows:
        team = ids.get(native_ref("fantasy_team", r["team"], SEASON))
        player = ids.get(native_ref(kind(r["player"]), r["player"], SEASON))
        live[(str(team), str(player))] = r
    diffs: Counter[str] = Counter()
    for key in live.keys() & stored.keys():
        a, b = live[key], stored[key]
        if a["slot"] != b.slot:
            diffs["slot"] += 1
        if (a["points"] is None) != (b.official_points is None) or (
            a["points"] is not None and Decimal(str(a["points"])) != Decimal(str(b.official_points))
        ):
            diffs["points"] += 1
        if a["position"] != b.position:
            diffs["position"] += 1
        if a["name"] != b.display_name:
            diffs["displayNameNow"] += 1
        if a["pro_team"] != b.nfl_team_espn_id:
            diffs["nflTeamNow"] += 1
    historical = (
        len(live.keys() - stored.keys())
        + len(stored.keys() - live.keys())
        + diffs["slot"]
        + diffs["points"]
        + diffs["position"]
    )
    return {
        "onlyLive": len(live.keys() - stored.keys()),
        "onlyStored": len(stored.keys() - live.keys()),
        "differences": dict(sorted(diffs.items())),
        "historicalLineupDiffers": historical > 0,
        "classification": "REVISION" if historical else "READ_TIME_REPRESENTATION_ONLY",
    }


def live_checks(data: dict[str, Any], periods: list[int]) -> dict[str, Any]:
    """Re-verify through the existing guarded integration; nothing is stored."""
    from arbit_data.espn.client import EspnClient
    from arbit_data.espn.scoring_audit import audit_scoring
    from arbit_data.espn.transport import EspnTransport
    from arbit_data.league_history import fetch_transactions

    client = EspnClient(EspnTransport())
    started = datetime.now(UTC)
    scoring = audit_scoring(client, SEASON, tuple(periods))
    stored: dict[int, dict[str, tuple[str, str]]] = {}
    for t in data["transactions"]:
        stored.setdefault(int(t["scoring_period"]), {})[t["espn_id"]] = (t["type"], t["status"])
    transactions: dict[str, Any] = {}
    for period in periods:
        page, receipt = fetch_transactions(client, SEASON, period)
        # A page also carries next week's lineup moves; compare records of this period only.
        live_here = {
            t.id: (t.type, t.status) for t in page.transactions if t.scoring_period_id == period
        }
        db_here = stored.get(period, {})
        transactions[str(period)] = {
            "live": len(live_here),
            "stored": len(db_here),
            "missingFromStore": sorted(set(live_here) - set(db_here))[:5],
            "missingFromStoreCount": len(set(live_here) - set(db_here)),
            "notInLive": len(set(db_here) - set(live_here)),
            "notInLiveTypes": dict(
                Counter(
                    t["type"]
                    for t in data["transactions"]
                    if t["espn_id"] in set(db_here) - set(live_here)
                )
            ),
            "statusChanged": sum(
                1 for i, v in live_here.items() if i in db_here and db_here[i] != v
            ),
            "receiptSha256": receipt,
        }
    return {
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(UTC).isoformat(),
        "scoring": {
            k: scoring.get(k) for k in ("success", "verificationPassed", "totals", "issues")
        }
        | {
            "periods": [
                {
                    k: p.get(k)
                    for k in (
                        "scoringPeriod",
                        "lineupsChecked",
                        "lineupsMatched",
                        "verifiedPlayerGames",
                        "mismatches",
                        "errors",
                    )
                }
                for p in scoring.get("periods", [])
            ]
        },
        "transactions": transactions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "docs/research/ffa-2026-inventory.json")
    parser.add_argument(
        "--content",
        type=Path,
        help="write only the content-level live re-verification (PB-AUD-01) to this receipt; the "
        "v1 inventory receipt is left as it is",
    )
    args = parser.parse_args()
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    data = load(engine)
    current = data["current"]
    document, rules = current.payload, current.rules
    matchups = document["matchups"]
    finished = sorted(
        {
            m["scoring_periods"][0]
            for m in matchups
            if m.get("winner") and len(m["scoring_periods"]) == 1
        }
    )
    schedule_path = (
        args.main / "artifacts/dvp/prospective/2026/week-12/inputs/schedule-season.parquet"
    )
    manifest = json.loads((schedule_path.parents[1] / "manifest.json").read_text())
    if (
        hashlib.sha256(schedule_path.read_bytes()).hexdigest()
        != manifest["inputs"]["schedule-season.parquet"]
    ):
        raise SystemExit("the archived 2026 schedule does not match its manifest")
    schedule = pl.read_parquet(schedule_path)
    cut = cutoffs(schedule)

    # Ownership replay, verified against every captured period roster.
    draft = [(p["player_id"], p["team_id"]) for p in document["draft_picks"]]
    all_moves = fh.moves(data["transactions"])
    latest_capture = {c["scoring_period"]: c["id"] for c in data["captures"]}
    captured = {
        p: {(e["player"], e["team"]) for e in data["entries"] if e["capture_id"] == cid}
        for p, cid in latest_capture.items()
    }
    verification = fh.verify_periods(draft, all_moves, captured)
    draft_tx = {
        i["player_id"] for t in data["transactions"] if t["type"] == "DRAFT" for i in t["items"]
    }

    # D/ST state at each week's preweek cutoff.
    dst_code = {
        r["entity"]: ESPN_TO_FRANCHISE.get(r["abbreviation"], r["abbreviation"])
        for r in data["dst"]
    }
    hold = timedelta(hours=int(rules["waiver_hours"]))
    dst_states: dict[str, Any] = {}
    for week in range(1, max(finished) + 2):
        if week not in cut:
            continue
        rebuilt = fh.replay(draft, all_moves, until=cut[week])
        states = fh.availability(dst_code, rebuilt.owners, all_moves, cut[week], hold)
        counts = Counter("OWNED" if s.startswith("OWNED") else s for s in states.values())
        snapshot_check: dict[str, Any] | None = None
        before = [s for s in data["snapshots"] if s["observed_at"] <= cut[week]]
        if before and cut[week] - before[-1]["observed_at"] <= timedelta(hours=24):
            seen_at, owners, _ = snapshot_owners(engine, before[-1]["id"])
            replay_then = fh.replay(draft, all_moves, until=seen_at)
            snapshot_check = {
                "snapshotObservedAt": seen_at.isoformat(),
                "hoursBeforeCutoff": round((cut[week] - seen_at).total_seconds() / 3600, 2),
                "dstOwnership": fh.snapshot_agreement(replay_then.owners, owners, dst_code),
                "allPlayers": fh.snapshot_agreement(
                    replay_then.owners, owners, set(owners) | set(replay_then.owners)
                ),
            }
        dst_states[str(week)] = {
            "cutoff": cut[week].isoformat(),
            "cutoffInTheFuture": cut[week] > datetime.now(UTC),
            "counts": dict(sorted(counts.items())),
            "replayProblems": len(rebuilt.problems),
            "snapshot": snapshot_check,
            "ownershipClass": "VERIFIED_BY_SNAPSHOT"
            if snapshot_check and snapshot_check["dstOwnership"]["disagree"] == 0
            else "RECONSTRUCTED",
        }

    days = Counter(s["observed_at"].date().isoformat() for s in data["snapshots"])
    # The replay at the time of the last snapshot of each day, against that snapshot's owners.
    daily: dict[str, Any] = {}
    last_of_day: dict[str, dict[str, Any]] = {}
    for snap in data["snapshots"]:
        last_of_day[snap["observed_at"].date().isoformat()] = snap
    for day, snap in sorted(last_of_day.items()):
        seen_at, owners, _ = snapshot_owners(engine, snap["id"])
        replay_then = fh.replay(draft, all_moves, until=seen_at)
        daily[day] = fh.snapshot_agreement(
            replay_then.owners, owners, set(owners) | set(replay_then.owners)
        ) | {"observedAt": seen_at.isoformat(), "replayProblems": len(replay_then.problems)}
    report: dict[str, Any] = {
        "format": FORMAT,
        "generatedAt": datetime.now(UTC).isoformat(),
        "code": code_version(),
        "season": SEASON,
        "ownerClarification": "OWN-076: 2026 is FFA's inaugural season; no FFA league history exists before it. "
        "Historical NFL seasons 2016-2025 are studied under the current FFA scoring rules.",
        "leagueState": {
            "currentScoringPeriod": document["scoring_period"],
            "currentMatchupPeriod": document["matchup_period"],
            "finishedScoringPeriods": finished,
            "matchups": len(matchups),
            "matchupsWithResults": sum(1 for m in matchups if m.get("winner")),
            "draftPicks": len(document["draft_picks"]),
            "draftPicksAgreeWithDraftTransactions": {p for p, _ in draft} == draft_tx,
            "currentSnapshot": str(current.observed_at),
        },
        "rules": {
            "lineupSlots": rules["lineup_slots"],
            "lineupLock": rules["lineup_lock_type"],
            "waiverType": rules["waiver_type"],
            "waiverHours": rules["waiver_hours"],
            "waiverProcessDays": rules["provider_policy"]["acquisitionSettings"][
                "waiverProcessDays"
            ],
            "acquisitionBudgetInUse": rules["provider_policy"]["acquisitionSettings"][
                "isUsingAcquisitionBudget"
            ],
            "tradeDeadline": datetime.fromtimestamp(
                rules["provider_policy"]["tradeSettings"]["deadlineDate"] / 1000, UTC
            ).isoformat(),
            "tradeVetoVotes": rules["provider_policy"]["tradeSettings"]["vetoVotesRequired"],
            "dstRosterLimit": rules["provider_policy"]["rosterSettings"]["positionLimits"].get(
                "16"
            ),
        },
        "lineups": lineup_checks(data, matchups, rules["lineup_slots"]),
        "transactions": transaction_checks(data),
        "transactionReads": {
            str(r["scoring_period"]): {
                "lastReadAt": str(r["last_read_at"]),
                "count": r["transaction_count"],
            }
            for r in data["reads"]
        },
        "snapshots": {
            "count": len(data["snapshots"]),
            "first": str(data["snapshots"][0]["observed_at"]),
            "last": str(data["snapshots"][-1]["observed_at"]),
            "byDay": dict(sorted(days.items())),
            "gapDays": gap_days(days),
        },
        "ownershipReplay": {
            "moves": len(all_moves),
            "byType": dict(Counter(f"{m.transaction_type}/{m.kind}" for m in all_moves)),
            "periods": {str(p): v for p, v in verification.items()},
            "allPeriodsVerified": all(v["verified"] for v in verification.values()),
            "dailySnapshots": daily,
            "allSnapshotsAgree": all(v["disagree"] == 0 for v in daily.values()),
        },
        "dstAtPreweekCutoff": dst_states,
        "sourceHealth": [{k: str(v) for k, v in h.items()} for h in data["health"]],
    }
    if args.content:
        read_through = max(int(r["scoring_period"]) for r in data["reads"])
        content = live_content_checks(engine, data, finished, read_through)
        tx = content["transactions"]
        receipt = {
            "format": "arbit-ffa-2026-inventory-content-v2",
            "generatedAt": datetime.now(UTC).isoformat(),
            "code": code_version(),
            "scope": f"transaction pages 1-{read_through}; finalized lineups of periods {finished}",
            "liveContent": content,
            "summary": {
                "transactionsContentEqual": tx["contentEqual"],
                "transactionsCompared": tx["contentEqual"] + len(tx["contentDiffers"]),
                "transactionsDiffering": len(tx["contentDiffers"]),
                "liveNotStored": len(tx["liveNotStored"]),
                "storedNotLive": len(tx["storedNotLive"]),
                "unresolvedIdentities": tx["unresolvedIdentities"],
                "lineupPeriodsEqual": sum(
                    v["contentEqualToCapture"] for v in content["lineups"].values()
                ),
                "lineupPeriodsWithHistoricalDifferences": sorted(
                    p
                    for p, v in content["lineups"].items()
                    if v.get("fieldDifferences", {}).get("historicalLineupDiffers")
                ),
                "lineupPeriods": len(content["lineups"]),
            },
            "stored": "nothing: read-only identity lookups, no writes",
        }
        args.content.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + "\n")
        print(json.dumps(receipt["summary"]))
        return
    if args.live:
        report["liveVerification"] = live_checks(data, finished)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n")
    print(
        json.dumps(
            {
                "finished": finished,
                "lineupPeriods": len(report["lineups"]),
                "replayVerified": report["ownershipReplay"]["allPeriodsVerified"],
                "live": "liveVerification" in report,
            }
        )
    )


if __name__ == "__main__":
    main()
