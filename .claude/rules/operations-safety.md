---
paths:
  - "infra/**"
  - "services/worker/**"
  - "services/api/**"
---

Do not run migrations, restart/publish the owner's live app, change Cloudflare,
modify real league data or provision external services without explicit scope.
Use fixture/local tests and the operations runbook; no secret-bearing logs.
Separate repository implementation, integration verification and runtime release.
