# Handoff — 2026-11-05 — Live platform release on main

The owner requested publication of the Live work, integration of all branches into `main), and a refresh of the local app and databases. The [Week 9 handoff](2026-11-05-live-feed-observation.md) has the capture paths, analysis command, and remaining live evidence.

## Git history

- `d34d19c` records the NFL collector, the real-time game renderer, and the observation tools on published branch `claude/platform-reset`.
- `cb417d1` adds the `claude/sprite-art` branch as a merge parent. All 19 paths changed by its original commit matched the copy already incorporated at `600a258`. The merge keeps the newer platform files and has the same source tree as `d34d19c`.
- Every local and remote-tracking branch tip present before the release is reachable from `main`. The remote had zero open pull requests when checked.

## Local release

The local API and worker started from the merged code at **17:56:57 Arizona time**, before the 18:15 kickoff. The API returned `{"status":"ready"}`. The live game page referenced `index-CxwOYkhC.js), and HTTP responses for that asset and `sw.js` matched the new staged build byte for byte. The separate Week 9 browser recorder stayed active. Its existing cutoff is 23:00 Arizona time.

| Database | Result |
|---|---|
| `arbit_local` | Backed up and verified at Alembic head `0008_nfl_api`. `alembic upgrade head` required no schema changes. |
| `arbit_fixture` | Backed up and migrated from `0006_members` to `0008_nfl_api`. |
| `arbit_member_fixture`, `arbit_nfl_test` | Both already at `0008_nfl_api`. The browser suite used the member fixture. |
| `arbit_test` | Integration tests create and migrate their own isolated schemas on each run. |

Owner-only backup files for the app and older fixture database are in `data/backups/2026-11-05/` with the prefix `before-main-175459-`. Both passed `pg_restore -l`. The previous web build is in `web-before-main-175651` under the same directory.

## Verification

- `uv sync --frozen` and `make db-up` succeeded.
- `npm exec --offline --yes --package=pnpm@12.16.1 -- make runtime-check` passed on the merged tree with 1,181 tests, foundation, Ruff, mypy, and contract checks.
- Generated client, design, Biome, TypeScript, 22 web tests, the staged production build, and the PWA test passed. The isolated member browser suite on port 8011 passed all 11 tests.
- Local HTTP readiness and byte comparisons verified the served web release after startup. The worker's NFL lane rediscovered the Week 9 schedule.

R-042 remains open for the actual in-game comparison and full-slate request budget. Run the [postgame analysis](2026-11-05-live-feed-observation.md#after-the-game) after the capture window.
