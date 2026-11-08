# Handoff — 2026-11-05 — Game strip, field and Jumbotron

The single-game page uses the existing game cards in a horizontally scrolling row. The selected card scrolls into view when the selection changes, and moving keyboard focus follows the cards. The field uses the full content width. The Jumbotron is the main visual scoreboard while a clip supplies board state. The readable score stays available to assistive technology. The secondary board opens below the field for the live game state, score by quarter and game details. It appears above the field when the Jumbotron is unavailable. [Plan](../../superpowers/plans/2026-11-05-live-field-layout.md) and [owner decision](../decision-register.md#confirmed-product-decisions).

## Verification

- `pnpm check:client`, `pnpm check:design`, `pnpm --filter @arbit/web lint`, `pnpm --filter @arbit/web test` (22 tests), and `pnpm test:pwa` passed. `tsc -b` and `vite build --outDir` built the isolated release. Biome reported the three existing reduced-motion style warnings. `python3 scripts/validate_foundation.py` and `git diff --check` passed.
- `pnpm --filter @arbit/web test:browser` ran with the fixture database and staged dist path on port 8013 and passed all 11 tests. A first rerun omitted the stage and fixture variables. Its PWA test temporarily wrote to the old service worker and restored it in its cleanup. The fixture write was refused. The corrected run used the dedicated fixture database and staged service worker for both tests.
- A separate browser check used CHI at SEA on the isolated app. At a 1280px viewport, the canvas grew from 942×302px to 1214×389px. The 256px card width and sampled visual styling matched. At 320, 390, 768 and 1280px, all 15 cards occupied one scrolling row without page overflow. Keyboard scroll and replay, the score disclosure, screen-reader score, and the visible scoreboard when art was missing, the art request failed or the canvas failed all passed.
- The audit ran the production normalizer and animation builder on 5,881 raw NFL records from 31 games. It found 4,593 canvas-eligible clips and 67 football actions or tries without a clip. All 328 cancelled records stayed text-only. The private script and counts are in `data/nfl-api/play-coverage-2026-11-05/`. [Coverage and cases](../../research/live-play-coverage-2026-11-05.md).

## Local activation

The verified build was loaded at **23:24:30 Arizona time**. The game page matched the staged HTML, and HTTP responses for `index-ByM84CIO.js`, `index-DntqWtZR.css` and `sw.js` matched the installed files byte for byte. The API returned ready. The NFL worker stayed active with PID 739522 throughout. This was a web release with no database migration. The prior build is backed up in `data/backups/2026-11-05/web-before-layout-232424/`.

Full M6 play coverage remains open under R-045. Sunday live latency and slate-wide cadence remain open under R-042. [Fresh-poll worker handoff](2026-11-05-nfl-fresh-polling.md).
