# Validation Guide

## Available now

`python3 scripts/validate_foundation.py` (or `make check`) is the only repository check currently implemented. Python 3.12+ standard library only. CI runs the same command on documentation, schemas, tokens, configuration and the scaffold. It checks local Markdown targets, required artifacts, source-brief checksum, requirement-to-milestone/spec mapping, the declared contract-example subset, league configuration and declared token contrast pairs. External URL reachability is not a deterministic CI check.

The contract-example checker supports the schema keywords actually used by these local schemas; it is not a complete JSON Schema implementation. Runtime bootstrap must add a standards-compliant validator/code generator and contract tests before consuming contracts in production. Foundation success is not an application build, provider integration proof, full accessibility audit, or model-quality result.

## Runtime validation to add at M1/M2

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

Introduce commands only when their tool/config/test suites exist. First runtime slices should provide `uv run pytest`, formatting/lint/type checks and an aggregate check; the web slice adds real pnpm scripts. Use lockfile-frozen installs in CI. Fixtures must be sanitized or clearly synthetic and never include member contact information or cookies. Network smoke tests require a deliberately configured local environment and do not run on untrusted pull requests.

## Verification report format

Record command, environment, time, result and interpretation. Include meaningful skipped/failed checks and why. Label provenance (synthetic fixture vs source observation vs owner-confirmed input). Acceptance is evaluated against each affected requirement, not inferred from a green aggregate check. Repeat checks after changes that affect their result; do not repeatedly run unrelated suites without a reason.
