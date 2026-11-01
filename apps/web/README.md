# Arbit member client

React19/TypeScript/Vite, React Router and TanStack Query consume [generated API contracts](src/generated/api.ts) and [shared tokens](../../packages/design-tokens/tokens.json). Front Office, player facts, watchlist, preferences, administrator access controls and static-only PWA behavior are implemented. Draft/Scout/Market/Lineup/Archive state plainly that they are not built; no fake analysis is shown.

See [member application operations](../../docs/engineering/member-application.md) for Google configuration, the isolated fictional preview, validation and release prerequisites. `pnpm check:web` runs client checks/build; `pnpm test:pwa` verifies network-only private paths. Production browser verification uses `pnpm --filter @arbit/web test:browser` against the dedicated fixture application.

Visual system: officiating and broadcast, per [ADR-005](../../docs/architecture/decisions/005-officiating-character.md) and the [design system](../../docs/design/design-system.md). Big Shoulders and Libre Franklin are self-hosted OFL releases with packaged notices. `pnpm check:design` enforces token-only styling and bans slogan copy. No Gridiron or NFL media is reused yet.
