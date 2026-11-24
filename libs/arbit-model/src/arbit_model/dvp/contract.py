"""The row-level data contract of DvP observations, enforced where they are used (owner audit AUD-04).

Admission (`provenance.admit`) checks a source's columns, its scoring hash and some row values when
it enters. A column that is allowed can still carry a value that isn't: a forbidden source type,
a generated row, another scoring hash, points on an invalid cell. This module checks every row's
lineage again at the forecasting and fitting boundary, so a frame that skipped admission, or was
altered after it, cannot be fit or forecast. It fails closed with a `LineageError`.

Checks per row:
- lineage present: `source_id`, `source_type`, `scoring_hash`, `observed_or_generated`,
  `finality_basis`, `available_at`, `kickoff` and the keys are never null;
- `source_type` is an actual FFA type and `observed_or_generated` is `observed`;
- `source_id` is an FFA target table, the D/ST one exactly for D/ST rows;
- `scoring_hash` is the configured rule set of that table;
- `finality_basis` is the declared rule;
- `status` is known; a valid cell has finite points, any other has none;
- availability comes after kickoff; `unit` is the orientation the position defines;
- keys are unique.
"""

from collections.abc import Mapping

import polars as pl

from arbit_model.dvp import observations as obs
from arbit_model.dvp.provenance import LineageError, SourceType

ACTUAL_TYPES = frozenset({SourceType.FFA_ACTUAL_FINAL.value, SourceType.FFA_ACTUAL_AS_OF.value})
SOURCE_OF = {"athlete": "ffa_targets.athlete", "defense": "ffa_targets.defense"}
STATUSES = frozenset(
    {obs.VALID, "missing_coverage", "invalid_refused_line", "invalid_duplicate_line"}
)
REQUIRED = (
    "game_id",
    "season",
    "week",
    "kickoff",
    "available_at",
    "position",
    "offense",
    "defense",
    "unit",
    "status",
    "source_id",
    "source_type",
    "scoring_hash",
    "observed_or_generated",
    "finality_basis",
)
KEYS = ("game_id", "offense", "position")


def violations(frame: pl.DataFrame, scoring: Mapping[str, str]) -> dict[str, int]:
    """Count of rows breaking each rule (empty when the frame keeps the contract)."""
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        return {f"missing column {c}": frame.height for c in missing}
    dst = pl.col("position") == obs.DST
    expected_source = (
        pl.when(dst).then(pl.lit(SOURCE_OF["defense"])).otherwise(pl.lit(SOURCE_OF["athlete"]))
    )
    expected_hash = (
        pl.when(dst).then(pl.lit(scoring["defense"])).otherwise(pl.lit(scoring["athlete"]))
    )
    valid = pl.col("status") == obs.VALID
    rules: dict[str, pl.Expr] = {
        "null lineage or key": pl.any_horizontal([pl.col(c).is_null() for c in REQUIRED]),
        "source_type is not an FFA actual": ~pl.col("source_type").is_in(list(ACTUAL_TYPES)),
        "row is not observed": pl.col("observed_or_generated") != "observed",
        "source_id is not this position's FFA table": pl.col("source_id") != expected_source,
        "scoring_hash is not the configured rules": pl.col("scoring_hash") != expected_hash,
        "finality_basis is not the declared rule": pl.col("finality_basis") != obs.FINALITY,
        "unknown status": ~pl.col("status").is_in(list(STATUSES)),
        "unknown position": ~pl.col("position").is_in(list(obs.POSITION_GROUPS)),
        "valid cell without finite points": valid
        & (pl.col("points").is_null() | ~pl.col("points").cast(pl.Float64).is_finite()),
        "invalid cell with points": ~valid & pl.col("points").is_not_null(),
        "available before kickoff": pl.col("available_at") <= pl.col("kickoff"),
        "unit does not follow the position": pl.col("unit")
        != pl.when(dst).then(pl.col("offense")).otherwise(pl.col("defense")),
        "a team faces itself": pl.col("offense") == pl.col("defense"),
    }
    if "points" not in frame.columns:
        return {"missing column points": frame.height}
    counts = frame.select(
        [rule.fill_null(True).sum().alias(name) for name, rule in rules.items()]
    ).row(0, named=True)
    out = {name: int(n) for name, n in counts.items() if n}
    duplicated = int(frame.select(KEYS).is_duplicated().sum())
    if duplicated:
        out["duplicate keys"] = duplicated
    return out


def enforce(frame: pl.DataFrame, scoring: Mapping[str, str]) -> pl.DataFrame:
    """The frame unchanged if every row keeps the contract; otherwise a LineageError."""
    found = violations(frame, scoring)
    if found:
        detail = "; ".join(f"{name}: {n}" for name, n in sorted(found.items()))
        raise LineageError("ROW_CONTRACT", detail)
    return frame
