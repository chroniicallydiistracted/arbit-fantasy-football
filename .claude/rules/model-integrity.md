---
paths:
  - "libs/arbit-model/**"
  - "scripts/model/**"
  - "docs/architecture/model-specification.md"
---

Follow accepted ADR-006: nflverse-only statistical inputs and exact FFA scorer.
ADR-007 is accepted with owner amendments (OWN-066): a value fetched late after a
capture gap counts from the source's own timestamp or family rule, never before
the gap start; every field states when it applies rather than being barred. Never
use a value before its known-from time. Betting lines need the OWN-067 study.
Require baseline comparisons, holdout protocol and traceable manifests before
claiming projection readiness. Do not fabricate a trained model or probability.
