"""The research eligibility registry and the production gate (owner final directive §11)."""

import json
import re
from pathlib import Path

import pytest
from arbit_model import eligibility as el
from arbit_model.feature_specs import FEATURES, SHRINKAGE

DIRECTIVE = {
    "M3-3.DST.B06": "PROMISING_HISTORICAL_CANDIDATE",
    "M3-3.DST.LEAGUE": "INCONCLUSIVE",
    "M3-3.QB.AGG": "INCONCLUSIVE",
    "M3-3.RB.AGG": "TESTED_METHODS_UNSUPPORTED",
    "M3-3.WR.AGG": "TESTED_METHODS_UNSUPPORTED",
    "M3-3.TE.AGG": "TESTED_METHODS_UNSUPPORTED",
    "M3-3.K.AGG": "TESTED_METHODS_UNSUPPORTED",
    "M3-3.K.VOLUME": "EXPLORATORY_FUTURE_LEAD",
    "M3-3.OPPORTUNITY": "EXPLORATORY",
    "LEGACY.DVP": "LEGACY_DEFINITION_ONLY",
}


def test_the_directive_classifications_are_recorded_and_nothing_is_production_eligible():
    entries = el.load()
    assert {k: v.classification for k, v in entries.items()} == DIRECTIVE
    assert not any(e.production_eligible for e in entries.values())
    b06 = entries["M3-3.DST.B06"]
    assert any("OWN-074" in a for a in b06.required_approvals)
    assert any("integrated Sit/Start" in a for a in b06.required_approvals)
    assert b06.raw["prospectiveConfirmation"].startswith("PENDING_FUTURE_DATA")


def test_every_legacy_dvp_feature_is_governed_and_every_pattern_matches_one():
    dvp_like = [n for n in FEATURES if el.DVP_LIKE.search(n)]
    assert dvp_like, "feature_specs defines legacy DvP columns"
    coverage = el.covered(dvp_like)
    assert all(v == "LEGACY.DVP" for v in coverage.values()), coverage
    for entry in el.load().values():
        for pattern in entry.feature_specs:
            assert any(re.fullmatch(pattern.replace("*", ".*"), n) for n in FEATURES), pattern
    # The legacy shrinkage constants are preserved unchanged by this registry.
    assert SHRINKAGE["dvp_RB"][0] == 18.7 and SHRINKAGE["dst_allowed_adj"][0] == 9.1


def test_production_assembly_refuses_every_dvp_feature_and_passes_others():
    for feature in (
        "opp_dvp_RB_adj_shrunk",
        "opp_off_dst_allowed_pg",
        "b06",
        "b07v",
        "M3-3.DST.B06",
    ):
        with pytest.raises(el.IneligibleFeature, match="not production-eligible"):
            el.check_assembly(["rest_days", feature], purpose="production")
    with pytest.raises(el.IneligibleFeature, match="no registry entry"):
        el.check_assembly(["dvp_new_measure"], purpose="production")
    assert el.check_assembly(["rest_days", "off_epa_per_play_shrunk"], purpose="production") == []


def test_research_use_reports_classifications_without_refusing():
    report = el.check_assembly(["b06", "opp_dvp_WR_pg", "is_home"], purpose="research")
    assert [r["classification"] for r in report] == [
        "PROMISING_HISTORICAL_CANDIDATE",
        "LEGACY_DEFINITION_ONLY",
    ]
    with pytest.raises(ValueError, match="purpose"):
        el.check_assembly(["b06"], purpose="shadow")


def test_a_registry_claiming_eligibility_without_its_approvals_is_refused(tmp_path: Path):
    data = json.loads(el.REGISTRY.read_text())
    data["entries"][0]["productionEligible"] = True
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(el.RegistryError, match="production-eligible without"):
        el.load(bad)
    # With every approval recorded with evidence, the entry may be eligible.
    entry = data["entries"][0]
    entry["approvalsRecorded"] = [
        {"approval": a, "evidence": "receipt"} for a in entry["requiredApprovals"]
    ]
    bad.write_text(json.dumps(data))
    assert el.load(bad)["M3-3.DST.B06"].production_eligible
    assert el.check_assembly(["b06"], purpose="production", path=bad)


def test_a_malformed_entry_is_refused(tmp_path: Path):
    data = json.loads(el.REGISTRY.read_text())
    del data["entries"][1]["evidence"]["simulation"]
    bad = tmp_path / "registry.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(el.RegistryError, match="evidence lacks"):
        el.load(bad)
    data = json.loads(el.REGISTRY.read_text())
    data["entries"][2]["researchClassification"] = "PROBABLY_FINE"
    bad.write_text(json.dumps(data))
    with pytest.raises(el.RegistryError, match="unknown classification"):
        el.load(bad)
