# Local-first infrastructure

M1a includes digest-pinned PostgreSQL 18 Compose configuration on loopback port 55439 and idempotent local test/fixture database initialization. Named-volume data is preserved. API/worker container images, reverse proxy, remote object storage and deployment/backups remain later work. No paid or production service is provisioned. See [local development](../docs/engineering/local-development.md) and the operations runbook; do not delete volumes casually.
