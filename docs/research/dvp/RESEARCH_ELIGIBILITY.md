# M3-3 research eligibility

Owner final directive §11 (DEC-07, DEC-09), TASK-20261125-002.
- **Machine-readable registry:** [`config/model/research-eligibility.json`](../../../config/model/research-eligibility.json).
- **Gate:** [`arbit_model.eligibility`](../../../libs/arbit-model/src/arbit_model/eligibility.py).
- **Tests:** `libs/arbit-model/tests/test_eligibility.py`.

**What it keeps apart:** a feature existing, being historically reliable, being a promising research candidate, being prospectively confirmed, and being allowed into a production model. These are separate facts. **No M3-3 feature is production-eligible.**

| Entry | Classification | Production | Before production it needs |
| --- | --- | --- | --- |
| M3-3.DST.B06 (D/ST B06) | **PROMISING_HISTORICAL_CANDIDATE** | No | The complete 2026 window CONFIRMED (amendment 1 gate); an incremental test against the integrated Sit/Start model; the owner's weight decision (OWN-074) |
| M3-3.DST.LEAGUE (FFA league-constrained utility) | INCONCLUSIVE | No | A study with enough decisions to measure |
| M3-3.QB.AGG | INCONCLUSIVE | No | A new predeclared study |
| M3-3.RB.AGG | TESTED_METHODS_UNSUPPORTED: a consistent sub-threshold gain (AUD-07), not shown absent | No | A new predeclared study |
| M3-3.WR.AGG, M3-3.TE.AGG, M3-3.K.AGG | TESTED_METHODS_UNSUPPORTED | No | A new predeclared study |
| M3-3.K.VOLUME | EXPLORATORY_FUTURE_LEAD | No | A predeclared confirmatory study |
| M3-3.OPPORTUNITY (volume, efficiency, windows, split-half k) | EXPLORATORY | No | A predeclared study |
| LEGACY.DVP (`opp_dvp_*`, `opp_off_dst_allowed_*` in `feature_specs`) | LEGACY_DEFINITION_ONLY | No | Evidence under a predeclared study |

**What each entry records:**
- identifiers, position, estimator and version;
- the definition, eligible sources and scoring;
- six kinds of evidence: historical reliability, forward prediction, unrestricted decisions, FFA league-constrained, simulation, and threshold sensitivity;
- prospective status, classification, production eligibility and required approvals;
- limitations, when to reconsider, evidence references, and the last evaluation date.

**The gate** (`check_assembly(features, purpose)`):
- **Production:**
  - refuses any feature the registry governs unless its entry is production-eligible;
  - refuses a DvP-like name with no entry;
  - lets other features through, since they are outside this registry.
- **Research:** reports each governed feature's classification without refusing.
- **Fail closed:** a registry that marks an entry production-eligible without every required approval recorded with evidence fails to load.
- **What it does not change:** nothing is activated. The legacy definitions and shrinkage constants are unchanged.

**For later slices:** even a confirmed B06 must show incremental value against the integrated Sit/Start model before any weight (directive §11). A slice adding a new DvP-derived input adds a registry entry first.
