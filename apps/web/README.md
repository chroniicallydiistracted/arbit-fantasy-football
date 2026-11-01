# Arbit member client

React19/TypeScript/Vite, React Router and TanStack Query consume [generated API contracts](src/generated/api.ts) and [shared tokens](../../packages/design-tokens/tokens.json). Front Office, player facts, watchlist, preferences, administrator access controls and static-only PWA behavior are implemented. Draft/Scout/Market/Lineup/Live/Archive clearly identify their future capability; no fake analysis is shown.

See [member application operations](../../docs/engineering/member-application.md) for Google configuration, the isolated fictional preview, validation and release prerequisites. `pnpm check:web` runs client checks/build; `pnpm test:pwa` verifies network-only private paths. Production browser verification uses `pnpm --filter @arbit/web test:browser` against the dedicated fixture application.

Visual direction: warm paper, ink/deep green, an original field-inspired Arbit mark, Newsreader display type and Instrument Sans body text. Fonts are self-hosted OFL releases with packaged notices; no Gridiron/NFL media is reused.
