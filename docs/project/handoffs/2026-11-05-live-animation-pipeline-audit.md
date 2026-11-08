# Handoff — 2026-11-05 — Live animation pipeline audit

The owner requested an end-to-end audit to identify corrections and missing play templates. The [audit report](../../research/live-animation-pipeline-audit-2026-11-05.md) traces LV-001–005 from raw NFL records and stored revisions to production scripts, the board, private art and the browser. It names the confirmed failures, play IDs and regression cases in repair order.

## Verification and reproduction

From the repository root, with the existing loopback PostgreSQL service and the owner-private captures available:

- `uv run --frozen --env-file .env.local python data/nfl-api/animation-audit-2026-11-05/pipeline.py` exited 0. The SQL connection defaulted to read-only transactions. The script checked 4,919 NFL scripts and the separate 144 mixed-source scripts. Its receipt contains all 11 rule flags, 67 missing NFL clip cases, and the Thursday revision comparison.
- `uv run --frozen pytest -q libs/arbit-data/tests/test_{nfl_api,play_facts,choreography,kicks_fumbles_penalties,pacing,board}.py tests/contracts/test_sprite_{uniforms,frames}.py tests/integration/test_{live_review_regressions,live_store,nfl_lane}.py` passed 447 tests.
- `pnpm --filter @arbit/web test:browser` passed 11 tests against the fixture application on port 8014. The test used the explicit fixture database and a private copy of the installed distribution for its PWA update test. Only the fixture score was reset or changed.
- `pnpm --filter @arbit/web exec vite build <private-audit-dir>/harness --outDir <private-audit-dir>/renderer` succeeded. Served the harness on loopback port 8015. `node <private-audit-dir>/browser.cjs` sampled 2,912 frames from 420 clip instances and reproduced the terminal ball disappearance without draw exceptions. `node <private-audit-dir>/playback.cjs` reproduced reduced-motion and replay-selection failures through the isolated client's event listeners. `node <private-audit-dir>/transport.cjs` verified session gating and recorded the local payload measurements.
- `python3 scripts/validate_foundation.py` and `git diff --check` passed.

The private audit directory is `data/nfl-api/animation-audit-2026-11-05/`. It contains the scripts, receipts and sample frames. Gridiron images and raw/provider-derived replay material remain local. The running worker kept the same PID during the audit. The tested browser was Chromium, and the controlled event sequences used archived play payloads.

## Resume here

Start with R-046 to protect the confirmed NFL final and restore a clean Thursday replay through the normal ingestion path. Use R-047 for the browser lifecycle fixes. R-045 and R-048 list the missing play, try and board-state cases. The existing [field layout](2026-11-05-live-field-layout.md) and [fresh polling](2026-11-05-nfl-fresh-polling.md) handoffs cover the preceding changes. These open issues block complete M6 acceptance.
