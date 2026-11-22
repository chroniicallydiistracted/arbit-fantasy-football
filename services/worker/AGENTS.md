# Worker-specific rules

Inherited root AGENTS.md applies. Read [data architecture](../../docs/architecture/data-architecture.md)
and [operations guide](../../docs/engineering/security-and-operations.md).
Source cadence, stale window, bounded retries, immutable lineage and clear
failure states are required. No live worker activation or external reads without
proper scope. Preserve data and deployment boundaries.
