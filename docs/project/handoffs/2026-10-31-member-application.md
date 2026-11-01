# M2 member application handoff — 2026-10-31

Branch `codex/m2-member-application`, based on M1e commit `08d2e29`. Plan/policy commit: `85887c0`; Sleeper correction: `4e51ceb`. No push, merge, deployment, external registration or outbound messages. The owner selected Google. Every delegated task and review used GPT-6.1 Sol only.

## Implemented locally

- Retired all active Sleeper fantasy directory/state/trend/stat/hint acquisition and mapping. Legacy commands fail before cache/network access. Historical receipts remain audit-only. No eligible Sleeper live/PBP route is enabled; verified ESPN game/PBP paths remain available.
- Added migration `0006_members`: issuer+subject accounts, hashed invitations and opaque sessions, one-use browser-bound OIDC state/nonce/PKCE, audited manager bindings, bounded revisioned preferences and safe access audit records. Google-compatible authentication uses maintained Authlib/joserfc validation and bounded requests to fixed provider hosts.
- Added authorized member and administrator APIs with generated OpenAPI/TypeScript. Facts preserve nullable Decimal totals, source status and one canonical snapshot. Historical matchups with no captured lineup withhold the roster. Player inspection pins its snapshot. Invitations never assign teams automatically; binding changes revoke sessions. Suspension/reactivation protects the last active administrator, including concurrent requests.
- Built the React Front Office, player drawer/search, watchlist, themes and administrator controls. Warm paper/deep green, self-hosted OFL typography and an original SVG mark follow the design system. Future modules identify their status; no analysis, projection or recommendation is invented.
- Added same-origin static serving, explicit public file allowlists, CSP, generated install icons, manifest and controlled PWA updates. Static assets alone are cached. Offline, expiry, account/session replacement and logout clear private memory; offline navigation shows only the neutral connection page.

See the [plan](../../superpowers/plans/2026-10-31-member-application.md), [operator guide](../../engineering/member-application.md), [API contract](../../architecture/api-contracts.md) and [design system](../../design/design-system.md). The source brief is unchanged; owner decisions supersede earlier source interpretations.

## Validation

| Command | Actual result |
| --- | --- |
| `uv sync --frozen`; pinned `pnpm install --frozen-lockfile` | Frozen installs passed |
| pinned `make runtime-check` | Foundation, Ruff (137 files), strict mypy (77 source files), AJV and **453 pytest tests passed**, 22.29 seconds |
| pinned `make web-check` | Generated OpenAPI/TypeScript/token drift, Biome, strict TypeScript, **14 unit/component tests**, production build and static-cache negative test passed |
| pinned `pnpm --filter @arbit/web test:browser`, using `ARBIT_BROWSER_PATH` | **7 Chromium scenarios passed**, 15.0 seconds, final server and production build |
| populated local compatibility verifier under `.env.local` | Additive migration and exact existing source/canonical content preserved; actual member account count remained zero |
| `python3 scripts/validate_foundation.py` | Links, requirement traceability, semantic contrast and unchanged owner-brief checksum passed |

Browser evidence covers two fictional members and foreign-team denial; unknown versus historical official scores; watchlist, theme, sign-out and focus restoration; 320/768/1280/1600 px rendering with automated accessibility; 200% type reflow and reduced motion; static-cache exclusions, offline private clearing/fallback and explicit worker update. The final additional scenario replaces the shared session cookie with another fictional member, verifies the old private deep link cannot retain cached facts, and exercises an apostrophe search.

Native OS installation and a human screen-reader pass were not performed. Accessibility-tree, keyboard and axe checks support the implementation; they are not WCAG certification. CI now runs the frozen runtime/web/browser checks against an ephemeral database, but it was not run remotely. Build sizes are approximately 105 kB gzip JavaScript and 6 kB gzip CSS, plus self-hosted fonts; these are not measured load/freshness SLOs.

## Data preservation and fixture distinction

The actual local database upgrade from `0005_public_sources` to `0006_members` preserved the canonical document digest and counts: 1 league snapshot, 19,008 canonical entities, 35,505 aliases, 1,140 dataset manifests and current pointers, and 25 public source observations. Native serving-model validation confirmed 8 FFA teams, 1,055 current player facts and 132 rostered entries. No real member account or fixture identity was created there; no real member HTTP access was bypassed. This proves stored-data compatibility, not Google sign-in.

The dedicated `arbit_member_fixture` database contains 2 fictional members, 2 teams and 34 players. An earlier seed attempt safely refused the older `arbit_fixture` dataset; only the additive migration was applied there, preserving its existing snapshot. Integration tests use disposable random schemas. Neither synthetic scores nor mocked provider exchanges are presented as actual source/provider proof.

## Independent review and fixes

One independent GPT-6.1 Sol review found two Important/P2 issues and one Minor/P3; no Critical findings. All were addressed in one fix pass:

- Account/session replacement now cancels and clears queries and remounts private component state before publishing a replacement identity. Unit and actual shared-cookie/deep-link browser regressions pass.
- Transport validates normalized same-origin paths separately from query values, allowing `Ja'Marr` and `D'Andre` searches. Apostrophe-name regressions and a real browser request pass.
- Existing fictional accounts sign in without creating unused invitations. Repeated preview login/reseed preserves the complete prior invitation inventory in a PostgreSQL regression.

The three new client regressions failed before the fixes, then passed. The fixture regression likewise failed before its fix. No checks were disabled. Intermediate validation also caught and corrected login refresh behavior, browser readiness/label assertions, missing install/offline assets, generated CSS formatting drift and an accidental planning-file overwrite. The planning files were restored from their verified baseline with scoped additions; final source/brief/reference validation passes.

## Remaining operational gate and next stage

M2 code and local verification are complete. Actual member release requires an owner-controlled Google Web OAuth client/consent configuration, private local client ID/secret entry, a real invited administrator round trip, approved FFA manager binding and verification with a second actual member. No client or project was registered. Use the [configuration template](../../../config/google-auth.env.example) and operator guide; never send secrets in chat. Production requires HTTPS and complete OIDC, and refuses fixture mode and local operator-token access. Hosting, TLS, backups/restore and load acceptance remain separate release work.

After that operational gate, M3 defines point-in-time semantic features, missingness/coverage policy and temporal model validation on the imported NFLverse foundation. Recommendations remain disabled until shared scoring, identity, ownership freshness and model evidence satisfy their gates. M6 still owns active-game timing/corrections/full-slate Live and verified Gridiron reuse.

Only local commits were created. Fixture API/browser processes are stopped; the existing PostgreSQL service remains available. The next contributor can start from the operator guide without relying on chat history.

## Google configuration follow-up — 2026-10-31

The owner has now created the Google client. The owner-provided `config/google-auth.env` was moved safely to root `.env.auth.local` with mode 600; both the final profile and its former path were confirmed excluded from Git, and neither was tracked. The separate downloaded credential backup remains outside the workspace and was not accessed. A `uv run python` check loaded the two private profiles, validated `RuntimeSettings`, then used local `TestClient` reads of `/health/ready` and `/auth/status`: ready, OIDC enabled, fixture mode false and unauthenticated. Credential values were not printed; no provider request, administrator invitation or real member login occurred. First-administrator identity/invitation and actual Google/member acceptance are the next operational steps.
