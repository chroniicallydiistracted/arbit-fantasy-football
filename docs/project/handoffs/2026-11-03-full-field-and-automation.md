# Handoff — 2026-11-03 — Full-field view, the ball, the dev account and the automation plan

## Current state

Branch `claude/platform-reset`, local only and not pushed. Commits on top of `053a917`:

- `2e0ab6e` sprites
- `91e5b66` dev account
- a docs commit holding this handoff

**The running app was upgraded at 17:50** with the owner's approval. It was offline 25 seconds; a backup was taken first (`data/backups/2026-11-03/before-upgrade-175041.dump`) and no migration was needed. It now has the read-only dev account (ENG-031) and the R-036 sign-in fix.

Owner reviews today:
- **OWN-029.** Accepted the real uniforms and asked for the full field.
- **OWN-030.** Made the full field the standard and asked for good kicks to go through the posts.
- **OWN-031.** Asked for the ball to fly like a real one.
- **OWN-032.** Wants Claude on the live app through a dev account, not a copy. Skips NGS tracking for now. Keeps only the players in the play, after a family member found it easier to follow.

The automation [plan](../../superpowers/plans/2026-11-03-live-play-automation.md) is **proposed**; none of it is built.

## Completed work

- **Sprites** (`2e0ab6e`; ENG-028–030).
  - The full-field camera is the default in `real_plays.py`.
  - Players, goalpost pieces and the ball are drawn in depth order.
  - `kick_through` and `place_kick` handle the kicks, including two real extra points.
  - `Ball(at, spin, since, depth)`: spirals for passes, snaps and punts; end-over-end tumbles for place kicks; upright for the hold; flat at rest.
- **Dev account** (`91e5b66`, ENG-031).
  - `make dev-account` gives the account, issuer `urn:arbit:observer`, one session of 12 hours (24 at most). It goes to `data/observer/storage-state.json`, mode 600, for Playwright. The token is never printed.
  - The account counts as on every team, so the Front Office team switcher opens any manager's view, and it reads the administrator pages.
  - The API refuses its changes except to its own preferences and signing out (`OBSERVER_READ_ONLY`), and ignores it in production.
  - `make dev-account-end` ends its sessions. The administrator can also suspend it in League access.
  - Docs are in `docs/engineering/member-application.md`.
- **The copy-based dev view was removed.** The owner doesn't want a copy. Its code was reverted before it was ever committed, its server stopped, and `arbit_devview_test` dropped.
- **NGS** ([research](../../research/ngs-highlights-2026-11-03.md), SRC-22). Skipped for now (Q-011 resolved).
- **Records.** OWN-029–032, ENG-028–031, R-029 (database restart, merged), R-036 (shipped), R-039, the plan (supporting players on hold), the changelog and status.

## Verification

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 613 passed, including 4 dev account tests: every team, admin read, refused changes, sessions ending, suspension, production, and the session file |
| `uv run ruff check .`, `ruff format --check .`, `mypy`, `pnpm check:client`, `check:design`, `check:contracts`, `make check` | Passed |
| Web: `vitest run` | 22 passed, including the read-only League access test |
| `pnpm --filter @arbit/web test:browser` against a fictional preview on `:8011`, with a client built in the scratchpad | 11 passed. The running app's `sw.js` checksum is unchanged |
| `systemctl --user stop …`, `make local-upgrade`, `systemctl --user start …` | Backup written, already at `0007_realtime`, client built. Both services active, the worker's three lanes started, live lane idle |
| `curl localhost:8000/` | 307 to `127.0.0.1:8000` (R-036 is live) |
| `make dev-account`, then Chromium with its session on `127.0.0.1:8000` | Switcher with 8 teams. Riding Hurts's Front Office. Draft, Scout, Market, Lineup, Live, Archive, Watchlist and Preferences, with League access read-only. The CHI at SEA game page. A test change returned `403 OBSERVER_READ_ONLY` |
| Sprite renders, in batches | 9 full-field GIFs. Public pass, field goal and punt previews rebuilt |

## Decisions, issues and limitations

- **R-039.** On Live, the dev account counts every rostered player as "yours". The devices note says 30/90 days while its sessions last 12 hours. Both ship with the next approved upgrade.
- **Dev account session.** One is open until 05:51 on 2026-11-04. Start a new one with `make dev-account`; end it early with `make dev-account-end`.
- **Punts spiral** (ENG-030). Making them tumble is a one-word change.
- **R-029.** The database container won't restart by itself after a PC restart. Check `docker ps`.
- **No live data source** for player movement, speed or catch-to-carry, which the owner would like (OWN-032).

## Resume here

1. The owner reviews the full-field GIFs with the new ball, in `data/sprites/review/real-plays-wide/`.
2. R-039, with the next approved upgrade.
3. Slice 1 of the [plan](../../superpowers/plans/2026-11-03-live-play-automation.md): `libs/arbit-data/src/arbit_data/live/play_facts.py`, tested on real stored plays.
4. See [status](../status.md) and the [roadmap](../roadmap.md).
