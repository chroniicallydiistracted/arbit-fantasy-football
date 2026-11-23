"""Machine-readable M3-3 experiment records (spec §10; T40).

Every record carries the fields the specification lists. A record whose
`forbidden_vendor_projection_dependencies` is not zero is invalid whatever else it says: its status
becomes `INVALID` and its decision is withdrawn.
"""

from collections.abc import Iterable, Mapping
from typing import Any

WORKSTREAM = "M3-3"
STATUSES = frozenset(
    {"EXISTING", "REPRODUCED", "PLANNED", "EXECUTED", "PASSED", "FAILED", "BLOCKED", "INVALID"}
)
DECISIONS = frozenset({"PROMISING", "INCONCLUSIVE", "NOT_USEFUL", "BLOCKED"})
FIELDS = (
    "workstream_id",
    "experiment_id",
    "status",
    "hypothesis",
    "data_hash",
    "scoring_hash",
    "code_commit",
    "source_ancestry_hash",
    "forbidden_vendor_projection_dependencies",
    "actual_game_finality_policy",
    "as_of_policy",
    "train_validation_test_periods",
    "holdout_independence_status",
    "sample_count",
    "coverage_pct",
    "estimator",
    "parameters",
    "primary_metric",
    "baseline_metric",
    "absolute_delta",
    "relative_delta",
    "interval",
    "placebo_summary",
    "subgroups",
    "tests_passed",
    "limitations",
    "evidence_paths",
    "decision",
    "reason",
    "next_steps",
)


def record(experiment_id: str, status: str, **values: Any) -> dict[str, Any]:
    """A complete record: every specified field present (null when not applicable yet)."""
    unknown = set(values) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    if status not in STATUSES:
        raise ValueError(f"unknown status {status}")
    out: dict[str, Any] = dict.fromkeys(FIELDS)
    out.update(values)
    out.update(workstream_id=WORKSTREAM, experiment_id=experiment_id, status=status)
    if out["forbidden_vendor_projection_dependencies"] is None:
        raise ValueError("forbidden_vendor_projection_dependencies is required")
    return enforce(out)


def enforce(entry: Mapping[str, Any]) -> dict[str, Any]:
    """The record, invalidated if it depends on a provider's projected fantasy points."""
    out = dict(entry)
    if out.get("decision") is not None and out["decision"] not in DECISIONS:
        raise ValueError(f"unknown decision {out['decision']}")
    if out.get("forbidden_vendor_projection_dependencies") != 0:
        out["status"] = "INVALID"
        out["decision"] = None
        out["reason"] = "Depends on a provider's projected fantasy points: not valid for inference"
    return out


def problems(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Why a set of records cannot support a claim: missing fields or projection dependencies."""
    found: list[str] = []
    for entry in entries:
        name = entry.get("experiment_id", "?")
        missing = [f for f in FIELDS if f not in entry]
        if missing:
            found.append(f"{name}: missing {missing}")
        if entry.get("forbidden_vendor_projection_dependencies") != 0:
            found.append(f"{name}: forbidden vendor projection dependency")
        if entry.get("status") not in STATUSES:
            found.append(f"{name}: unknown status {entry.get('status')}")
    return found
