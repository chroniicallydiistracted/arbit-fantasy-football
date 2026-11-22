# API-specific rules

Inherited root AGENTS.md applies. Read [API contracts](../../docs/architecture/api-contracts.md)
and [security/operations](../../docs/engineering/security-and-operations.md).
Authenticate/authorize real member resources; do not leak private data into
browser bundles or fixture logs. Generated OpenAPI client types come from the
approved generator, not hand editing. Require scoped API and integration tests.
