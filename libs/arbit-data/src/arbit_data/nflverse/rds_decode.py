"""Resource-limited data-only RDS decoder. Never evaluates R code or unpacks model ZIPs."""

import os
import resource
import sys


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    import pyreadr  # type: ignore[import-untyped]

    result = pyreadr.read_r(sys.argv[1], output_format="polars")
    if len(result) != 1:
        raise ValueError("RDS_NOT_TABULAR")
    frame = next(iter(result.values()))
    if not hasattr(frame, "write_parquet") or frame.height > 5_000_000 or frame.width > 1024:
        raise ValueError("RDS_NOT_TABULAR")
    frame.write_parquet(sys.argv[2], compression="zstd")
    os.chmod(sys.argv[2], 0o600)


if __name__ == "__main__":
    main()
