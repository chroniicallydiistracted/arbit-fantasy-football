"""Research eligibility of M3-3 DvP features, and the production gate (owner final directive §11).

config/model/research-eligibility.json is the registry. It keeps apart four things a later agent
could confuse: a feature existing (arbit_model.feature_specs), being historically reliable, being a
promising research candidate, and being allowed into a production model.

`check_assembly(features, purpose="production")` is the gate every production model assembly calls
with its feature names. It fails closed:
- a feature the registry governs (a legacy DvP column, an M3-3 estimator or entry) is refused
  unless its entry is production-eligible;
- a name that looks like a DvP feature but has no entry is refused as unregistered;
- other features are outside this registry (no M3-3 evidence either way) and pass.

Research use (`purpose="research"`) is allowed and returns each governed feature's
classification. Nothing here computes a feature or changes any legacy definition or constant.
"""

import fnmatch
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTRY = Path(__file__).resolve().parents[4] / "config/model/research-eligibility.json"
CLASSIFICATIONS = frozenset(
    {
        "PROMISING_HISTORICAL_CANDIDATE",
        "INCONCLUSIVE",
        "TESTED_METHODS_UNSUPPORTED",
        "EXPLORATORY_FUTURE_LEAD",
        "EXPLORATORY",
        "LEGACY_DEFINITION_ONLY",
    }
)
REQUIRED = (
    "id",
    "workstream",
    "position",
    "estimator",
    "version",
    "definition",
    "eligibleSources",
    "scoring",
    "evidence",
    "prospectiveConfirmation",
    "researchClassification",
    "productionEligible",
    "requiredApprovals",
    "limitations",
    "reconsideration",
    "evidenceRefs",
    "featureSpecs",
    "lastEvaluated",
)
EVIDENCE = (
    "historicalReliability",
    "forwardPrediction",
    "unrestrictedDecision",
    "leagueConstrained",
    "simulation",
    "thresholdSensitivity",
)
# Names that look like DvP features: legacy columns, M3-3 estimator columns, entry ids.
DVP_LIKE = re.compile(r"(^|_)dvp(_|$)|^opp_off_dst_|^b0\d|^M3-3\.|dst_allowed", re.IGNORECASE)


class RegistryError(ValueError):
    """The registry is malformed or claims eligibility without its approvals."""


class IneligibleFeature(ValueError):
    """A production assembly used a feature the registry does not allow."""


@dataclass(frozen=True)
class Entry:
    id: str
    classification: str
    production_eligible: bool
    required_approvals: tuple[str, ...]
    feature_specs: tuple[str, ...]
    raw: dict[str, Any]


def load(path: Path = REGISTRY) -> dict[str, Entry]:
    """The registry's entries by id, validated."""
    data = json.loads(path.read_text())
    entries: dict[str, Entry] = {}
    for raw in data["entries"]:
        missing = [k for k in REQUIRED if k not in raw]
        if missing:
            raise RegistryError(f"{raw.get('id')}: missing {missing}")
        gaps = [k for k in EVIDENCE if k not in raw["evidence"]]
        if gaps:
            raise RegistryError(f"{raw['id']}: evidence lacks {gaps}")
        if raw["researchClassification"] not in CLASSIFICATIONS:
            raise RegistryError(f"{raw['id']}: unknown classification")
        if raw["id"] in entries:
            raise RegistryError(f"{raw['id']}: duplicate")
        if raw["productionEligible"]:
            recorded = {
                a.get("approval") for a in raw.get("approvalsRecorded", []) if a.get("evidence")
            }
            outstanding = [a for a in raw["requiredApprovals"] if a not in recorded]
            if outstanding:
                raise RegistryError(f"{raw['id']}: production-eligible without {outstanding}")
        entries[raw["id"]] = Entry(
            id=raw["id"],
            classification=raw["researchClassification"],
            production_eligible=bool(raw["productionEligible"]),
            required_approvals=tuple(raw["requiredApprovals"]),
            feature_specs=tuple(raw["featureSpecs"]),
            raw=raw,
        )
    return entries


def governing(feature: str, entries: dict[str, Entry]) -> Entry | None:
    """The entry that governs a feature name, or None if the registry doesn't cover it."""
    if feature in entries:
        return entries[feature]
    for entry in entries.values():
        if any(fnmatch.fnmatchcase(feature, pattern) for pattern in entry.feature_specs):
            return entry
    if re.match(r"^b0\d", feature):
        # An M3-3 forecast column; only D/ST B06 is a candidate, and it is position-specific.
        return entries["M3-3.DST.B06"] if feature == "b06" else entries["M3-3.OPPORTUNITY"]
    return None


def check_assembly(
    features: Iterable[str], purpose: str, path: Path = REGISTRY
) -> list[dict[str, Any]]:
    """Gate a model assembly's features. Production: raise IneligibleFeature for any governed
    feature not production-eligible and any unregistered DvP-like name. Research: report."""
    if purpose not in ("production", "research"):
        raise ValueError("purpose is production or research")
    entries = load(path)
    report: list[dict[str, Any]] = []
    refused: list[str] = []
    for feature in features:
        entry = governing(feature, entries)
        if entry is None:
            if DVP_LIKE.search(feature):
                refused.append(f"{feature}: a DvP-like feature with no registry entry")
                report.append({"feature": feature, "classification": "UNREGISTERED"})
            continue
        report.append(
            {
                "feature": feature,
                "entry": entry.id,
                "classification": entry.classification,
                "productionEligible": entry.production_eligible,
            }
        )
        if not entry.production_eligible:
            refused.append(
                f"{feature}: {entry.id} is {entry.classification}, not production-eligible "
                f"(requires: {'; '.join(entry.required_approvals)})"
            )
    if purpose == "production" and refused:
        raise IneligibleFeature("production assembly refused: " + " | ".join(refused))
    return report


def classifications(path: Path = REGISTRY) -> dict[str, str]:
    return {k: v.classification for k, v in load(path).items()}


def covered(names: Sequence[str], path: Path = REGISTRY) -> dict[str, str | None]:
    """For each name, the governing entry id (or None)."""
    entries = load(path)
    return {n: (e.id if (e := governing(n, entries)) else None) for n in names}
