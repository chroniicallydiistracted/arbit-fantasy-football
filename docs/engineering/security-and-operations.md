# Security and Operations Runbook

Version 0.1 · Proposed runtime procedures; no production service exists.

## Trust and secrets

Assets: ESPN session cookies, member identity/team bindings, private rosters/league metadata, saved scenarios, model lineage and historical results. Main boundaries: browser ↔ same-origin API; API ↔ OIDC provider; services ↔ PostgreSQL/storage; worker ↔ unofficial providers. Treat every provider payload, player/news string and downloaded image as untrusted. Escape text, allowlist links, prohibit executable remote HTML, validate content type/size and protect image fetchers from SSRF using approved HTTPS hosts and redirect validation.

Store provider/OIDC/database credentials in local ignored environment files or a deployment secret store. `.env.example` has names only. Never ask members to paste ESPN cookies into chat. Commissioner enters them through an approved local/admin setup path at the integration milestone; no automatic extraction from browser profiles. Never request ESPN passwords. Do not log headers/cookies/raw auth responses or persist auth secrets in snapshot metadata. Use least-privilege DB/storage access, encryption at rest where supported, TLS externally, and restricted backups. Redact PII from test fixtures and research records.

Only invited accounts access FFA data. Administrator bindings are audited. Authenticate and authorize each HTTP/job/export/SSE path; a UUID is not authorization. No secret key appears in a `VITE_*` client variable. CSRF protection applies to local preference/scenario/admin mutations even though provider integration is read-only. Logout/revocation closes streams and clears in-memory private data. Avoid private browser persistence/service-worker caches in the first version.

## Local bootstrap prerequisites

Before live access: adopt runtime ADRs, pin versions/lockfiles, validate `config/league.json`, configure storage/database, register a chosen OIDC client if testing auth, and supply ESPN secret references only if required. Start with synthetic fixtures, test migrations and readiness, then run one bounded live read. A 401 without credentials was observed for the configured FFA settings endpoint; do not claim private access until a valid authorized fetch succeeds. Do not print the successful response's member data into development logs.

## Incident and recovery procedures

| Trigger | Immediate response | Recovery evidence |
| --- | --- | --- |
| ESPN 401/403 | Mark source auth-needed, stop tight retry, preserve last snapshot; administrator rotates locally | Bounded read succeeds, complete snapshot validates, no secret in logs |
| 429/provider outage | Honor Retry-After/backoff, global limiter/circuit breaker; show stale state | Source healthy and schedule resumes without request storm |
| Schema drift/partial data | Quarantine revision, preserve last complete current pointer; block affected advice | Adapter/fixture updated, replay validates completeness and scoring |
| Identity mismatch | Freeze affected advice, review alias evidence; version correction | Recomputed joins/derived output and audit trail verified |
| Incorrect model/advice | Withdraw run/current pointer and fall back to prior validated model/baseline | Regression and temporal validation evidence before re-release |
| Leaked credential | Revoke/rotate credential, invalidate sessions if affected, restrict artifacts and examine redacted audit | Rotation and access review recorded; no claim history erasure fixes exposure |
| DB/storage failure | Stop publication, retain recoverable jobs; restore isolated backup | Counts/constraints/snapshot pointers, sessions, archive and replay pass checks |
| Faulty deployment | Roll back compatible images/static bundle; pause failing worker; forward DB fix as needed | Readiness plus synthetic member, outbox and sync checks |

Daily encrypted backups target RPO 24 hours; proposed RTO four hours if a host is available. Restore quarterly into isolated storage and verify identities, rule hashes, latest snapshot, saved scenarios, archive finals and job/outbox consistency. Do not rely on replayable public data as the only backup of private league history. Retention details live in data architecture.

## Release checklist

Confirm relevant tests/contract generation and source/data/model gates; backup/restore readiness; migration compatibility; pinned images/lockfiles; secret references; response security headers and same-origin proxy; no private caching; source budgets and degraded states; health and SSE reconnect. Deploy only within explicit owner authorization. Rollout records identify exact versions and rollback artifact. Provider failure is not the same as API liveness failure; avoid restart storms during upstream outages.

## Observability and cost controls

Structured logs: request/job/run IDs, source type, safe error code, duration and redacted counts. Metrics: last successful source observation, completeness/mapping failures, polling volume, queue age/retries/dead letters, scoring discrepancies, SSE reconnections/delivery delay, cached read latency, feature missingness and model calibration. Alert on user-impacting staleness or persistent failure; deduplicate unchanged incidents. Portable local-first proposal creates no paid account or recurring cost. Hosting/storage capacity must be measured and agreed before external provisioning.
