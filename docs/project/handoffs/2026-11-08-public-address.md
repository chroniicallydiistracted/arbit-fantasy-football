# Handoff — 2026-11-08 — The app's public address

## Current state

**Live.** The app on this PC is served at `https://ffa.westfam.media` (OWN-058, ENG-049), and that is its only sign-in address.
- **Path:** browser → Cloudflare → the owner's existing Cloudflare Access (team `chroniic`) → tunnel `arbit` → `arbit-tunnel` user service → `127.0.0.1:8000`.
- **Owner decisions:** the owner first chose Wi-Fi-only access through their domain, then the same day asked for the full public address instead. They kept Access in front and approved switching during the late games.
- **Unchanged:** choosing a hosting platform is still deferred (OWN-014). The API still runs Codex's release snapshot `live-animation-motion-2026-11-08` through its systemd drop-in.

## Completed work

- **`infra/tunnel/`:** `config.yml.template`, `arbit-tunnel.service.template` and `install.sh` (with `--remove`). The installer:
  - creates or reuses the tunnel `arbit`, leaving the account's other tunnels alone
  - renders `~/.config/arbit-tunnel/config.yml` and checks its ingress rules
  - starts the user service and routes the DNS name
- **Operator reads:** `/internal/league/*` only checks for a loopback caller plus the operator token. Every tunneled request comes from loopback, so the tunnel answers `^/internal` with 404 itself.
- **External state:**
  - Cloudflare tunnel `arbit`, ID `0ecfd9a0-6db4-40b8-9acf-79ba83ac7378`
  - proxied CNAME `ffa.westfam.media`
  - user unit `arbit-tunnel` (enabled)
  - credentials at `~/.cloudflared/<id>.json`
- **App address:** `.env.auth.local` now has `ARBIT_PUBLIC_ORIGIN=https://ffa.westfam.media`. The backup is `data/backups/2026-11-08/env.auth.local.before-public-origin` (mode 600).
- **Records:**
  - OWN-058 and ENG-049 in the decision register
  - R-052 and R-053 in known issues
  - the "Public address" section of the operations guide
  - status, changelog, and the hosting sentence in `AGENTS.md`
- **Wi-Fi plan:** `infra/wifi/` was written, then deleted when the owner changed direction. Nothing from it was installed.

## Verification

- **Before going public:**
  - `cloudflared tunnel --config <scratch> ingress validate`: OK.
  - `ingress rule` sends `/internal/...` and `/%69nternal/...` to `http_status:404`, the app's paths to `http://127.0.0.1:8000`, and other hosts to 404.
  - Case and double-slash variants pass the tunnel, but the app answers them with 404.
- **Response caching:** with the dev account, every `/api` response, Gridiron art included, is `no-store, private`. Only `/assets/*` is public and immutable. The event stream's heartbeat is 20 s.
- **Released code:** with the snapshot's source, `RuntimeSettings` accepts the HTTPS origin and sets Secure cookies, and the loopback redirect doesn't fire behind the proxy. A plain-HTTP Wi-Fi origin is refused ("loopback-only").
- **Installer run:** `sh infra/tunnel/install.sh`, run with the owner's explicit permission, exited 0.
  - Four tunnel connections registered (lax01/07/10/13).
  - `ffa.westfam.media` resolves through 1.1.1.1 and 8.8.8.8 to Cloudflare. The local resolver still held the earlier no-such-name answer, so these checks used `curl --resolve`.
  - The certificate is Google Trust Services WE1, expiring 2027-01-04.
  - Every path returns 302 to `chroniic.cloudflareaccess.com`: Access gates the name.
- **Switch at 13:17:52 MST (owner-approved):** back up, edit one line with `sed`, then `systemctl --user restart arbit-api`.
  - The API was ready about 6 s later. Its new PID is 474594, and the worker kept PID 285.
  - `/` and `/assets/index-RUW63baV.js` still match the release snapshot byte for byte.
  - `POST /auth/start` with an invalid body returns 422 for `Origin: https://ffa.westfam.media` and 403 for `http://127.0.0.1:8000`.
  - `make dev-account` issued a Secure cookie for `ffa.westfam.media`.
  - Four signed-in Live pages loaded on `127.0.0.1:8000` with no page or console errors and no failed requests (the cookie was rescoped to that host in a temporary copy, deleted afterwards).
  - Seven live games kept updating, with no worker errors.
- **Docs:** `python3 scripts/validate_foundation.py` passed.
- **Not run:** a Google sign-in at the new address, which needs the owner (R-053). Automated checks through the public address can't pass Access. The app's test suites weren't run, because no application code changed.

## Decisions, issues and limitations

- **Environment:** `ARBIT_ENV` stays `development`. `production` would refuse the configured operator token at startup and turn off the dev account.
- **R-052:** Access expiry is expected to stop live updates until a reload. The owner should set a long session for this Access application.
- **R-053:** the owner adds `https://ffa.westfam.media/auth/callback` in Google. A family member needs an Access allowance, an Arbit invitation, and a test-user entry if the consent screen is in Testing.
- **R-029:** the public site is down whenever this PC sleeps or WSL stops.
- **cloudflared:** version 2026.2.0 is installed at `/usr/local/bin`, and 2026.10.7 is available. Upgrading needs `sudo`.
- **Decision numbering:** `main` has OWN-054 twice. OWN-058 and ENG-049 were numbered to avoid Codex's OWN-055–057 on `codex/live-animation-rebuild`. Reconcile when the branches merge.

## Resume here

- **Owner checks:**
  - Done at 13:26 MST: the owner signed in from an iPad through Access and Google (one new session, labeled "Safari on Mac" by iPadOS). Still to do: this PC, and a second member (R-053).
  - The first Access expiry. Record it under R-052.
- **Rollback:** copy the backup over `.env.auth.local`, run `systemctl --user restart arbit-api`, and optionally `sh infra/tunnel/install.sh --remove`. The tunnel and DNS record stay in Cloudflare until the owner deletes them.

[Status](../status.md) · [Operations](../../engineering/member-application.md#public-address)
