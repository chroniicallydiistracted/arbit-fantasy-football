# Authority, provenance and conflict resolution

| Question | Authoritative evidence | Not sufficient by itself |
| --- | --- | --- |
| What is Arbit? | Immutable [brief](../product/vision-source.txt), [product specification](../product/product-specification.md), accepted decisions | Agent narrative |
| What can change? | Current owner request, [decision register](../project/decision-register.md), accepted [ADRs](../architecture/decisions/README.md) | Proposed ADR or historical plan |
| What is implemented? | Read source + tests + [status](../project/status.md) with matching verification | Checklist, fixture or PR title |
| What is actually deployed? | Timestamped runtime/owner operations evidence with code hash, migration and origin | A checked-out branch or passing unit tests |
| What is active? | [state](state.json), [task](tasks/), [latest recorded handoff](../project/handoffs/) | Long chat or oldest AGENTS.md link |
| What may Model consume? | Accepted [ADR-006](../architecture/decisions/006-model-architecture.md) and future owner-approved availability policy | Any convenient third-party projections |
| Where are expected results? | [requirements registry](../product/requirements.json) and linked contracts/tests | Speculative agent claims |
| Can an operation change services, data, spend or publish? | Explicit recorded authorization and [operations guide](../engineering/security-and-operations.md) | An automation merely suggesting a command |

**Resolution:** quote both conflicting sources and dates, verify code/runtime facts,
check whether a later *accepted* decision supersedes the earlier, and escalate
material unresolved authority conflicts rather than inventing a resolution.
Never alter old ADR history in place; supersede with a separately approved ADR.

**Evidence grades:** `observed` (command/provider/runtime with timestamp and
scope), `documented` (recorded statement), `inferred` (reasoned but unverified),
`proposed` (not accepted), `unknown` (missing). Keep these separate in summaries.
