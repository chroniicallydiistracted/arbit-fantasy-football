# Task: The NFL API as the primary live source, plays at real time, and the live worker

Status: built and on the running app, 2026-11-05 07:47 Arizona time (ENG-041 to ENG-043). The live proof is JAX at BAL tonight, 18:15 Arizona time (OWN-042). Owner direction OWN-041; source findings in [NFL API routes](../../research/nfl-api-routes-2026-11-05.md) (SRC-24).

- **Requirement IDs.**
  - LV-001: the live scoreboard and plays.
  - LV-003: play graphics.
  - LV-005: late, revised and cancelled plays.
  - DATA-006 and DATA-008: supervised sources with a cadence and a stale limit.
  - ENG-005: workers.
- **Owner direction (OWN-041).**
  - **Source:** the NFL API (`api.nfl.com`) becomes the primary real-time source, using every response field. ESPN's live game data becomes the emergency fallback. ESPN Fantasy stays the league authority for rosters, lineups and fantasy scoring.
  - **Survey:** read everything the NFL API can return first.
  - **Pacing:** plays run at their real snap-to-whistle time. Movement and timing change first; animations change only after that. The quarterback holds the ball longer and a runner covers less ground, but running and throwing look the same, so nothing looks like slow motion.
  - **The live worker comes last.** It discovers games, polls active ones, detects changes including corrections, and publishes app events right after each commit.
- **Baseline.**
  - **The ESPN feed:** the worker stores ESPN plays as append-only revisions and pushes changes over SSE. The [real-time plan](2026-10-31-realtime-sync.md) sets its cadences.
  - **Play facts and boards:** the interpreter (`play_facts`), the choreographer and the board read ESPN's `LivePlay`.
  - **NFL API evidence:** the owner's route tests (week 1, 16 games) and CHI at SEA (week 8) are in the ignored `data/`:
    - The play records carry the snap clock, the snap and whistle times, GSIS player IDs and jersey numbers.
    - 157 of 159 CHI at SEA football plays join to ESPN's.
    - ESPN's clock on a scoring play is the clock after it.
    - Our runs and passes animate in about 0.53 and 0.63 of real time.

## Target: live for Jacksonville at Baltimore (OWN-042)

The owner's intention: everything done in full, including the browser renderer for the real-time live animation, by the next kickoff.
- **The game:** Jacksonville at Baltimore, Thursday Night Football, 2026-11-05.
- **Kickoff:** 18:15 Arizona time (01:15 UTC on 2026-11-06).
- **NFL game ID:** `ab380826-4feb-11f1-abca-2c54536568a9`.

The order puts the path to a live animation first, and each step works on its own:

| # | Step | What it delivers | Owner's approval |
| --- | --- | --- | --- |
| 1 | Morning decisions | Approve migration `0008` and an upgrade window. Choose the art for JAX at BAL: Gridiron's week-9 listing if posted, else the labeled plain kits (automation plan item 4, OWN-028) | Yes |
| 2 | B: NFL adapter and storage | NFL responses stored with every field, migration `0008`, and joins to ESPN; tested on the stored week-8 responses | Applied at step 9 |
| 3 | C: facts, script and board from the NFL record | The snap and whistle clocks, numbers from the play, ESPN as the fallback | |
| 4 | D: pacing to real time | Plays fitted to their snap-to-whistle time by timing first; CHI at SEA renders for the owner | Look |
| 5 | F: the live NFL lane | Discover, poll the week's game summaries and fetch changed games, detect changes and corrections, publish after commit | Applied at step 9 |
| 6 | Browser renderer and live field (automation plan slice 7) | `apps/web/src/live/`: the WebGL2 scene, players and ball from scripts, the field, the board with logos, the play queue, replay, keyboard and reduced motion, SSE updates. Behind a session, the API serves the scripts, boards, frames, logos and art | |
| 7 | E: ESPN as the emergency fallback | The app switches to ESPN plays, labeled, when the NFL lane is stale | |
| 8 | Verification on an isolated port | Tests, the browser suite, the browser against the Python renderer frame by frame, and the rule checks | |
| 9 | Upgrade the running app | Migration `0008` applied, and the API, worker and web rebuilt. No later than 17:15 Arizona time (00:15 UTC), an hour before kickoff, so nothing changes during the game | Yes |
| 10 | Live proof during JAX at BAL | Each play's delay from the whistle to the animation, corrections seen, no failed renders, and how a live response changes | Watches |

