# Validation Guide

## Available now

`python3 scripts/validate_foundation.py` (or `make check`) remains the dependency-free artifact check. Python 3.12+ standard library only. CI runs the same command on documentation, schemas, tokens, configuration and the scaffold. It checks local Markdown targets, required artifacts, source-brief checksum, requirement-to-milestone/spec mapping, the declared contract-example subset, league configuration and declared token contrast pairs. External URL reachability is not a deterministic CI check. Ignored local captures, secrets, scratch state and third-party `.references` checkouts are excluded from artifact discovery; a regression proves project links remain checked.

The contract-example checker supports the schema keywords actually used by these local schemas; it is not a complete JSON Schema implementation. M1a adds full Draft 2020-12 AJV validation through `pnpm check:contracts`. OpenAPI business contracts/code generation follow with authenticated API features. Foundation success is not an application build, provider integration proof, full accessibility audit, or model-quality result.

## Runtime checks available now

After frozen installs and `make db-up`, `make runtime-check` runs foundation checks, Ruff lint/format, strict mypy, AJV contract examples and all pytest tests, including real PostgreSQL migration/snapshot/job/health integration. See [local development](local-development.md). The current verified baseline is 409 tests, including public ESPN acquisition/scoring/durable sync, NFLverse source-proof/current-order/crosswalk/normalization regressions and real PostgreSQL integration. Full local NFLverse offline verification and HTTP/identity evidence are recorded in the [M1d audit](../research/nflverse-data-audit-2026-10-31.md). Scoring tests include numeric-only anonymized observed cases plus independent hand/boundary scenarios; a live completed-week audit/replay is separate evidence, never mandatory CI. Provider tests use synthetic identities and a loopback-only network guard; live public inspection is a separate opt-in smoke check. CI is configured to run the same checks with an isolated database, but has not been remotely executed in this session.

## Feature validation gates across M1/M2 and later milestones

| Change | Required meaningful evidence |
| --- | --- |
| Core scoring/rules/eligibility | Hand-calculated Decimal fixtures, boundary/bonus/negative/correction cases, unsupported-rule rejection, legal slot assignment; reconcile supported FFA cases against sanitized ESPN totals |
| Provider adapter/sync | Sanitized representative contracts, schema drift, 401/403/429/retry behavior, complete pagination, partial snapshot rejection, idempotent replay, alias ambiguity |
| Persistence/jobs | Ephemeral PostgreSQL integration tests; unique ownership/alias constraints; transaction rollback; lease expiry/reclaim/fencing and outbox replay |
| API/auth | Schema client generation diff, status/error contracts, invite/team authorization, cross-user job access, session/CSRF/OIDC failure/revocation tests |
| Models/features | Point-in-time cutoff/leakage checks, reproducibility, rolling holdout/baseline/subgroups/interval calibration, missing features and scoring rule changes |
| Advisor | Lineup exhaustive-case oracle; waiver/trade before/after legality and ownership race; draft full replay/scenario calibration; consistent model/rules across modules |
| UI/PWA | Component behavior, primary journey browser tests, keyboard/screen-reader/reflow, accessible chart alternatives, private-cache exclusion, session expiry and offline/update flow |
| Live | Named play-type replay, both field directions, correction/tombstone/duplicate/reorder handling, roster filtering, reconnect cursor expiration, reduced motion, full-slate load |
| Archive | Finalization/tie/multiweek playoff and correction fixtures; original rule/name history; inaugural empty state |
| Deployment | Image/dependency/migration checks, readiness, backup restore, rollback, secrets handling and measured load/freshness budgets |

Introduce commands only when their tool/config/test suites exist. M1a provides `uv run pytest`, lint/format/type checks, native JS contract validation and `make runtime-check`; web application checks arrive with the web slice. Use lockfile-frozen installs in CI. Fixtures must be sanitized or clearly synthetic and never include member contact information or cookies. Network smoke tests require a deliberately configured local environment and do not run on untrusted pull requests.

## Verification report format

Record command, environment, time, result and interpretation. Include meaningful skipped/failed checks and why. Label provenance (synthetic fixture vs source observation vs owner-confirmed input). Acceptance is evaluated against each affected requirement, not inferred from a green aggregate check. Repeat checks after changes that affect their result; do not repeatedly run unrelated suites without a reason.

M1e adds real PostgreSQL refresh-reservation/cache/last-good/fencing tests, safe public JSON bounds, read-only supplemental ID conflict checks, exact source-reference/type scopes, per-play observation ordering through cached/mixed pages and correction replay, asset-context/permission fallback, and safe offline/partial CLI behavior. [Source proof](../research/m1e-source-audit-2026-10-31.md) uses opt-in calls; synthetic corrected/delayed/sneak cases are not empirical source availability evidence.
