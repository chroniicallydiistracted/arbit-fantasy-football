# ADR-004: Separate access, provider sync and safe live delivery

Status: Accepted · 2026-10-30 · Owner approved architecture and recommended stack in chat.

## Context

Members need personalized access to a private league. ESPN sync credentials must not become member sessions. Live updates are predominantly downstream, while PWA caches on shared devices can expose private information.

## Decision

Invite-only OIDC with administrator-confirmed manager/team bindings and opaque server-side sessions. Provider credentials exist only in server secret configuration; initial ESPN integration is read-only. Shared backend polls and revision-aware outbox feed session-authorized SSE with cursor replay and polling fallback. PWA caches static versioned assets only; private API/auth/export/SSE requests remain network-only/no-store.

## Alternatives and consequences

Unrestricted team selection is not identity verification. Custom passwords add recovery/security obligations without a demonstrated requirement. Browser ESPN fetches expose cookies and multiply polls. WebSockets are possible but unnecessary for initial one-way feeds. Static-only offline support limits offline research, but avoids persisting private league data until an explicit product design addresses it.

## Evidence

M2 auth/CSRF/binding/revocation and offline-cache negatives; M6 reconnect/expired cursor/correction/full-slate tests. OIDC provider still needs owner selection. Related: ENG-004, UX-004, LV-005; [system architecture](../system-architecture.md), [operations](../../engineering/security-and-operations.md).

Adoption record: owner stated “Architecture passed” and “I approve your recommended stack” on 2026-10-30. Original proposal retained above; implementation evidence is recorded in runtime handoffs.
