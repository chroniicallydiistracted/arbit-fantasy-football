"""Pin the FFA 2026 league inputs M3-3 uses as immutable research inputs (final directive PB-AUD-08,
DEC-04).

Reads Arbit's stored league records once, read-only, and writes the minimum normalized inputs the
league-constrained research needs into a local, git-ignored bundle:
- transactions (every 2026 record, with its content hash and observation times);
- finalized lineup captures and entries;
- the draft, matchup results, team ids and the rules that apply (from the current league
  document and its rule version);
- every archived snapshot's time and hash, its rosters, and ESPN's reported state of every D/ST;
- the D/ST identity mapping to franchise codes.

The schedule and NFL observations come from the week-12 prospective archive's inputs, already
hash-pinned. A manifest with each file's SHA-256, row counts and source ancestry is written beside
the bundle and to docs/research/ffa-2026-league-inputs-v1.json (hashes and counts only: no names,
managers or member identifiers).

  uv run --env-file <main>/.env.local python scripts/model/ffa_2026_pin.py --main <main>
"""

import argparse
import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
SEASON = 2026
VERSION = "v1"
ESPN_TO_FRANCHISE = {"LAR": "LA", "WSH": "WAS"}
WEEK12 = "artifacts/dvp/prospective/2026/week-12"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame(rows: Sequence[Any]) -> pl.DataFrame:
    return pl.DataFrame([dict(r._mapping) for r in rows], infer_schema_length=None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--main", type=Path, default=ROOT)
    parser.add_argument(
        "--manifest", type=Path, default=ROOT / "docs/research/ffa-2026-league-inputs-v1.json"
    )
    args = parser.parse_args()
    main_root = args.main.resolve()
    out = main_root / f"artifacts/dvp/league-2026/inputs-{VERSION}"
    if out.exists():
        raise SystemExit(f"{out} exists; pinned inputs are never overwritten")
    staging = out.with_name(out.name + ".staging")
    staging.mkdir(parents=True)
    engine = create_engine(
        os.environ["ARBIT_DATABASE_URL"],
        hide_parameters=True,
        execution_options={"postgresql_readonly": True},
    )
    read_at = datetime.now(UTC)
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        current = c.execute(
            text(
                "select s.id, s.observed_at, s.content_hash, d.rules_hash, d.payload, "
                "r.payload as rules from league_snapshot s "
                "join current_snapshot c on c.snapshot_id = s.id "
                "join league_document d on d.snapshot_id = s.id "
                "join rule_version r on r.hash = d.rules_hash"
            )
        ).one()
        tables = {
            "transactions": frame(
                c.execute(
                    text(
                        "select espn_id, type, status, scoring_period, team_id::text as team, "
                        "proposed_at, processed_at, related_espn_id, items::text as items, "
                        "first_observed_at, last_changed_at, content_hash "
                        "from fantasy_transaction where season = :s order by espn_id"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "transaction_reads": frame(
                c.execute(
                    text(
                        "select scoring_period, last_read_at, transaction_count "
                        "from fantasy_transaction_read where season = :s order by 1"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "lineup_captures": frame(
                c.execute(
                    text(
                        "select id::text as capture_id, scoring_period, matchup_period, "
                        "captured_at, content_hash from fantasy_lineup_capture "
                        "where season = :s order by scoring_period, captured_at"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "lineup_entries": frame(
                c.execute(
                    text(
                        "select e.capture_id::text as capture_id, c.scoring_period, "
                        "e.team_id::text as team, e.player_id::text as player, e.slot, e.position, "
                        "e.official_points::float8 as official_points "
                        "from fantasy_lineup_entry e join fantasy_lineup_capture c "
                        "on c.id = e.capture_id where c.season = :s "
                        "order by c.scoring_period, e.team_id, e.player_id"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "snapshots": frame(
                c.execute(
                    text(
                        "select id::text as snapshot_id, observed_at, content_hash "
                        "from league_snapshot where season = :s order by observed_at"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "snapshot_rosters": frame(
                c.execute(
                    text(
                        "select r.snapshot_id::text as snapshot_id, r.team_id::text as team, "
                        "r.entity_id::text as player, r.slot from roster_entry r "
                        "join league_snapshot s on s.id = r.snapshot_id where s.season = :s "
                        "order by 1, 2, 3"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "snapshot_dst": frame(
                c.execute(
                    text(
                        "select s.id::text as snapshot_id, x->>'id' as unit, "
                        "x->>'availability' as availability, x->>'team_id' as team "
                        "from league_snapshot s join league_document d on d.snapshot_id = s.id, "
                        "jsonb_array_elements(d.payload->'players') x "
                        "where s.season = :s and x->>'kind' = 'defense_unit' order by 1, 2"
                    ),
                    {"s": SEASON},
                ).all()
            ),
            "dst": frame(
                c.execute(
                    text(
                        "select e.id::text as unit, n.abbreviation from canonical_entity e "
                        "join team_affiliation a on a.entity_id = e.id and a.valid_to is null "
                        "join nfl_team n on n.entity_id = a.team_id where e.kind = 'defense_unit' "
                        "order by 1"
                    )
                ).all()
            ),
        }
    tables["dst"] = tables["dst"].with_columns(
        pl.col("abbreviation").replace(ESPN_TO_FRANCHISE).alias("code")
    )
    document = current.payload
    policy = current.rules.get("provider_policy", {})
    league = {
        "snapshotId": str(current.id),
        "observedAt": current.observed_at.isoformat(),
        "contentHash": current.content_hash,
        "rulesHash": current.rules_hash,
        "teams": sorted(str(t["id"]) for t in document["teams"]),
        "draftPicks": [
            {"player": str(p["player_id"]), "team": str(p["team_id"])}
            for p in document["draft_picks"]
        ],
        "matchups": [
            {
                "scoringPeriods": m["scoring_periods"],
                "winner": m.get("winner"),
                "home": {
                    "team": str(m["home"]["team_id"]),
                    "officialPoints": m["home"].get("official_points"),
                },
                "away": {
                    "team": str(m["away"]["team_id"]),
                    "officialPoints": m["away"].get("official_points"),
                },
            }
            for m in document["matchups"]
        ],
        "rules": {
            "waiverHours": current.rules["waiver_hours"],
            "waiverType": current.rules["waiver_type"],
            "lineupLockType": current.rules["lineup_lock_type"],
            "lineupSlots": current.rules["lineup_slots"],
            "positionLimits": policy.get("rosterSettings", {}).get("positionLimits"),
            "isBenchUnlimited": policy.get("rosterSettings", {}).get("isBenchUnlimited"),
            "waiverProcessDays": policy.get("acquisitionSettings", {}).get("waiverProcessDays"),
            "waiverProcessHour": policy.get("acquisitionSettings", {}).get("waiverProcessHour"),
            "tradeDeadline": policy.get("tradeSettings", {}).get("deadlineDate"),
            "vetoVotesRequired": policy.get("tradeSettings", {}).get("vetoVotesRequired"),
        },
    }
    files: dict[str, dict[str, Any]] = {}
    for name, table in tables.items():
        path = staging / f"{name}.parquet"
        table.write_parquet(path)
        files[path.name] = {"sha256": sha256(path), "rows": table.height}
    path = staging / "league.json"
    path.write_text(json.dumps(league, indent=1, sort_keys=True) + "\n")
    files[path.name] = {"sha256": sha256(path), "draftPicks": len(league["draftPicks"])}
    week12 = main_root / WEEK12
    week12_manifest = json.loads((week12 / "manifest.json").read_text())
    for name, digest in week12_manifest["inputs"].items():
        if sha256(week12 / "inputs" / name) != digest:
            raise SystemExit(f"week-12 archived input {name} does not match its manifest")
    manifest = {
        "format": "arbit-ffa-2026-league-inputs-v1",
        "version": VERSION,
        "readAt": read_at.isoformat(),
        "readMode": "one read-only repeatable-read transaction",
        "bundle": f"artifacts/dvp/league-2026/inputs-{VERSION} (local, git-ignored)",
        "currentSnapshot": {
            k: league[k] for k in ("snapshotId", "observedAt", "contentHash", "rulesHash")
        },
        "files": files,
        "external": {
            "schedule and 2026 observations": {
                "path": f"{WEEK12}/inputs",
                "inputs": week12_manifest["inputs"],
            }
        },
        "ancestry": {
            "transactions": "fantasy_transaction (mTransactions2, every period read; one row per ESPN id, updated in place)",
            "lineups": "fantasy_lineup_capture/entry (finalized period lineups reconciled to ESPN totals)",
            "league.json": "current league_document (draft_picks, matchups, team ids) and its rule_version",
            "snapshots": "league_snapshot, roster_entry and each snapshot's league_document players (D/ST only)",
            "dst": "canonical_entity defense_unit -> team_affiliation -> nfl_team (LAR->LA, WSH->WAS)",
        },
        "privacy": "Local bundle only. This manifest holds hashes and counts; no names, managers or member identifiers.",
        "write_to_production": False,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    os.rename(staging, out)
    for item in out.iterdir():
        item.chmod(0o444)
    args.manifest.write_text(
        json.dumps(
            manifest | {"manifestSha256": sha256(out / "manifest.json")}, indent=1, sort_keys=True
        )
        + "\n"
    )
    print(json.dumps({"bundle": str(out), "files": {k: v.get("rows") for k, v in files.items()}}))


if __name__ == "__main__":
    main()