**Open for the morning:**
- **Polling interval:** set from the request budget. The first live measurements come at kickoff.
- **The live-only fields** (`latestPlay`, `playClock`, `playReviewStatus`): unseen until the game.
- **Skin tone (R-037):** stays as the review renderer does it unless the owner decides otherwise.

**The risk.** One day for all of it is tight. Each step is usable when it lands, and the order keeps the live animation's path first.

## Slices

Each slice ends with evidence. Slices that change the running app, or add a migration, need the owner's approval at the time, outside game windows.

**A. Survey everything the NFL API returns (finalizes the findings).**
- **Which routes:** every route the sportsdataverse endpoint catalog, the owner's tests and NFL.com's own traffic name. Each is classified for live use: game state, plays, players, teams, statistics, schedule, standings, injuries, rosters and media metadata.
- **How:** every route that can bear on a live game is requested for week 8 (the 14 captured games) with the owner's script, in its own ignored folder, at its pace. No media is downloaded, nothing is played back and no entitlement is tested.
- **Result:** a field catalog for each route, recording each field's meaning, coverage and what Arbit would use it for.
- **Also measured:**
  - how long the anonymous token lasts, and how it renews
  - rate limits
  - how much a game response changes between reads
  - on the next live slate, how soon a play appears against ESPN's 36-second median
- **Evidence:** the survey document, and the field catalog in `docs/research/`.

**B. NFL adapter and storage.**
- **Code:** a library module that reads NFL API game responses into stored, append-only revisions keyed by NFL game UUID and play ID. Every field is kept, including the snap and whistle times, the stats with GSIS IDs and jersey numbers, the text with numbers, deleted plays and drive data.
- **Joins:** games join to ESPN events through Elias ID → nflverse `old_game_id` → ESPN ID. Plays join on quarter, snap clock and text, and scoring plays on text, since ESPN times their clock after the play.
- **Migration:** additive tables for NFL games, play revisions and raw responses.
- **Evidence:** CHI at SEA and the week's other games stored, with every field, and every play joined or its reason recorded.

**C. Facts, script and board from the NFL record.**
- **Facts:** the interpreter takes the NFL play record as its first source, and ESPN's as the fallback.
- **The board:**
  - the snap clock, and the clock at the whistle from snap minus duration (kickoffs from the touch)
  - foul numbers from the game's own stats and text
  - the scoring-play clock corrected
- **Evidence:**
  - the board check, comparing scores and the clock at the next snap with the NFL's game summary
  - the facts check on every stored week-8 play

**D. Pacing to real time (OWN-041).**
- **Timing:** the choreographer takes each play's real snap-to-whistle duration and fits the play to it, by timing first:
  - the quarterback's drop, hold and throw
  - the handoff and the mesh
  - routes and coverage
  - pursuit
  - the runner's pace through traffic
  - the pile up to the whistle
- **The look stays the same:** speeds stay within the natural-motion rules (OWN-033), and run, throw and other cycles keep their stride. A longer play spends its time on things that happen in a real play, not on slowed motion.
- **Animations** change only after the owner reviews this.
- **Evidence:** CHI at SEA rendered with real durations; the rule check gains "the whistle at the real duration" and "no cycle slower than its natural pace"; the owner reviews it against the video.

**E. The NFL API primary, ESPN the emergency fallback.**
- **Which source a page uses:** the NFL record. When the NFL lane is stale or failing, ESPN's plays are used, with a visible "Fallback source" label.
- **The ESPN lane** keeps running at a reduced cadence, so the fallback is current.
- **Records:** `AGENTS.md`'s source rules and the architecture documents say so.
- **Evidence:** a forced NFL outage in the isolated environment shows the fallback, its label, and the return.

**F. The live worker (last).** It follows the owner's four steps:
1. **Discover games.** Read the schedule, resolve each game's UUID, and start watching before kickoff.
2. **Poll active games.** Fetch the full game response on a configurable interval, within the request budget.
3. **Detect changes.** Compare snapshots and individual plays, including corrections to earlier plays and deleted plays.
4. **Publish updates.** Send app events immediately after the changes are committed, through the existing outbox and SSE.

It is supervised like every lane, with a declared cadence and a stale limit.
- **Evidence:** a real slate, with each play's delay from the NFL's whistle time to the app event, corrections observed, and no missed play.

## Inputs and decisions

