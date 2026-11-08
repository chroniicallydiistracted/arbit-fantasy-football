# Handoff · 2026-11-07 · Local Live animation preview activation

The owner requested the new renderer and choreographer on the local app for Thursday's Jacksonville–Baltimore replay, limited to the web stack (OWN-056). The opt-in game URL is `http://127.0.0.1:8000/live/games/401873037?script_version=2`. A saved play selection adds `&play=4018730373140` for the kickoff return and recovery. LV-003 and LV-005 apply. The default animation stays on the existing renderer pending the full rebuild gates.

## Activation and rollback

The browser build and API source snapshot were staged in the worktree under `.superpowers/releases/live-animation-preview-2026-11-07`. The member API service uses that snapshot and browser build through the user service override `arbit-api.service.d/30-live-animation-preview.conf`. The prior bundle and original source checkout remain available for rollback. Remove that override, reload the user service configuration and restart only the member API to restore the prior web stack. No database migration or worker restart was needed.

The member API restarted at 23:50 MST. The sync worker stayed active on PID 285 throughout. The prior API PID was 284 and the replacement PID was 245234. The new browser bundle is `/assets/index-DGdPl8Fd.js`.

## Verification

- Ran the icon generator, `node ../../scripts/web/tokens.mjs --check`, `node_modules/.bin/tsc -b --noEmit` and `node_modules/.bin/vite build --outDir` against the staging directory. All exited 0.
- The fixture preview on port 8027 passed five `node_modules/.bin/playwright test live-playback.spec.ts` scenarios. The staged real API on port 8029 passed readiness, served the staged HTML and required sign-in for animation and art. The initial check expected a query validation response on an anonymous request. Auth runs first and returned 401. The API schema separately verified the script version parameter and upper bound.
- Read-only Thursday replay build using the staged source verified 170 entries with NFL lineage. The opt-in path returned 88 eligible v2 clips and 50 existing clips. All six original audit plays used v2. The kickoff included receipt, loose ball and recovery.
- After the restart, port 8000 returned readiness. The replay page, JS bundle and service worker matched the staged files byte for byte. Anonymous animation and art returned 401. The production browser was outside the automated suite.
- `python3 scripts/validate_foundation.py` and `git diff --check` passed.

The default activation gate remains open for complete play-family coverage, directional art, held-out comparison and live delivery measurements. [Preview implementation](2026-11-07-live-animation-rebuild-preview.md) · [Implementation plan](../../superpowers/plans/2026-11-07-live-animation-rebuild.md).
