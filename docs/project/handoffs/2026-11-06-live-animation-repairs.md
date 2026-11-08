# Handoff — 2026-11-06 — Live animation audit repairs

The owner confirmed three presentation choices (OWN-047). Stoppages update the Jumbotron in place. A removed replay stays selected with corrected text and a No Play notice. A partial re-creation shows the verified action and result, with the unknown part available in text. The [repair plan](../../superpowers/plans/2026-11-06-live-animation-repairs.md) implements these choices and the [audit](../../research/live-animation-pipeline-audit-2026-11-05.md).

## Implementation

- Migration `0009_nfl_detail_phase` adds a marker for the phase of an accepted NFL detail. It leaves older phase hints and revision history intact. The worker validates a usable final, reconciles fallback-only rows in the same transaction and fences late ESPN and NFL writes. Unconfirmed linked final games remain eligible for verification across week rollover. Changed final summaries retry if the detail is still live or incomplete.
- The facts parser separates observed action spots from the next snap, understands the four-letter NFL team alias, and uses the effective reviewed result. Independent tries keep their own metadata, scoreboard and timing. Direct snaps to the eventual passer use the normal pass continuation. Direct snaps with an unconfirmed exchange, laterals, complex fumbles and blocked punts use labeled partial action and original text.
- The browser uses play ID and part across log navigation and event refreshes. Reduced motion follows each arrival, the terminal ball remains visible, and standalone board state replaces the board in place as the latest scene settles. The log opens a play directly and can load up to 400 rows.
- Game events scope invalidations by event ID. Unchanged replay entries reuse their browser scene. Large animation payloads negotiate gzip, with session checks and private cache policy. Art builds stage all six files, publish an atomic content-addressed revision and label each fallback independently.

## Verification

- `npm exec --offline --yes --package=pnpm@12.16.1 -- make runtime-check` passed 1,208 tests, foundation, Ruff, mypy and contract validation. The focused PostgreSQL pass covered 71 tests across the NFL lane, live store and migration. The final validator also accepted all 30 archived NFL final responses, including three overtime games.
- Generated client, design, Biome, TypeScript, 23 web unit tests, isolated Vite build and PWA checks passed. Biome reported three existing reduced-motion CSS warnings. `pnpm --filter @arbit/web test:browser` passed all 15 tests against the fixture application on port 8017 with an explicit staged dist path and the migrated fixture database. Browser tests exercised reduced motion, terminal ball, corrected and cancelled selections, partial text and in-place board updates.
- The archived `repairs.py` replay in `data/nfl-api/animation-audit-2026-11-05/` found 4,660 eligible NFL clips versus 4,593 in the baseline. The prior 67 omissions have full or partial clips. The rule and spot checks recorded zero remaining flags in this sample. The script separately reads the currently stored mixed-source Thursday replay for comparison. The private Chromium renderer sampled 2,980 frames across 431 clip instances in three matching-art replay sets. It found no draw errors, missing atlas rectangles, missing hand anchors or terminal ball loss.
- The isolated animation response returned 401 without a session and used gzip, `Vary: Accept-Encoding` and private no-store policy after sign-in. The artwork smoke test built the same six-file revision twice with the same content hash, explicit per-team and field labels and distinct neutral kits. Artwork and verification payloads stayed private.

## Local release

- The owner approved activation (OWN-048). A private `pg_dump -Fc` of `arbit_local` passed `pg_restore -l`; the prior dist was saved alongside it in `data/backups/2026-11-06/live-animation-214804/`. The API and worker were stopped outside a live game window, and `uv run --frozen --env-file .env.local alembic upgrade head` applied `0009_nfl_detail_phase`.
- The API and worker were active and the API returned ready at 21:48:10 Arizona time. The live game page matched the staged HTML, and the JavaScript `index-Bqkloj5L.js`, stylesheet `index-DntqWtZR.css` and service worker matched the installed files byte for byte.
- At 21:48:12 Arizona time the normal worker confirmed a fresh Jacksonville–Baltimore NFL final. Read-only SQL verified 166 current NFL rows, zero current ESPN rows and 126 current rows with both snap and whistle times. The previous ESPN revisions remain in history. A read-only run of `animation.build` on the actual local database returned 170 entries, 138 playable clips including three partials, and a Final Jumbotron at Jacksonville 33–Baltimore 10.
- The owner kept natural movement when the generated action takes longer than the recorded whistle. This resolves the presentation choice for the 491 affected full-motion clips in the audit.

## Week 9 field art

The owner chose exact fields where available, otherwise the most-used verified field at that venue in the current regular season. Most recent use breaks ties. Miami and Seattle both used their Week 8 fields under that rule. The latest Week 8 and 9 listings were captured directly from Gridiron, and Week 1–7 captures supplied earlier uses. [Week 9 listing](https://www.gridiron-uniforms.com/GUD/controller/controller.php?action=weekly&league=NFL&week=9&year=2026).

- `uv run --offline --with pillow --with numpy --with pyarrow python data/gridiron/2026/activation-2026-11-06/build_slate.py` staged 15 bundles. Baltimore and Indianapolis use their exact listed fields, 12 use labeled season-use variants, and Madrid uses a labeled plain field. Madrid's listed image returned HTTP 404 at both published sizes. Twenty-six of 30 kits were exact, and four unlisted kits use labeled plain uniforms.
- `node data/gridiron/2026/activation-2026-11-06/check_art.cjs` checked all 90 files byte for byte over authenticated HTTP against the isolated app on port 8020. The same route returned 401 without a session. All 15 verified private bundle pointers were promoted at 21:54:30 Arizona time. The local API remained ready and its anonymous art route returned 401.
- The capture, source checksums, per-game variant choices and prior pointer record are private under `data/gridiron/2026/activation-2026-11-06/`. R-043 tracks Madrid and unlisted kits. R-042 still requires simultaneous live games to measure arrival latency and slate request volume.

## November 7 wake check

PostgreSQL was healthy and the original API and worker processes were running after wake. The served HTML, assets and service worker matched the release, and `arbit_local` remained on migration 0009. Jacksonville–Baltimore still had 166 current NFL rows, 126 with both timestamps. The NFL lane resumed successful Week 9 summary polls at its five-minute idle cadence.

The refreshed Gridiron listing changed one matchup since activation. Denver's exact B3 kit was verified against the private archive checksum and published for Denver–Carolina. The isolated signed-in route served six matching files, and the live art pointer was replaced atomically. The slate now has 27 exact kits and three labeled plain kits. Madrid's listed field still returned HTTP 404 at both sizes. The new listing and receipt are private under `data/gridiron/2026/verification-2026-11-07/`. [Week 9 listing](https://www.gridiron-uniforms.com/GUD/controller/controller.php?action=weekly&league=NFL&week=9&year=2026).