- **Authorization:** the anonymous device grant with NFL.com's public web-client defaults, as the owner's script uses. The token is held server-side only, renewed on expiry, and never logged.
- **To settle in slice A:**
  - **Polling interval:** the owner wants data the moment it's available. The API offers nothing to subscribe to, so the worker polls, and the interval is set from what slice A measures.
  - **ESPN's fallback cadence.**
- **Unchanged:**
  - **ESPN Fantasy** stays the league authority.
  - **nflverse** stays the statistical foundation for models; the NFL API is the live source it is published from.
- **Rollback:** the ESPN lane keeps running, so turning the NFL lane off falls back without losing data.

## Evidence and outcome

**Slice A, so far (2026-11-05).** [The data survey](../../research/nfl-api-data-survey-2026-11-05.md) covers every catalogued route, the owner's tests and NFL.com's traffic. 21 requests for week 8 all returned 200, and no token was saved.

- **Routes for the live feed:**
  - **Discovery:** the week by date, then the week's schedule with each game's UUID.
  - **The cheap scoreboard to poll:** game summaries, 11 kB for the whole week.
  - **The play record:** v2 game details. v1 game details add game state.
  - **Statistics:** player and team box scores.
- **The play record:** snap and whistle times, the clock at the whistle (snap minus duration, matching ESPN's 7 scoring plays to the second), and jersey numbers from the play's own stats and text.
- **The join to ESPN:** every football play's ESPN ID is the event ID followed by the NFL play ID (152 of 152).
- **Sign-in:** a token lasts about 60 minutes and comes with a refresh token.
- **Linking to video:** 18 of 25 clips name their plays, so a play can link out to its official highlight.

**Still open in slice A:** the live slate, for the delay, how a live response changes and the live-only fields; a rate-limit budget; and injuries paging.

**The day's build (2026-11-05, before kickoff).** Owner answers: OWN-043 (upgrade, uniforms, skin tone) and OWN-044 (field).

| Slice | What it is | Evidence |
| --- | --- | --- |
| B: adapter and storage (ENG-041) | `nfl_api.py` and migration `0008` (`nfl_api_game`). Plays are stored in `nfl_play_revision` under ESPN's IDs | Week 8, interpreted from both sources: shape differs on 5 of 2,199, start on 4, score on 0. `test_nfl_api.py`: 10 tests against ESPN's record of CHI at SEA |
| C: facts, script, board | The record's snap and whistle clocks and foul numbers. Wiped-out plays' players come from the numbered text | The scoring-play clock runs from the snap (5:30) to the whistle (5:25). Foul numbers come from the game's own record (Nelson's 53) |
| D: pacing (ENG-042) | `pacing.py` | 1,800 of 2,021 timed week-8 plays end at the real whistle. No run is slower than 5.5 yards a second. `test_pacing.py` |
| F: the live lane (ENG-041) | `nfl_feed.py`, the worker lane `nfl` | `test_nfl_lane.py`: 6 tests on PostgreSQL. On the running app it discovered and linked all 15 week-9 games |
| Browser (ENG-043) | `apps/web/src/live/`, `live_art.py`, and the animation and art routes | Harness screenshots match the reviewed clips. An isolated app on port 8010 showed the field on the game page with no errors. `make web-check` passed |
| E: fallback | The ESPN feed skips games the NFL lane has fresh, and keeps a game until the NFL record has plays. The field labels ESPN plays "Fallback source: ESPN" | `test_nfl_lane.py` |

**Tonight's art:** `data/live-art/401873037/`.
- **Uniforms:** Gridiron's week-9 listing, JAX `A2` and BAL `W`.
- **Field:** Baltimore's usual 2026 field, labeled (OWN-044).

**The upgrade, 07:47 Arizona time:**
1. A backup: `data/backups/2026-11-05/before-nfl-api-upgrade-074654.dump`.
2. `alembic upgrade head` to `0008_nfl_api`.
3. The web build.
4. API and worker restarts.

The worker was restarted three more times by 07:51 for the kickoff rule, the empty-record safeguard and wiped-out plays. The API reports ready. The NFL lane is healthy (`nfl.api.plays`).

**Checks:**

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 1,170 passed, before the last three tests; 1,176 with them |
| Ruff, format, mypy, `pnpm check:contracts`, `make web-check`, `make check` | Passed |

**Not yet seen (the live proof tonight):**
- the delay from the whistle to the play on the field
- what the summaries show during a live game
- the live-only fields
- corrections in flight

**Later:**
- Building art for each game automatically, ahead of its kickoff (slice 6).
- The rate-limit budget for a full Sunday slate.
- Injuries paging.
