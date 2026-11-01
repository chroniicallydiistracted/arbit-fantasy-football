# Architecture Decision Records

Records are immutable explanations of consequential choices; supersede with a new ADR when accepted behavior changes. Status is **Proposed**, **Accepted**, **Superseded**, or **Rejected**. Record decision owner/date and acceptance evidence; never infer approval from an agent writing a proposal.

| Record | Status | Topic |
| --- | --- | --- |
| [001](001-modular-runtime.md) | Accepted | Modular mixed-language runtime and native tooling |
| [002](002-data-and-identity.md) | Accepted | Relational serving state, versioned analytical storage and canonical aliases |
| [003](003-shared-intelligence.md) | Accepted | Shared exact scoring, point-in-time model outputs and evidence policies |
| [004](004-access-live-and-pwa.md) | Accepted | Independent member access, provider secrets, SSE and safe PWA caching |
| [005](005-officiating-character.md) | Accepted | Officiating and broadcast product character; enforced design rules |

Template: context → decision → alternatives → consequences → validation/adoption → related requirements. Small routine implementation choices belong in task records rather than generating an ADR for every edit.
