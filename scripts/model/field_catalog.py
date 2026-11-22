"""Check (or regenerate) the Model's nflverse field catalog against the imported manifests.

Check, the default, exits 1 if any field of any current nflverse manifest has no catalog entry,
or if the committed catalog no longer matches its rules. `--write` regenerates the committed
catalog from the current manifests and fails if a field matches no rule. Read-only against the
database and the nflverse object store.

  ARBIT_NFLVERSE_PATH=<main checkout>/data/nflverse uv run --env-file .env.local \\
    python scripts/model/field_catalog.py [--write]
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from arbit_data.nflverse.objects import ObjectStore
from arbit_data.schema import dataset_current, dataset_manifest
from arbit_model.fields import (
    Observation,
    build_catalog,
    catalog_family,
    classify,
    load_catalog,
    render,
    unclassified,
)
from sqlalchemy import create_engine, select

CATALOG = (
    Path(__file__).resolve().parents[2] / "libs/arbit-model/src/arbit_model/nflverse_fields.json"
)


def observations() -> tuple[list[Observation], dict[str, str | None]]:
    engine = create_engine(os.environ["ARBIT_DATABASE_URL"], hide_parameters=True)
    with engine.connect() as c:
        rows = (
            c.execute(
                select(
                    dataset_manifest.c.logical_key,
                    dataset_manifest.c.family,
                    dataset_manifest.c.payload,
                ).join(dataset_current, dataset_current.c.manifest_hash == dataset_manifest.c.hash)
            )
            .mappings()
            .all()
        )
    found = [
        Observation(
            family=row["family"],
            logical_key=row["logical_key"],
            columns=tuple((col["name"], col["type"]) for col in row["payload"]["columns"]),
            seasons=tuple(row["payload"]["coverage"].get("seasons") or ()),
            row_count=row["payload"]["row_count"],
            missing=row["payload"].get("missing") or {},
        )
        for row in rows
    ]
    parquet = {row["logical_key"]: row["payload"].get("parquet_hash") for row in rows}
    return found, parquet


def multi_season_first(
    found: list[Observation], parquet: dict[str, str | None], store: ObjectStore
) -> dict[tuple[str, str], int]:
    """First season with a value, for tables that span seasons and carry a season column."""
    first: dict[tuple[str, str], int] = {}
    for obs in found:
        names = [name for name, _ in obs.columns]
        digest = parquet.get(obs.logical_key)
        if len(obs.seasons) < 2 or "season" not in names or digest is None:
            continue
        family = catalog_family(obs.family, obs.logical_key)
        rule = classify(family, "season")
        if rule is not None and rule.use == "excluded":
            continue
        table = pq.read_table(store.verify(digest).path)
        seasons = pc.cast(table.column("season"), "int64", safe=False)
        for name in names:
            present = pc.and_(pc.is_valid(table.column(name)), pc.is_valid(seasons))
            low = pc.min(pc.filter(seasons, present)).as_py()
            if low is not None:
                first[(obs.logical_key, name)] = int(low)
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenerate the committed catalog")
    arguments = parser.parse_args()
    found, parquet = observations()
    if arguments.write:
        store = ObjectStore(
            Path(os.environ.get("ARBIT_NFLVERSE_PATH", "data/nflverse")) / "objects"
        )
        catalog = build_catalog(found, multi_season_first=multi_season_first(found, parquet, store))
        CATALOG.write_text(render(catalog))
        print(json.dumps(catalog["summary"], indent=1))
        return
    catalog = load_catalog()
    missing = unclassified(catalog, found)
    drift = [
        f"{family}.{name}"
        for family, entries in catalog["fields"].items()
        for name, entry in entries.items()
        if (rule := classify(family, name)) is None
        or (rule.id, rule.use) != (entry["rule"], entry["use"])
    ]
    report = {
        "manifests": len(found),
        "catalogued": catalog["summary"]["fields"],
        "unclassified": [f"{family}.{name}" for family, name in missing],
        "ruleDrift": drift,
    }
    print(json.dumps(report, indent=1))
    if missing or drift:
        sys.exit(1)


if __name__ == "__main__":
    main()
