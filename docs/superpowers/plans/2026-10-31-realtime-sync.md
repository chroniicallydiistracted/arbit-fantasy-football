# Real-time sync platform implementation plan

**Goal:** Every source that changes stays current without an operator, open clients update without a reload, and member sessions behave like an app's (OWN-017).

**Requirements:** DATA-006, DATA-008, ENG-005, FO-001, WA-001 (prerequisite), LV-001, LV-005 (partial). **Spec:** [data architecture](../../architecture/data-architecture.md), [system architecture](../../architecture/system-architecture.md), [API contracts](../../architecture/api-contracts.md).

## Problem

The FFA sync only runs while someone keeps a foreground command open; it stopped at 01:18 UTC on 2026-11-01 and members saw stale data within 15 minutes. NFL games and plays are manual inspection only. nflverse imports are manual. The outbox has no consumer, so clients poll on a timer. NFL team names, byes and kickoffs are not stored at all. Signing in on a second device revokes the first device's session.

## Source policy

Cadence adapts to the actual NFL schedule. **Active** means a game is in progress, delayed or at halftime. **Pregame** means a kickoff within 30 minutes. **Idle** is otherwise. These are Arbit's targets, not provider guarantees.

| Source | Active | Pregame | Idle | Stale after |
| --- | --- | --- | --- | --- |
| FFA league (rosters, locks, matchups, availability) | 60 s | 120 s | 5 min | 3× cadence, minimum 3 min |
| NFL scoreboard | 15 s | 60 s | 15 min | 3× cadence, minimum 60 s |
| NFL plays per active game | 15–30 s, scaled to budget | off | off | 90 s while active |
| NFL game summary per active game | 60 s | off | off | 3 min while active |
| NFL teams, byes and schedule | 6 h | 6 h | 6 h | 24 h |
| nflverse catalog and changed files | daily | daily | daily | 36 h |

Request budgets are per host: Fantasy `lm-api-reads` stays at one request per 2 s; NFL `site.api`/`sports.core` get one per second. A full slate of 14 active games is 4 scoreboard, 28 play and 14 summary requests a minute, about 46 of the 60 allowed. Play cadence widens automatically if more games are active. 429s back off through the existing gate. Sources still to add as their consumers ship: transactions and waivers (M4), player news (M3), ESPN positional ratings (M4).

## Architecture

- **Worker daemon (`arbit-worker run`).** Independent lanes (league, live, statistics) so a slow nflverse import cannot delay a score. Each lane records attempts, successes and safe errors. Survives source failures, stops cleanly on SIGTERM, runs under a systemd user unit with restart on failure.
- **Migration `0007_realtime`, additive.** `source_health`; `nfl_team`, `nfl_schedule_game`; `nfl_game` (current state); `nfl_play_revision` (append-only with current marker, unique per revision hash). `member_session.device_label`.
- **Live storage.** A poll with an unchanged body writes nothing but freshness. A changed body writes only changed plays as new revisions. Full page snapshots per poll would cost several GB per NFL Sunday, so raw live bytes are not retained; normalized revisions carry the evidence. Manual `live-inspect` still archives raw observations when originals are wanted.
- **Events.** The worker writes `outbox_event` in the same transaction as the data. One hub in the API polls the outbox once a second while anyone is connected (simpler than `LISTEN`, and within the 5-second delivery target) and fans out to session-bound SSE streams at `/api/v1/events` with `Last-Event-ID` replay, `snapshot.required` when a cursor has expired, a 20 s heartbeat, and session re-validation that closes the stream on revocation. The outbox is trimmed after 24 h.
- **Client.** One `EventSource` per signed-in tab invalidates the affected TanStack queries and clears on sign-out. Disconnection shows in the status strip and falls back to 30 s polling.
- **Sessions.** Sign-in replaces only the session the browser presents, not the account's other devices. Each session has a device label; members can view and end them. Idle 30 days, absolute 90 days, at most 10 devices. Privilege changes still revoke every session. No long-lived tokens in storage or URLs.
- **Read models.** `/api/v1/sources`, `/api/v1/live/games`, `/api/v1/me/sessions`. Roster rows gain NFL team, bye and this week's opponent and kickoff from the stored directory.

## Tasks

1. Migration, schema and stores with real PostgreSQL RED→GREEN tests: idempotent poll, single revision on change, correction, cancellation, unchanged body writes no revision, reordered pages.
2. Pure cadence policy with table-driven tests, including budget scaling and stale limits.
3. Worker lanes, per-host gate, SIGTERM handling, failure isolation. Health recorded per source.
4. Events: outbox writes, hub, SSE stream, replay, expiry, revocation.
5. Sessions: migration, multi-device sign-in, device list and revocation. Negative tests retained for rotation, fixation and revocation.
6. Member API, generated contracts, client event hook and status strip, Live scoreboard, roster NFL context.
7. systemd units and Make targets. Live proof against real ESPN during actual games; receipts recorded in research.

## Validation and limits

`make runtime-check`, `make web-check`, the browser suite, plus a real active-game capture for R-021 latency and correction evidence. SSE delivery target is p95 ≤5 s after commit, measured rather than assumed; it is not field-to-screen latency. Provider freshness remains limited by ESPN's publication. No fantasy-point attribution from plays is added here; that stays M6.

**Rollback:** additive migration; stopping the unit returns to manual sync. Existing `sync --watch` keeps working.
