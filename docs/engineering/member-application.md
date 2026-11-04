# Member application — M2

The local application implements invited accounts, Google-compatible OpenID Connect, administrator-approved FFA manager bindings, opaque sessions, saved preferences/watchlists and stored Front Office facts. It serves the built React client on the API origin. No model, provider transaction, full Live workspace or deployment is enabled. The [handoff](../project/handoffs/2026-10-31-member-application.md) separates actual source evidence from fictional browser evidence.

## Build and validate

Use the [pinned tools](local-development.md), frozen installs and `make db-up`. From the repository root:

```sh
uv sync --frozen
pnpm install --frozen-lockfile
make runtime-check
make web-check
```

`web-check` verifies generated OpenAPI/TypeScript drift, Biome, strict TypeScript, Vitest/component behavior, the production build and negative service-worker coverage. `pnpm generate:client` regenerates TypeScript after `uv run python scripts/export_openapi.py`. API boundary models remain authoritative. `pnpm --filter @arbit/web dev` runs the optional Vite development server; configure `ARBIT_PUBLIC_ORIGIN` to that exact origin while using its same-origin proxy. Browser tests use the built single-origin application at port 8000.

The build generates 192/512 PNG icons from the original SVG using resvg-js, plus CSS from shared semantic tokens. Binary outputs remain ignored; frozen packages supply fonts locally. OFL notices ship under `/licenses/`. No CDN fonts, provider client calls or private environment values enter the browser bundle.

## Fictional local preview

This is a separate database, not a way to bypass real FFA authentication. `make db-up` creates `arbit_member_fixture`. Use only this profile for the preview:

```sh
export ARBIT_ENV=test
export ARBIT_AUTH_MODE=fixture
export ARBIT_PUBLIC_ORIGIN=http://127.0.0.1:8000
export ARBIT_DATABASE_URL='postgresql+psycopg://arbit_local:arbit-local-dev-only@127.0.0.1:55439/arbit_member_fixture'
uv run python -m arbit_api.fixture
make web-build
uv run uvicorn arbit_api.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

Open `http://127.0.0.1:8000`. The banner and sign-in buttons identify the test data. To verify without disturbing a running app, build elsewhere (`vite build --outDir`), set `ARBIT_WEB_DIST_PATH`, serve on another port and point `ARBIT_BASE_URL` at it for Playwright. Two members have separate teams; current scores are unknown; one historical matchup has fictional final totals. The seed is idempotent and refuses existing unrelated data. Fixture authentication requires explicit test mode, a dedicated loopback `_test`/`_fixture` database, a matching actual engine and an actual loopback HTTP peer. It refuses the real `_local` database and production. Stop this process and clear these exported variables before running real member access.

For reproducible Chromium checks, install `pnpm --filter @arbit/web exec playwright install chromium`, start the isolated application as above, then run `pnpm --filter @arbit/web test:browser`. On this host the existing Chromium149 binary was selected with `ARBIT_BROWSER_PATH`; other hosts use Playwright’s matching browser by default. Tests use fictional identities only. Browser traces/screenshots stay ignored. CI performs this against an ephemeral test database; the workflow has not been run remotely in this session.

## Google sign-in and real FFA access

