# Shared data

M1a implements normalized snapshot candidates, atomic PostgreSQL snapshot/current-pointer/outbox publication and a durable job queue with idempotency, leases, heartbeat, fencing, retries and failed state. Applied DDL is versioned in Alembic. Leased workers pass their lease when publishing. ESPN/nflverse/Sleeper adapters, persisted crosswalks, full league contracts, source completeness proof and dataset manifests remain M1b–e work. No live ingestion is claimed.
