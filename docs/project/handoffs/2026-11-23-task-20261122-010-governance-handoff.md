# Task handoff — TASK-20261122-010 — Fix the flaky Live playback browser test (route.fetch after test end)

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** The fictional member browser journey no longer fails at random: route handlers that fetch from the server finish or are ignored before a Live playback test tears down

**Requirements:** LV-001, GOVAI-006

**Change class:** web

**Scoped files:** apps/web/tests/browser/live-playback.spec.ts, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Run 45089822359 (Runtime validation, push, e944420) failed in 'Run fictional member browser journey': live-playback.spec.ts:281 'a partial replay draws the verified action and explains what is unknown' threw 'route.fetch: Test ended. Consider awaiting page.unrouteAll({ behavior: ignoreErrors })'. The pull_request run of the same commit passed; main d9f95ec passed. openPlayback routes **/plays?* through route.fetch() to the real server, and the page re-requests plays as the stubbed event stream reconnects (retry: 50), so a fetch can be in flight when the last assertion passes. Spec from 8074c8f; no afterEach or unroute anywhere in tests/browser.

Files: apps/web/tests/browser/live-playback.spec.ts, apps/web/playwright.config.ts, .github/workflows/runtime.yml, docs/engineering/member-application.md

## Plan

Add test.afterEach that awaits page.unrouteAll({ behavior: 'ignoreErrors' }) in live-playback.spec.ts. Prove locally on an isolated stack: scratch DB arbit_browser_fixture (seeded by arbit_api.fixture), client built to a scratch outDir, API on 127.0.0.1:8011, Playwright via ARBIT_BASE_URL and the installed headless shell; run the spec with --repeat-each before (expect at least one Test ended failure) and after (expect none). Then web-check and foundation; CI reruns the full browser journey.

Files: apps/web/tests/browser/live-playback.spec.ts

## Implement

Added test.afterEach awaiting page.unrouteAll({ behavior: 'ignoreErrors' }) with a comment on the cause (7 lines, live-playback.spec.ts). Isolated stack: scratch DB arbit_browser_fixture seeded by arbit_api.fixture, client built to scratchpad outDir, API on 127.0.0.1:8011, owner app on :8000 untouched. Without the fix: --repeat-each 40 passed 200/200 (race too rare locally); with a temporary random 0-1200 ms delay before route.fetch, 22 failed / 38 passed and 21 errors were exactly 'route.fetch: Test ended.'; with the fix and the same delay, 60/60 passed. Delay removed (no TEMPORARY lines); full browser suite 16 passed. Status and changelog updated.

Files: apps/web/tests/browser/live-playback.spec.ts

## Validate

Observed exit 0: foundation; web-check (Biome lint and format, typecheck, Vitest, build, PWA); browser-suite-isolated (full Playwright suite, 16 tests, against the isolated fixture stack on :8011). Reproduction evidence in implementation. Isolated API stopped and scratch database dropped afterwards; owner app :8000 returned 200 throughout. CI reruns the browser journey on push and PR.

Files: not separately listed

## Document

Status line under Running now; changelog entry with cause, fix and proof. Written before validation; unchanged since.

Files: docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T01:01:11Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=64764660c2cae425384faadeae6c046075da4259e761c848060d3e6ddccf4e59
- `web-check`: exit=0, 2026-11-23T01:01:16Z; argv=["make", "web-check"]; output SHA-256=48128e7fc66150f7e49325de47f44846a56e76f65eb13f4bba5d05015ce55fe6
- `browser-suite-isolated`: exit=0, 2026-11-23T01:01:41Z; argv=["bash", "-c", ". /tmp/claude-1000/-home-andre-arbit-fantasy-football/2ce75ffa-5c13-4be1-b560-0af3d67cef32/scratchpad/browser-env.sh && cd apps/web && pnpm exec playwright test --reporter=line --workers 1"]; output SHA-256=5d7194031deee3992b0fc0f859988d962cf4dea3741980beee2fef327211b03c

## Findings / decisions / contradictions

- 2026-11-23T01:01:56Z [observation] The race reproduces only when a route.fetch is in flight as teardown begins; a fixed 1.5 s delay did not reproduce it (the callback woke after the page closed), a random 0-1200 ms delay did (21 exact errors in 60 runs). — Local Playwright runs against 127.0.0.1:8011, 2026-11-23

## Remaining unresolved / blocked

None for this test. Other browser specs have no route.fetch handlers.

## Next executable action

Merge PR #3 once validate, runtime and governance pass; fast-forward main, restart arbit-worker; remove the merged worktree and local branches (TASK-009 next step); then M3 slice 3 with weather W1.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