The owner selected Google on 2026-10-31. The server profile matches Google’s published issuer, endpoints, RS256 and S256 metadata. Google requires a Web application OAuth client and an exact registered redirect URI. [Official setup](https://developers.google.com/identity/openid-connect/openid-connect), [published metadata](https://accounts.google.com/.well-known/openid-configuration).

1. In the owner-controlled Google project, configure the consent screen/audience and a Web application OAuth client. For local use, register `http://127.0.0.1:8000/auth/callback` exactly. Add invited test accounts if the Google app remains in testing.
2. Copy [the configuration template](../../config/google-auth.env.example) to ignored `.env.auth.local`, restrict it to mode600, and enter the client ID/secret locally. Do not send credentials in chat. Leave `.env.local` as the private database/operator profile.
3. Run `make local-db-migrate` and `make web-build`. Prepare the first administrator’s private invitation with `uv run --env-file .env.local --env-file .env.auth.local python -m arbit_api.admin`. The hidden email prompt is not logged; the link is written exclusively to mode600 `secrets/admin-invitation.txt`. Bootstrap closes when an administrator or an unexpired administrator invitation exists.
4. Run `make member-api`, open the private invitation link locally, and sign in with that exact invited Google account. Invitation fragments are stripped before requests and submitted only to the same-origin auth-start endpoint; they are never sent to Google.
5. In **Preferences → League access**, approve the correct canonical FFA manager identity for the account. An unassigned administrator can reach Preferences. Binding changes revoke prior sessions; sign in again to confirm the team. Subsequent invitations, bindings, suspension/reactivation and session revocation are administrator-only. Inviting a member does not bind a team automatically.

No Google client/project has been registered by this development work. A real Google round trip, real first-admin bootstrap and real member/team confirmation remain the M2 operational acceptance gate. They cannot be replaced by fixture sign-in or mocked provider tests. No real member accounts were created for validation.

Externally served environments must use `ARBIT_ENV=production`, complete OIDC configuration and HTTPS. Fixture mode, auth bypass and operator-token routes are rejected. Use a trusted TLS proxy and suppress query/access logging there as well. Hosting, TLS, backups/restore and measured load remain separate release work; no service is provisioned here.

## Local address

The app's address is exactly `ARBIT_PUBLIC_ORIGIN`, which is `http://127.0.0.1:8000` locally. Browsers treat `localhost` and `127.0.0.1` as separate sites, so the session cookie and the sign-in origin check only work on the configured one. Pages opened under another loopback name on the same port redirect there. Hosted origins never redirect, because their proxy decides the host header.

## Access and data behavior

Accounts are immutable issuer+subject identities. A verified email only redeems a one-use seven-day invitation; it cannot claim a manager. Session hashes live in PostgreSQL, with 30-day idle and 90-day absolute expiry. A completed login replaces the session that browser presented; other devices stay signed in, up to ten. Members can review and end devices in Preferences. HttpOnly, host-scoped, SameSite=Lax cookies are Secure over HTTPS. CSRF token and exact Origin checks protect mutations. Single-use browser-bound state, nonce and PKCE verifier expire in ten minutes; consumed secrets are wiped, expired flows pruned and active flows capped100. The maintained Authlib/joserfc path validates RS256 signature, issuer/audience/nonce/time and applicable access-token hash. Provider HTTP has fixed HTTPS hosts, no redirect/environment proxy and bounded responses; provider access tokens are never stored.

Bound members read one canonical saved snapshot per facts response. Unknown official scores remain unknown; no projection or live estimate is added. The player drawer pins its source snapshot when opened from a roster/search. Historical matchup selection shows official totals and explicitly withholds a roster when no historical lineup capture exists. Current season standings stay labeled current. A paused/degraded/stale/unknown source is visibly limited. No request refreshes a provider.

Member preferences use revision checks; a conflicting tab refreshes the actual state rather than silently overwriting it. Watchlists contain known canonical player IDs only, at most100. Theme-only preference changes remain possible while assignment/source facts are unavailable. Access is rechecked on private requests, window focus and once per minute while a signed-in tab is visible. Session/account/assignment changes are audited; one active administrator must survive concurrent suspension attempts. Reactivation does not restore revoked sessions or bindings.

The service worker has a closed static allow-list and build-content version. `/api`, `/auth`, `/internal`, exports and events remain network-only; arbitrary runtime content and authenticated HTML are not cached. Offline, expiry and logout clear private query memory; offline navigation serves only the neutral connection page. Updates wait for the user’s **Update & reload** action. No private localStorage/sessionStorage, persisted query cache or offline roster is implemented.

Manager assignment choices prefer the ESPN-provided first name followed by canonical team names. Missing first names fall back to the original ESPN display name; colliding labels additionally show that handle. Labels never establish identity or assign a team: existing canonical manager IDs remain the binding keys. Optional name fields are omitted when absent to preserve old capture hashes and canonical serialization. The explicitly used first name stays in private captures; unused surnames, email and notification settings remain excluded.

## Dev account (read-only)

A read-only account that lets Claude, or anyone working on this machine, see the running app signed in, without the owner's Google account.

```sh
make dev-account       # a 12-hour session, saved for Playwright in data/observer/storage-state.json
make dev-account-end   # end every dev account session at once
```

- **What it can do.**
  - It opens every team: the Front Office team switcher shows any manager's view.
  - It reads the administrator pages.
  - A yellow band on every page says it's the read-only dev account.
  - It can change only its own preferences and sign out. The API refuses everything else with `OBSERVER_READ_ONLY`, and the administrator buttons are disabled.
- **How it signs in.** Its identity, issuer `urn:arbit:observer`, can't come from Google or any other sign-in, so only the local command gives it a session.
  - One session at a time, 12 hours by default (`python -m arbit_api.observer session --hours N`, at most 24).
  - The session goes into a storage-state file only this user can read, and the token is never printed.
  - Playwright loads the file with `storageState`.
- **The administrator's control.** The account appears in League access as "Dev account (read-only)". Revoking its sessions or suspending it works like any member's, and `make dev-account` refuses while it's suspended.
- **Production.** It is off when `ARBIT_ENV=production`: the API treats its sessions as signed out.

## Upgrading a running local app and keeping it running

`make local-upgrade` backs up the database, applies migrations and rebuilds the client. Stop the member API and worker first (`systemctl --user stop arbit-api arbit-worker`, then `start` afterward), since a new client needs new routes. Avoid `pkill -f` with the server's command line through the prompt's `!` prefix or a script: the calling shell matches the pattern and kills itself. To run as supervised services, `make services-install` installs `arbit-worker` and `arbit-api` as systemd user units that restart on failure and survive logout; this enables linger for your user, and `make services-remove` undoes it. Without services, run `make member-api` and `make local-worker` in two terminals. Logs: `journalctl --user -u arbit-worker -f`. On WSL the services stop with WSL, and Postgres does not restart by itself (R-029): after a Windows restart, start Ubuntu and run `make db-up`.

Hosting is deferred until development finishes (OWN-014). At that point the production origin is `https://ffa.westfam.media`, and Google needs `https://ffa.westfam.media/auth/callback` registered as a redirect URI. The worker's database guard currently allows local databases only and will need a production path then. Second-member acceptance moves to that release gate unless a member signs in on this machine.
