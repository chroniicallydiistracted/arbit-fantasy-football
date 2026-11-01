# M2 member application implementation plan

> **For agentic workers:** Execute natively with meaningful RED→GREEN behavior checks. Use only `gpt-6.1-sol` for any subagent; one final independent review. No additional design-approval gate is needed for the already accepted architecture and explicit M2 request.

**Goal:** Deliver the invite-only member foundation, stored Front Office facts, deliberate React/PWA shell and safe local operational setup, while enforcing the owner's corrected Sleeper scope.

**Spec:** Approved roadmap M2, ADR004/system/data/API architecture, design system and Front Office workflow. Owner now restricts Sleeper to relevant NFL live games/PBP only, forbids all Sleeper fantasy inputs, and restricts subagents to GPT-6.1 Sol. Original brief and historical source receipts remain unchanged; new decisions supersede broader prior interpretations.

**Architecture:** PostgreSQL opaque sessions, issuer+subject accounts, private invitations and administrator-approved dated manager bindings. A maintained OIDC/JWT library validates provider tokens; auth flow secrets remain server-side. FastAPI composes one pinned canonical FFA snapshot into typed member facts; generated OpenAPI TypeScript contracts feed React/Vite/Router/Query. Static-only PWA cache, in-memory private queries and explicit unavailable analysis.

**Execution scope:** No source/model recommendations, active Live UI or deployment. No new provider account/project/client registration, paid service or messages. Real OIDC connection requires owner-selected provider and local client configuration; complete all provider-neutral implementation/testable local work first, never present fixture sign-in as real-provider proof.

**Requirements:** DATA-003 source correction; CTX-002 team context; FO-001 pinned facts; UX-002/003/004 implemented components, accessibility and PWA; ENG-003/004 validation, sessions and authorization. Other modules remain future capability.

**Affected files:** additive `services/api/migrations/versions/0006_members.py`; member schema/store in `libs/arbit-data`; auth/settings/contracts/routes/static/fixture/admin in `services/api`; generated `packages/contracts/openapi.json` and `apps/web/src/generated/api.ts`; React client/public assets/tests in `apps/web`; node/build/token/CI scripts and the operator/status/requirements/handoff records. Source correction touches only former Sleeper acquisition/mapping and its generic source tests/docs.

## Task 0 — Correct source/model policy

- Add regression requiring all existing Sleeper directory/state/trend/fantasy-stat request kinds and forged requests to fail before cache/network access.
- Remove active Sleeper fantasy normalization/mapping/CLI entry points, preserve immutable historical research only. ESPN game/play source paths remain active. Generic capture/lease tests switch to allowed ESPN resources without weakening cache/fencing evidence; daily-vendor policy becomes historical unless a verified eligible route needs it.
- Record owner source override and GPT-6.1 Sol-only rule in AGENTS/current specs/status/source guide. Preserve original brief and old factual audit counts. Run focused/full checks and commit.

## Task 1 — Accounts, invitations, bindings and session storage

- New additive schema0006: member accounts keyed by issuer+subject; hashed invitations, hashed opaque sessions, one-use browser-bound OIDC flows, manager bindings and versioned preferences/audit records.
- Implement transactional invite redemption (verified email + issuer policy), role/suspension/session rotation/revocation, idle7d/absolute30d expiry, bounded preference CAS/watchlist. Team context derives from approved manager bindings and the current snapshot, never unrestricted client team selection.
- RED tests: invite reuse/expiry/wrong email/issuer, multiple managers/co-managers, different member scopes, revocation/rotation/expiry, absent binding, preference conflicts. Real isolated PostgreSQL tests; preserve existing FFA tables.

## Task 2 — OIDC and authenticated API boundary

- Provider-neutral OIDC client using maintained library for PKCE/token signature/iss/aud/nonce/expiry checks. Trusted server configuration fixes issuer/discovery/client/redirect endpoints; bounded no-proxy/no-redirect provider HTTP. Do not log codes/tokens or store provider access tokens.
- Same-origin auth start/callback/logout/status, browser-bound single-use state/nonce/verifier in DB, opaque HttpOnly session cookie, CSRF+Origin for mutations, no-store/referrer/security headers and safe errors. Production requires secure complete member auth; development test identity support only for dedicated test/fixture DB and explicit mode, never real local/private data.
- RED negatives cover tampered signature/issuer/audience/nonce/state, unverified email, callback replay/login CSRF, cross-origin changes, cookie attributes, session expiry/revocation and unsafe startup. Provider selection is pending the early user question; provider-specific configuration is dependent work.

## Task 3 — Member facts, administration and generated contracts

- Typed `/api/v1/me`, `/front-office`, `/league/teams`, `/players/{uuid}`, `/me/preferences` and bounded administration invite/binding/session actions. All read stored canonical FFA data, no providers; one snapshot/source age per response. Do not expose unnecessary manager/provider records.
- Front Office has own record/rank, matchup/official scores, roster/locks, standings and explicit pending analysis. Unknown NFL display metadata stays unknown; no guessed franchise labels. Historical scoring/matchup period routing remains explicit.
- Generate OpenAPI and TypeScript types reproducibly, no handwritten wire copies. Add safe operator bootstrap/invite setup and clearly synthetic two-member browser fixture data; never publish fixture identities into real `_local` data.
- RED cross-member/admin/unknown-player/team-context/binding/stale-null/source failure checks and contract generation drift.

## Task 4 — Deliberate application and PWA

- Add frozen React/TypeScript/Vite/Router/Query client in native pnpm workspace; semantic accessible primitives and shared token CSS. Warm paper/ink/deep green, restrained brass, purposeful editorial typography and dense readable football facts. No generic metric-card grid, decorative charts or fake forecasts.
- Sign-in/invitation/pending-binding paths; responsive shell/navigation; Front Office matchup, roster, standings; fact-only player drawer, watchlist/preferences/theme; preserved period/filter/deep-link context. Disabled analysis explains pending model without technical clutter.
- Web manifest/icons, static-only service worker, offline shell, explicit update prompt. Never cache API/auth/private data or persist private queries; clear on logout/expiry. Preview data is unmistakably fictional and guarded separately from real member data.
- Meaningful component tests, production build/type/lint, browser flows at320/768/1280/1600, keyboard/focus/reduced-motion/zoom, automated accessibility and offline/update/cache-negative checks.

## Task 5 — Integration, review and handoff

- Full pinned runtime + web checks, populated migration preservation, local browser/API roundtrip with two fixture members, actual stored-data composition proof without bypassing authentication. Real provider/configuration limitations remain explicit.
- One independent final `gpt-6.1-sol` review; fix Important/Critical findings in one regression-backed pass, no second reviewer. Respect current user model override over skill model defaults.
- Update status/requirements/contracts/design/operations/source policy/changelog and dated handoff with actual evidence, remaining provider setup/empirical gates and local branch. No push/merge/deployment, no active unneeded test processes.
