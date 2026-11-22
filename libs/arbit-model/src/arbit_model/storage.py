"""Versioned analytical tables for the Model: Parquet and a JSON manifest, content-addressed
(ADR-002). Unknown values stay null with a reason; nothing is filled in."""

import io
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.nflverse.objects import ObjectRef, ObjectStore

from arbit_model.targets import Participation, Target

DECIMAL = pa.decimal128(18, 6)
PAIR = pa.struct([("metric", pa.string()), ("value", pa.string())])
CONTRIBUTION = pa.struct([("rule_id", pa.string()), ("stat_id", pa.string()), ("points", DECIMAL)])
KEYS = [
    ("season", pa.int16()),
    ("week", pa.int16()),
    ("season_type", pa.string()),
    ("game_id", pa.string()),
    ("team", pa.string()),
    ("opponent", pa.string()),
    ("player_id", pa.string()),
    ("position", pa.string()),
    ("game_position", pa.string()),
    ("basis", pa.string()),
    ("participation", pa.string()),
    ("points", DECIMAL),
    ("refusal", pa.string()),
]


def default_sources(rows: Sequence[Target]) -> dict[str, str]:
    """The most common source of each metric; rows record only where theirs differs."""
    counts: dict[str, Counter[str]] = {}
    for target in rows:
        for metric, source in target.line.sources.items():
            counts.setdefault(metric, Counter())[source] += 1
    return {metric: c.most_common(1)[0][0] for metric, c in sorted(counts.items())}


def target_table(
    rows: Sequence[Target],
    metrics: Sequence[str],
    labels: Mapping[tuple[str, str], str],
    sources: Mapping[str, str],
) -> pa.Table:
    schema = pa.schema(
        KEYS
        + [(metric, DECIMAL) for metric in metrics]
        + [
            ("unknown", pa.list_(PAIR)),
            ("source_overrides", pa.list_(PAIR)),
            ("contributions", pa.list_(CONTRIBUTION)),
        ]
    )
    columns: dict[str, list[Any]] = {name: [] for name in schema.names}
    for t in rows:
        values = t.line.line.values
        if set(values) != set(metrics):
            raise ValueError("TARGET_METRICS_MISMATCH")
        record: dict[str, Any] = {
            "season": t.season,
            "week": t.week,
            "season_type": t.season_type,
            "game_id": t.game_id,
            "team": t.team,
            "opponent": t.opponent,
            "player_id": t.player_id,
            "position": t.position,
            "game_position": t.game_position,
            "basis": t.basis,
            "participation": labels.get((t.game_id, t.player_id)) if t.player_id else None,
            "points": t.points,
            "refusal": t.refusal,
            "unknown": [{"metric": m, "value": r} for m, r in sorted(t.line.unknown.items())],
            "source_overrides": [
                {"metric": m, "value": s}
                for m, s in sorted(t.line.sources.items())
                if sources.get(m) != s
            ],
            "contributions": [
                {"rule_id": r, "stat_id": s, "points": p} for r, s, p in t.contributions
            ],
        }
        for metric in metrics:
            record[metric] = values[metric]
        for name in schema.names:
            columns[name].append(record[name])
    return pa.table(columns, schema=schema)


def participation_table(labels: Sequence[Participation]) -> pa.Table:
    schema = pa.schema(
        [
            ("season", pa.int16()),
            ("week", pa.int16()),
            ("season_type", pa.string()),
            ("game_id", pa.string()),
            ("team", pa.string()),
            ("player_id", pa.string()),
            ("label", pa.string()),
            ("evidence", pa.string()),
            ("roster_status", pa.string()),
            ("position", pa.string()),
            ("offense_snaps", pa.float64()),
            ("defense_snaps", pa.float64()),
            ("st_snaps", pa.float64()),
        ]
    )
    return pa.table(
        {name: [getattr(p, name) for p in labels] for name in schema.names}, schema=schema
    )


def write_parquet(store: ObjectStore, table: pa.Table) -> ObjectRef:
    buffer = io.BytesIO()
    pq.write_table(table, buffer, compression="zstd")
    data = buffer.getvalue()
    return store.write((data,), expected_size=len(data))


def read_table(store: ObjectStore, digest: str) -> pa.Table:
    return pq.read_table(store.verify(digest).path)
