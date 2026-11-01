# Handoff — 2026-10-31 — Design reset and real-time platform

## Current state

Branch `claude/platform-reset`, on top of the owner's published `61368fd`. Local commits only: no push, merge or deployment. Primary developer changed to Claude this session. The owner redirected work ahead of M3 (OWN-013–017): the design had drifted to AI-identifiable defaults, data went stale, and clients needed live refresh and a true session.

**Applied to the running app on 2026-11-01 04:26 UTC (2026-10-31 21:26 Phoenix), by the owner's decision.** `:8000` serves the new client on schema `0007_realtime`, and `arbit-api` and `arbit-worker` run as systemd user services with linger. The next real slate is Sunday 2026-11-01, first kickoff 18:00 UTC, which gives the first active-game evidence (R-025).

## How the upgrade went

The command the developer gave the owner was defective. It began with `pkill -f '<uvicorn command line>'`. The prompt's `!` prefix runs through `bash -c`, so that shell's own command line matched the pattern: it stopped the API, then killed itself before `make` started. The empty output gave it away, and the app was down until the developer ran the two remaining steps the owner had just issued. The command had not been tested before it was handed over. Nothing was lost, since the migration had not started.

Results: backup `data/backups/2026-10-31/before-upgrade-212549.dump`; migration to `0007_realtime`; client rebuilt; both units active and enabled, linger on, no restarts. `/health/ready` reports ready. The one usable session survived. The worker read 32 NFL teams, 272 games, 14 games with state and 197 plays into the real database, with no source failures. The real sign-in page loaded in Chromium with both fonts and no console, CSP or request errors.

Backups were being written world-readable (the dated directory happened to protect this one), so `make local-upgrade` now sets `umask 077`.

## Later upgrades

```sh
systemctl --user stop arbit-api arbit-worker
make local-upgrade
systemctl --user start arbit-worker arbit-api
```

`make services-remove` undoes the services. Without them, run `make member-api` and `make local-worker` in two terminals. An open or installed client keeps its old version until the user chooses **Update & reload**.

## Completed work

**Decisions:** OWN-013 replaces the Sol-only subagent rule with a cost ceiling. OWN-014 defers hosting, with production at `https://ffa.westfam.media`. OWN-015 records the private Gridiron permission, personal use only. OWN-016 and OWN-017 direct this work. ADR-005 sets the character. Requirements UX-005, DATA-008 and ENG-005 are added. [Design plan](../../superpowers/plans/2026-10-31-design-reset.md), [real-time plan](../../superpowers/plans/2026-10-31-realtime-sync.md).

**Design:** new tokens, mark, fonts (Big Shoulders, Libre Franklin), stylesheet, shell, sign-in, Front Office, drawer, preferences, admin and offline page. Top band plus bottom tab bar, replacing the left sidebar and closing a recorded spec deviation. All slogan copy replaced with plain statements. `pnpm check:design` fails on raw style values, banned fonts and slogans.

**Sync:** `arbit-worker run` with league, live and statistics lanes; cadence policy driven by the observed slate; per-host budgets; `source_health`; migration `0007_realtime`; NFL directory and schedule; live game state; append-only play revisions; final-game re-reads for corrections.

**Clients and sessions:** session-bound SSE with replay, expiry and revocation; query invalidation in place of timers, with polling fallback; per-device sessions, 30-day idle and 90-day absolute, with a device list in Preferences.

**Member features from real data:** Live scoreboard and plays with a my-players filter, NFL team/bye/opponent on roster rows, per-source status, season strip, playoff line.

**Bugs found through real data and fixed:** official totals showing `899.3000000000001`; standings and roster in provider ID order; pregame scores of 0–0; data age measured from last change rather than last confirmation; a sign-in on one device ending every other session; first-seen cancelled plays reported as corrections.

## Verification

Pinned Python 3.12.13, Node 24.22.2, pnpm 12.16.1, uv 0.11.33, local PostgreSQL. Browser tests used Chromium 1228 on an isolated port with `ARBIT_BASE_URL` and `ARBIT_WEB_DIST_PATH`.

| Command | Result |
| --- | --- |
| `make runtime-check` | Foundation, Ruff, strict mypy (84 files), AJV and **545 pytest tests passed** |
| `pnpm check:client`, `pnpm --filter @arbit/web lint`, `typecheck`, `test`, `pnpm test:pwa` | Passed; **14 client tests** |
| `pnpm check:design` | Passes. RED first: **436 violations** on the old interface |
| `pnpm --filter @arbit/web test:browser` | **10 scenarios passed**: 320/768/1280/1600 px, axe, 200% zoom, offline, update, account switch, **a server-side change reaching an open page without reload**, Live deep link and device list |
| `timeout 150 arbit-worker run --lanes league,live` | Real ESPN into a restored copy of the local database (`arbit_staging_test`, since dropped). Clean SIGTERM. Exit 124 is the time limit |

Real-data results on the copy: migration preserved all counts (2 snapshots, 19,008 entities, 35,505 aliases, 1,140 manifests, 1 session). 32 NFL teams, 272 games. Directory joined 132/132 owned players and 14/14 games by team and event ID. 197 plays from the completed game. All five sources reported correctly. The fictional fixture login was bound to a real manager on the copy to view real pages; no real sign-in was bypassed on the real database.

**Not verified:** behavior during a live game, since none was on (R-025). The statistics lane against the real source; its first real import comes due about 2026-11-01 09:57 UTC (R-026). Signed-in pages on the upgraded app, since only the owner holds that session. Recovery after a crash or Windows restart (R-029). Native install and a human screen-reader pass (R-023). Remote CI has not run. The new design has not had owner review (R-028). No independent reviewer ran; OWN-013 now allows it within the cost ceiling.

## Decisions, issues and limitations

Hosting: the worker's database guard allows local databases only and needs a production path at release. Live is text-first: no fantasy attribution, field graphics or Gridiron art, which remain M6. Raw live bytes aren't retained; normalized revisions are, to avoid several GB per NFL Sunday. Not yet synced: transactions and waivers, player news, positional ratings (R-027). Sessions: changing idle and absolute limits or the device cap is a one-line constant in `arbit_data/members.py`.

## Resume here

1. Owner reviews the rendered design on the upgraded app.
2. Read `journalctl --user -u arbit-worker`: confirm the first statistics import (R-026), then after the first live slate record latency and any correction pair as a research receipt and close R-025.
3. Run an independent review of this branch at or below the current model's cost (OWN-013).
4. Start **M3 Model/Scout**: create `libs/arbit-model` as a workspace member, settle the historical-vintage policy (Q-005) before any backtest, and weigh league timing in the [roadmap](../roadmap.md).
