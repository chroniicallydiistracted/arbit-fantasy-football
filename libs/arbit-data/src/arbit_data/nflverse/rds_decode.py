"""Resource-limited data-only RDS decoding; nested histories stay explicit JSON fields."""

import json
import math
import os
import resource
import sys
from datetime import date, datetime
from typing import Any


def nested_value(value: Any, depth: int = 0) -> Any:
    import numpy as np
    import pandas as pd  # type: ignore[import-untyped]

    if depth > 24:
        raise ValueError("RDS_NESTING_LIMIT")
    if value is None or value is pd.NA or value is pd.NaT or value is np.ma.masked:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else None
    if isinstance(value, np.generic):
        return nested_value(value.item(), depth + 1)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return {
            "type": "data_frame",
            "columns": [str(c) for c in value.columns],
            "dtypes": [str(v) for v in value.dtypes],
            "index": nested_value(value.index.tolist(), depth + 1),
            "rows": [
                [nested_value(v, depth + 1) for v in row]
                for row in value.itertuples(index=False, name=None)
            ],
        }
    if isinstance(value, pd.Series):
        return {"type": "series", "values": nested_value(value.tolist(), depth + 1)}
    if isinstance(value, np.ndarray):
        return {
            "type": "array",
            "shape": list(value.shape),
            "values": nested_value(value.tolist(), depth + 1),
        }
    if isinstance(value, dict):
        return {str(k): nested_value(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [nested_value(v, depth + 1) for v in value]
    raise ValueError("RDS_UNSUPPORTED_VALUE")


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    import pyreadr  # type: ignore[import-untyped]

    try:
        result = pyreadr.read_r(sys.argv[1], output_format="polars")
        if len(result) != 1:
            raise ValueError("RDS_NOT_TABULAR")
        frame = next(iter(result.values()))
        if not hasattr(frame, "write_parquet") or frame.height > 5_000_000 or frame.width > 1024:
            raise ValueError("RDS_NOT_TABULAR")
        frame.write_parquet(sys.argv[2], compression="zstd")
    except pyreadr.LibrdataError:
        import warnings

        import pandas as pd
        import pyarrow as pa  # type: ignore[import-untyped]
        import pyarrow.parquet as pq  # type: ignore[import-untyped]
        import rdata

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Missing constructor for R class")
            frame = rdata.read_rds(sys.argv[1])
        if (
            not isinstance(frame, pd.DataFrame)
            or len(frame) > 5_000_000
            or len(frame.columns) > 1024
        ):
            raise ValueError("RDS_NOT_TABULAR") from None
        encoded = []
        for name in frame.columns:
            if any(
                isinstance(v, (pd.DataFrame, pd.Series, dict, list, tuple))
                or hasattr(v, "shape")
                and getattr(v, "ndim", 0) > 0
                for v in frame[name]
            ):
                frame[name] = [
                    None
                    if v is None or v is pd.NA
                    else json.dumps(
                        nested_value(v), sort_keys=True, separators=(",", ":"), allow_nan=False
                    )
                    for v in frame[name]
                ]
                encoded.append(str(name))
        table = pa.Table.from_pandas(frame, preserve_index=False)
        table = table.replace_schema_metadata(
            {
                **(table.schema.metadata or {}),
                b"arbit:nested_json_columns": json.dumps(encoded).encode(),
            }
        )
        pq.write_table(table, sys.argv[2], compression="zstd")
    os.chmod(sys.argv[2], 0o600)


if __name__ == "__main__":
    main()
