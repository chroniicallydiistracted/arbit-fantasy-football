# Arbit code and decision map for new contributors

The authoritative detailed map remains in [repository guide](../engineering/repository-guide.md); this is the lightweight restart routing table, checked against the supplied 2026-11-22 source snapshot.

| Work area | Production source | Verification | Preflight record |
| --- | --- | --- | --- |
| FFA scoring, Decimal and identities | `libs/arbit-core/src/arbit_core/` | `libs/arbit-core/tests/` | [ADR-003](../architecture/decisions/003-shared-intelligence.md) |
| ESPN/league snapshots, NFLverse, NFL live data, normalization | `libs/arbit-data/src/arbit_data/` | `libs/arbit-data/tests/` and `tests/integration/` | [data architecture](../architecture/data-architecture.md), [source register](../research/source-register.md) |
| Model field catalog, target lines, Parquet artifacts | `libs/arbit-model/src/arbit_model/` | `libs/arbit-model/tests/` | [ADR-006](../architecture/decisions/006-model-architecture.md), [proposed ADR-007](../architecture/decisions/007-model-availability.md) |
| API, member access, auth, generated schema | `services/api/src/arbit_api/` | `services/api/tests/`, `tests/integration/` | [API contracts](../architecture/api-contracts.md) |
| Source sync/background capture | `services/worker/src/arbit_worker/` | `services/worker/tests/`, `tests/integration/` | [sync standard](../engineering/ffa-synchronization.md), [operations](../engineering/security-and-operations.md) |
| Member/Front Office/Live React app | `apps/web/src/` | `apps/web/src/*.test*`, `apps/web/tests/browser/` | [design system](../design/design-system.md), [member operations](../engineering/member-application.md) |
| Schema/contracts/design tokens | `packages/contracts/`, `packages/design-tokens/` | `scripts/validate_foundation.py`, `pnpm check:contracts`, `make web-check` | [validation](../engineering/validation.md) |
| Runtime services/database/migrations | `infra/`, API+worker+data | Integration tests + isolated operations verification | [security and operations](../engineering/security-and-operations.md) |
| Project phase decisions and handoffs | `docs/project/`, `docs/architecture/decisions/` | Governance checker and review | [authority](SOURCE_OF_TRUTH.md) |
| Work objective and accountability | `docs/governance/state.json`, `docs/governance/tasks/` | `scripts/governance.py doctor`, `finish`, PR diff gate | [start](START_HERE.md) |

**Important:** Do not treat `tests/fixtures/` or files in `docs/research/` as evidence that a member-facing feature is shipped. Follow imports to actual API endpoints and client rendering before marking a capability delivered. For live source decisions, inspect date and owner decision; recorded earlier speculation can be superseded by later observed changes.
