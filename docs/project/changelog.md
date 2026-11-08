# Development Changelog

## 2026-11-08 — Fresh NFL polling measured live

- Measured the fresh-key, two-second NFL polling on the first live Sunday (R-042, OWN-045). Fresh reads saw new plays a median 17.9 s after the whistle, against 39.4 s for ordinary cached reads of the same games, and were first on all 263 paired plays. Cadence held at 2.0 s with no 429s. Added `scripts/live/check_fresh_polling.py` to rerun it. The browser leg, from announcement to the play's text in an open page, took a median 1.0 s (`scripts/live/time_browser_leg.cjs`, `browser_leg_report.py`). [Measurement](../research/nfl-fresh-polling-2026-11-08.md).
- The owner's Google sign-in through Access worked from an iPad at the public address.

## 2026-11-08 — The app's public address

- The app on this PC is now served at `https://ffa.westfam.media` through a dedicated Cloudflare Tunnel, `arbit`, behind the owner's existing Cloudflare Access (OWN-058, ENG-049). `infra/tunnel/` creates the tunnel, its `arbit-tunnel` user service and the DNS route. The tunnel answers the loopback-only operator reads with 404. The app's single origin switched to the new address with a 6-second API-only restart during the late games; the worker never stopped. Every device signs in again at the new address. A same-day Wi-Fi-only plan was replaced before anything was installed.

## 2026-11-08 — M&T Bank geometry refinement

- Modeled the farther right-wall cutout between sections 109 and 111 as the player tunnel. The separate lower cutout between sections 115 and 117 remains open. Both clearances passed the geometry check.

- Continued the owner-confirmed M&T-first approach: corrected the private 3D study's decks, tier heights, suite facades, entrances and corner lights. Added reproducible reference/before-after comparisons and current/taller Live-camera previews. Fifteen focused tests pass; 509,969 field pixels are preserved in each lighting mode. This is a review study, not a published stadium replacement; likeness and framing remain open. [Handoff](handoffs/2026-11-08-mt-bank-refinement.md).

## 2026-11-08 — Each home stadium's own design

- The live field's surround can now take each home stadium's own design, recreated in Arbit's pixel style from the owner's midfield references (OWN-054): seat colors by level, concrete, suites, ribbons and roofs. Shared buildings follow the home team, and neutral sites keep the generic stadium. The design is ready for the owner's review and not yet published. [Handoff](handoffs/2026-11-08-stadium-venues.md).

## 2026-11-07 — Live animation calibration and rebuild design

- Verified the expanded private NGS archive, checked overlap against archived NFL play-by-play, and split the reference by game. Recorded the proposed evidence, motion and rendering design and the owner's clarification on multi-role players. [Calibration handoff](handoffs/2026-11-07-live-animation-calibration.md).

## 2026-11-07 — Independent Live animation audit

- Audited the current NFL-to-browser path and repeated the archived timing and isolated playback checks. Recorded action sequencing, movement, ball attachment and review synchronization issues for the M6 rebuild. Detailed comparison evidence stays private under OWN-053. [Audit handoff](handoffs/2026-11-07-live-animation-rebuild-audit.md).

## 2026-11-07 — Our plays against real tracking

- Six of Jacksonville–Baltimore's highlights were rendered twice with the same renderer: as our choreographer builds them, and from the owner's private NGS tracking (OWN-053).
- The comparison found five gaps: throw and handoff timing, speeds, paths, alignment depth, and players we hold still.
- It also found three defects:
  - a receiver drawn twice when the text and the roster spell his first name differently
  - a kickoff return lost when the play's text carries a challenge
  - a short pass's flight about 50% too long

  The findings stay private with the captures. [Handoff](handoffs/2026-11-07-play-timing.md#ngs-comparison).

## 2026-11-07 — Play timing, slice 2: runs built to their real time

- Runs and scrambles now fill their real snap-to-whistle time with football, at natural speeds: a slower mesh, a wider path to the hole, a churning pile through contact, a longer or shorter look for a scrambler, then a natural dead ball before the whistle. Across 31 games, runs with more than 1.5 s of standing time went from 36% to 2%. Not released. [Handoff](handoffs/2026-11-07-play-timing.md).

## 2026-11-07 — Play timing, slice 1

- The Live board's game clock now runs one second per second from the snap and stops on the play's recorded end clock. Plays that run long no longer slow the clock.
- The choreographer receives each play's real snap-to-whistle time, and a phase fitter is ready for the templates. Plays are built to their real time from slice 2, starting with runs (OWN-051, OWN-052).
- A 31-game baseline found 27% of 4,285 timed plays leave more than 1.5 s of standing time, and 492 keep moving after the real whistle. [Research](../research/live-play-timing-2026-11-07.md) and [handoff](handoffs/2026-11-07-play-timing.md).

## 2026-11-07 — Stadium around the live field

- The space around the live field now shows a stadium in the home team's colors: sideline turf, benches, a padded wall, a crowded lower bowl, a lit club level and an upper deck. Neutral sites get an even crowd and gray walls. The field art is unchanged. Published to all 15 Week 9 games on the owner's approval. [Handoff](handoffs/2026-11-07-live-stadium.md).

## 2026-11-07 — Week 9 artwork refresh

- The wake check verified the installed repair and active NFL polling. Denver–Carolina now uses Denver's newly listed B3 kit. [Verification](handoffs/2026-11-06-live-animation-repairs.md#november-7-wake-check).

## 2026-11-06 — Live animation audit repairs

- A verified NFL final retains ownership of play revisions. New reads reconcile fallback-only rows and guard against late provider writes.
- Live replay follows new plays in reduced motion, keeps selected play identity across corrections and holds the ball in the ending frame. Stoppages update the Jumbotron in place. Play-log rows open their replay or text and can load earlier rows.
- Play facts recover known spots, aliases and reviewed try timing. Direct snaps, laterals, complex fumbles and blocked punts show verified portions with a readable note. Animation reads support gzip and game-specific events invalidate only affected game queries. Private artwork builds publish complete, versioned bundles. [Handoff](handoffs/2026-11-06-live-animation-repairs.md).
- Activated migration 0009 and the verified build locally. The NFL worker restored Thursday's replay, and 15 private Week 9 art bundles now use exact fields or the approved season-use fallback. Madrid uses a labeled plain field while its listed image is unavailable.

## 2026-11-05 — Animation pipeline audit

- Verified production script generation across 31 NFL games and sampled 2,912 browser-rendered frames. Reproduced final-source ownership, reduced-motion following, replay identity, terminal ball and try metadata gaps. [Audit](../research/live-animation-pipeline-audit-2026-11-05.md) and [handoff](handoffs/2026-11-05-live-animation-pipeline-audit.md).

## 2026-11-05 — Game cards, field and Jumbotron

- On the game page the existing cards sit in one horizontally scrolling row, and the wider field's Jumbotron is the main scoreboard. Quarter scoring and game details expand below the field. The full scoreboard stays visible when the field cannot show a board.
- Audited 5,881 NFL records through normalization, animation and browser eligibility. [Coverage](../research/live-play-coverage-2026-11-05.md) and [handoff](handoffs/2026-11-05-live-field-layout.md).

## 2026-11-05 — Fresh NFL polls every two seconds

- The primary NFL worker requests full details for each active game in each two-second round, even if its summary is identical. Primary summary and detail reads each get a new `_cache_probe` value, and concurrent reads cover overlapping games.
- Loaded locally after Thursday's game. An isolated pregame run returned six cold responses. Sunday will measure whistle-to-arrival time and slate-wide cadence. [Polling handoff](handoffs/2026-11-05-nfl-fresh-polling.md).

## 2026-11-05 — Live platform integrated into main

- Published the platform branch and integrated the milestone and sprite branch histories into `main`. The merge kept the newer reviewed sprite frames and renderer.
- Loaded the merged web build, API and worker on the local app. Verified the served bundle and service worker against the staged build. The live database was already at the current schema, and the older fixture database was upgraded. [Release handoff](handoffs/2026-11-05-main-release.md).

## 2026-11-05 — Week 9 live-feed observation

- The NFL worker pursues a changed summary through a cached detail response. Final details are retried after failures and polled until their phase catches up. ESPN's comparison reads have a separate schedule from the fallback's publication timestamp.
- Private request receipts include cache headers, gzip sizes, play fingerprints, whistle times and app commit times. A separate probe compares alternate NFL routes and observes the event-stream response type. ESPN play captures supply a second timestamp for matched IDs.
- An isolated browser records public Game Center routes and transport activity. The postgame report compares first sightings and summary offsets around observed revisions. [Handoff](handoffs/2026-11-05-live-feed-observation.md).

## 2026-11-05 — Live by kickoff: the NFL API lane, real-time pacing and the browser's live field (ENG-041 to ENG-043)

- **The NFL API is the primary live source.** A new worker lane follows the owner's four steps: it discovers the week's games, polls the week's 11 kB summaries every 2 seconds during games, fetches a game's full record when it changes (and every 20 seconds anyway, for corrections), and publishes the changes. Plays are stored under ESPN's own IDs, so everything built on them works unchanged.
- **ESPN is the emergency fallback.** It steps aside while the NFL lane has a game fresh, takes over if the NFL lane goes stale for 90 seconds, and keeps any game whose NFL record has no plays yet.
- **Facts from the NFL record:**
  - **The clock:** the board runs it from the snap to the whistle.
  - **Foul numbers:** from the game's own record.
  - **Scoring plays:** they show the snap's clock, not ESPN's after-play clock.
  - **Wiped-out plays:** they name their players again.
- **Plays run at real time.** The action slows by one factor, so the quarterback throws later and runners cover less ground. It stops before anything looks like slow motion; the rest of the real time is the end of the play.
- **The browser's live field.** The game page draws each play in the full-field view with the stadium board, from the same scripts and art as the reviewed clips. New plays play in turn as they arrive. You can step back, replay, pause, use the keyboard, or get each play's end with reduced motion. Before the first play it shows the empty field.
- **Tonight's art:** JAX at BAL has the uniforms Gridiron lists and Baltimore's usual field, labeled (OWN-044).
- **On the running app** since 07:47 Arizona time, with migration `0008`. The NFL lane linked all 15 week-9 games.

## 2026-11-05 — The NFL API as the primary live source: direction and survey (OWN-040 to OWN-042)

- **The owner's route tests** checked out, and CHI at SEA was fetched with the owner's script.
- **Matching ESPN:** NFL plays join ESPN's exactly, since ESPN's play ID is the event ID followed by NFL's play ID.
- **Timing:** the NFL's snap and whistle times are real, and the clock at the whistle matches ESPN's scoring plays to the second.
- **Jersey numbers:** they come from the game's own record.
- **Pace:** our animations run at about 0.53 to 0.63 of real time.
- **Direction (OWN-041):** the NFL API becomes the primary live source using every field, and ESPN's live data the emergency fallback. ESPN Fantasy stays the league authority. Plays are paced to real time by changing timing first. The live worker comes last.
- **Slice A survey:** discovery, the 11 kB game summaries to poll, two complementary game detail versions, statistics, rosters, video metadata linked to plays, and the 60-minute token.
- **Target (OWN-042):** everything live, including the browser renderer, for JAX at BAL at 18:15 Arizona time on 2026-11-05.

## 2026-11-05 — The board after the owner's review (OWN-039)

- **Results scroll in** from the side of the team they're for, instead of wiping in.
- **Colors:** scores are green, turnovers and missed kicks red, and penalties yellow, using the design system's `gain`, `challenge` and `flag` signals. The library sets each result's tone, so every renderer agrees.
- **Penalties on the board:** each flag shows the foul's name, the team and the player's jersey number, plus DECLINED or OFFSETTING.
  - **Numbers:** from the flagged team's nflverse roster for the game's week, by ESPN ID or else by the text's name. 214 of the 226 flags in the captures get a number. The rest are 11 team fouls and one player missing from his team's roster that week.
- **Team logos:** every team's logo is drawn in LED dots at its outer edge of the board. All 32 logos were fetched into the ignored `data/logos/`; they're the teams' trademarks, kept private like the Gridiron art.
- **Clock:** the board runs the clock from the snap to the end of the play when a source gives the end time, ready for the owner's NFL feed. Without one it holds.
- **Checks:** 1,155 tests pass. The board check and the renderer audit show no problems.
- **Accepted:** the owner: "The scoreboard looks phenomenal!" (OWN-040). Slice 5 is committed.

## 2026-11-05 — The stadium board (automation slice 5)

- **The board in the scene:** a stadium board above the far sideline in the full-field view (OWN-030), drawn as LED pixels with our own glyphs, never a licensed font or a logo.
- **What it shows**, as the game stood at the play on screen:
  - both teams' codes in their name tag colors, their scores and timeouts left
  - the quarter and the clock at the snap
  - possession
  - down and distance, kickoff or the try
  - the ball's spot
- **After the play:** the board turns to the game once the play is over. After scoring plays, turnovers and missed kicks it shows the result in large type for two seconds, such as "TOUCHDOWN", "FIELD GOAL GOOD", "INTERCEPTED" or "NO GOOD". A turnover returned for a score shows both.
- **One implementation:** `arbit_data.live.board` gives the board's facts from the stored plays, with the `play-board` contract. The browser will draw the same facts in slice 7.
- **Timeouts** come from ESPN's own numbering in the play text, lost challenges included.
- **The script** gains `whistle`, the moment the play is over.
- **Checked against ESPN's scoreboard** over all 14 captured games (`scripts/live/check_boards.py`): every final score, plus score and timeouts after 691 plays, down and distance after 641 and possession after 602. The board never differs where ESPN agrees with itself.
- **The check found two problems, both fixed:**
  - A flag on a try made the score drop by the extra point.
  - A challenge naming only "Los Angeles" would have been charged to the wrong team.
- **Tests and renders:** 1,143 tests pass. The 19 comparison plays are rendered with the board in `data/sprites/review/board/`, and the whole CHI at SEA game was re-rendered.

## 2026-11-04 — Play realism from the owner's video comparison (OWN-037, OWN-038)

- **Passes:** the receiver and the ball arrive together, timed by the throw. Short passes can be bullets, deep passes keep their pace, and receivers never wait or slow.
- **Coverage:**
  - Defenders named on a pass cover the receiver from the snap with a zone drop and a natural backpedal in new frames, keeping a cushion.
  - They break only as late as gets them there.
  - Tacklers meet the carrier from their own side and never back off to come again.
- **Waiting and idle:** players use new stance and idle frames. The quarterback's ball-holding frames are his alone.
- **Interceptions:** the intended receiver is drawn and the interceptor undercuts him. A pass tipped at the line, as on CHI at SEA Q4 6:01, pops up to the interceptor.
- **Sacks:** the quarterback works the pocket and escapes right into the sack.
- **Snaps:** the team's center snaps every play and stays over the ball, and the long snapper snaps kicks.
- **Runs:** the quarterback takes the snap and hands off at once; receiver sweeps come in jet motion.
- **Coverage fouls:**
  - **Pass interference:** contact while the ball is in the air, more than a yard past the line, on a catchable ball, in the owner's three actions.
  - **Holding, illegal contact and offensive pass interference** are drawn as they happen, and only on the player called.
  - **Officials:** each flag is thrown by a drawn official.
- **Sprites:** 11 new player frames and an official with 8 frames, from PixelLab.
- **Name tags:** style C, in team colors without the box.
- **Checks:** the rule check gains the new rules, `test_realism.py` covers each item, and the full suite has 1,085 tests passing. 19 comparison clips are in `data/sprites/review/play-types-2/`.

## 2026-11-04 — Players line up by position and play their role (OWN-036)

- **Positions** (`alignment.py`, ENG-037). Every drawn player starts at his position's general spot, from his team's 2026 depth chart by ESPN ID:
  - the offensive line across the ball
  - the tight end inline on the strong side
  - backs and the quarterback by shotgun or under center
  - the defensive front on the line, with a 3-4's outside linebackers on the edge
  - linebackers off the ball, corners wide, safeties deep
- **Context from the play.** The play's side and description move players:
  - a defensive back who makes the play lines up on its side, a corner over his receiver
  - receivers and ball carriers line up by position, with wide receivers at least in the slot
  - two-way players line up for their side of the ball
- **First moves after the snap.**
  - **Pass plays:** linemen rush the passer, and linebackers and defensive backs backpedal into coverage.
  - **Run plays:** linemen take on a block.
  - **Offense:** receivers release, and blockers set or drive.
- **Contract.** Scripts carry each player's `position`. Kick specialists show their job's slot (P, PK, H, LS, PR, KR).
- **Audit.**
  - `check_play_scripts.py` checks starting boxes and overlaps, and has a `--no-positions` mode.
  - The new `scripts/sprites/audit_render.py` checks scripts against the renderer's frames, anchors, flights, tags and captions.
  - Both report nothing wrong over all 2,254 captured scripts.
- **Fixed on the way.**
  - Air yards on penalty plays now come from the play's own gain (amends ENG-032).
  - Overlapping starts and a slow-motion encroachment are gone.
  - Name tags now fall back to the depth charts when the roster lacks a player's ESPN ID.
- **Renders.** `render_script.py --types` renders one clip of each play type, with position tags, to `data/sprites/review/play-types/` for the owner to compare with the game's video.

## 2026-11-04 — Kicks, tries, fumbles and penalties (automation slice 3)

- **Kicks** (`kicking.py`, ENG-035).
  - **Field goals:** a snap to a holder 8 yards back, as measured, and a kicker who approaches at his own pace. Good kicks tumble between the uprights into the net. Wide left and wide right pass outside their uprights, kicks off an upright or the crossbar come back, short kicks fall in front, and blocked kicks come off the blocker.
  - **Punts:** a 15-yard snap and a spiral.
  - **Kickoffs:** off a tee, with the coverage held at the receiving 40 until the catch.
  - **Results:** returns end on ESPN's spot, tackled by the kicking team. Also drawn: fair catches, touchbacks, kicks out of bounds, downed kicks, muffs, kicks short of the landing zone and onside kicks.
- **Tries.** The extra point or two-point try after a touchdown is its own script, named from the try's own sentence.
- **Spikes.** A spike is drawn too.
- **Fumbles** (`incidents.py`). The play is drawn up to the hit. The ball bounces to ESPN's recovery spot, and the recoverer falls on it, or scoops it and returns it when the text says so. The player who forced it stays up and goes after it.
- **Penalties.**
  - **Before the snap:** the penalized player and a flag.
  - **Plays wiped out:** the play, a flag and "No Play".
  - **Plays that count:** a flag for an accepted or declined penalty, and the caption names it.
  - **Flags:** a new `props` list in the script, each flag tossed by the nearest official.
- **Facts.** Play facts gain `before`, the play the text describes before a fumble or a flag that wiped it out.
- **Names.** Players ESPN gives no ID, such as a long snapper, appear under the text's name. Kickers, punters, returners and blockers can now be named from the text.
- **Contract.** The script contract gains `props`, and an actor's `espn_id` may be empty. There is a second example, a punt with a flag (`tests/fixtures/live/play-script.punt.example.json`).
- **Rule check.** `scripts/live/check_play_scripts.py` checks every captured play against the animation rules.
- **Renderer.** `render_script.py --slice3` renders a game's kicks, tries, fumbles and penalties, with flags drawn.
- **Owner review fixes (OWN-035, ENG-036).**
  - **Where players start:** the offense on or behind the line of scrimmage, and the defense on or beyond it, no deeper than a safety.
  - **No early movement:** nobody runs before the snap; the committed slice 2 code had started 441 tacklers early.
  - **Fumble:** CHI's J.Jackson, who tackles Lawrence on the return, now starts on Chicago's side of the line.
  - **Punt coverage** releases at the snap.
  - **Kickoff coverage** stays at the receiving 40, as the 2026 rule requires, now measured from any tee.
  - **Re-rendered:** CHI at SEA in full.

## 2026-11-03 — Play scripts (automation slice 2)

- `choreography.choreograph` turns a play's facts into a `PlayScript`: each named player's timed poses and moves, where the ball is at every moment, the lines and the caption. It covers passes (complete, incomplete, thrown away, screens), interceptions, sacks, runs by gap, scrambles, sneaks and kneels. The contract is published as `packages/contracts/schemas/play-script.schema.json` (ENG-034).
- Every play ends on ESPN's spot. A catch lands at the spot yards after catch puts it, and tacklers meet the carrier there. Speeds are bounded by pose, so nobody slides, and the same play gives the same script.
- All 1,706 captured plays with these templates get a script that keeps every rule: no speed over its pose class, no gap in a timeline or in the ball, every carrier on ESPN's spot, and no unnamed player and no one drawn twice.
- `scripts/sprites/render_script.py` draws scripts with the review renderer.
- **Reworked after the owner's first look (OWN-033).** Receivers had run in slow motion to meet the throw, and the quarterback froze before throwing.
  - Every player now keeps one natural pace, and routes set the timing: short receivers settle and come back to the ball, deep ones catch in stride.
  - The quarterback's drop fits the throw, and he works his feet in the pocket.
  - Anyone waiting sets with a side step.
- **Names** come from the roster by ESPN ID. Five labels in CHI at SEA had been wrong: an eligibility report, a trick play, and two tacklers swapped.
- **Trick plays.** A pass after a direct snap to someone else now shows its text.
- **Re-rendered.** CHI at SEA was rendered again for review.

## 2026-11-03 — Second upgrade of the day

- With the owner's approval, the running app was upgraded at 21:16. It was offline 5 seconds, a backup was written to `data/backups/2026-11-03/before-upgrade-211633.dump`, and no migration was needed.
- **Normalizer.** The worker now stores `yardLine`, yards after catch, and the penalty and review objects (ENG-033, R-040).
- **Live team context.** The dev account's Live board follows the team it picks (R-039). Checked signed in as the dev account.

## 2026-11-03 — Play facts (automation slice 1)

- `play_facts.interpret` turns a stored ESPN play into facts for animating it:
  - shape and template
  - offense and defense, with spots in the offense's frame, plus down, distance and line to gain
  - named players by role, and formation
  - pass depth, side, catch spot, air yards and QB hits
  - run direction and gap
  - kick distance, landing, result and miss
  - penalties, fumbles, the extra point or two-point try, touchdowns, turnovers and replay result
- Over all 14 captured games, 2,032 of 2,196 football plays (92.5%) have a template with nothing missing. Every other play has a stated reason: fumbles and no-play penalties wait for slice 3, plus 2 laterals.
- Checked against ESPN's own spots and text, the end spot matches the text on 1,627 of 1,627 plain plays, and so does start plus yards.
- Found that ESPN's `yardsToEndzone` often isn't flipped for the home team: 54 of 114 punts (R-040). The normalizer now keeps `yardLine`, yards after catch, the penalty object and the review object, and spots come from `yardLine` (ENG-033). This reaches the running worker with the next approved upgrade.
- 45 tests on 28 real captured plays, one per shape and text form.

## 2026-11-03 — Where richer live play detail can come from

- nflverse's raw play-by-play comes from a private `nflapi` package whose route isn't public. It works live, but nflverse releases a game only after FINAL. Working out the route means using NFL's own API, which NFL's terms prohibit collecting from (Q-012, [research](../research/live-play-detail-2026-11-03.md)).
- Checked nflreadr's 372-field play-by-play dictionary against ESPN. Only two play-specific facts are NFL-only during a game: exact air yards on incomplete passes and interceptions, and the play clock at the snap. The descriptions are the same NFL text on 94.5% of week 8 plays; nflverse's look longer because of the game clock and jersey numbers.
- ESPN's live summary already sends yards after catch on 506 of 508 receptions, within a yard of NFL's official value on 94.6%. The play interpreter will use it for the catch spot (ENG-032); the worker's normalizer drops it today, but the raw captures keep it.

## 2026-11-03 — Dev account, a ball that flies right, and NGS tracking

- **Dev account** (OWN-032, ENG-031). A read-only account on the running app, so Claude can see it signed in. `make dev-account` gives it a 12-hour session, saved where only this user can read it; the token is never printed.
  - It opens every team through the Front Office team switcher and reads the administrator pages.
  - The API refuses every change it makes except to its own preferences and signing out.
  - It is off in production, and the administrator can end its sessions or suspend it in League access.
  - A yellow band marks it on every page.
- **The ball** (ENG-030). It no longer changes width every frame.
  - Passes and snaps fly nose-first along the arc with a slight wobble.
  - Punts spiral and turn over at the top.
  - Field goals and extra points tumble end over end, and the ball stands upright for the hold, in front of the holder.
  - The review plays and the public previews were rebuilt.
- **NGS tracking** ([research](../research/ngs-highlights-2026-11-03.md)). nflverse's Next Gen Stats tables have no positions. The NGS site has real tracking for highlights only, and NFL's terms prohibit collecting it into a database. The owner chose to skip it for now (Q-011).
- **Only the players in the play** (OWN-032). A family member found plays easier to follow that way, so supporting players are on hold in the plan.
- **Upgraded the running app** at 17:50 with the owner's approval. It was offline 25 seconds, with a backup taken first and no migration. It now has the dev account and the R-036 sign-in fix. Checked signed in as the dev account in Chromium:
  - The team switcher lists all 8 teams, and Riding Hurts's Front Office shows its own roster and matchup.
  - All seven workspaces, the watchlist, Preferences with League access read-only, and the CHI at SEA game page all load.
  - A test change was refused with `OBSERVER_READ_ONLY`.
  - One flaw is in R-039: Live counts every team's players as the dev account's own.

## 2026-11-03 — Kicks through the uprights, and the full-field view as standard

- The owner made the full-field view the standard and dropped 2D (OWN-030). `real_plays.py` now renders it by default; `--close` gives the earlier following camera.
- Fix: a good kick seemed to pass in front of the near upright, because the ball was drawn over everything. Players, goalpost pieces and the ball in flight are now drawn by distance from the camera, and a kick keeps its arc across the end line into the net (ENG-029). Checked frame by frame: a good kick passes in front of the far upright and behind the near one.
- Two extra points from CHI at SEA added to the review set: C.Santos's good kick in the third quarter, and J.Myers's miss wide left in the second, which passes in front of the near upright.
- The public preview plays rebuilt: the punt has no visible change, and the field goal differs by 2 pixels where the holder now covers the ball's edge.
- The [automation plan](../superpowers/plans/2026-11-03-live-play-automation.md) gains supporting players, a jumbotron, a field that persists between plays, and the kick results. nflverse's Next Gen Stats turned out to be weekly averages per player, with no positions. FTN's per-play charting is the best formation source for finished games.
- The PC restarted during the session, and the dev database didn't come back with the services (R-029). It was started again and recovered cleanly; the worker resumed by itself.

## 2026-11-03 — Full-field view and the automation plan

- The owner accepted the real-uniform plays (OWN-029) and asked to see more of the field. `real_plays.py --wide` renders the seven CHI at SEA plays from a fixed camera that shows both end zones and goalposts (`data/sprites/review/real-plays-wide`, ignored). Players are about 35 pixels tall on a 1,920-pixel frame and are never drawn below their own pixel size. The punt's frame is taller so the ball stays in view (ENG-028).
- Name tags of players who meet now stack instead of covering each other. The public preview plays rebuilt byte-for-byte unchanged, so the close camera is untouched.
- [Plan](../superpowers/plans/2026-11-03-live-play-automation.md) for animating every play as it arrives: a server interpreter and choreographer make a small play script from each stored revision, and the browser draws it. Real art appears once Gridiron lists it, with a labeled plain fallback until then. Measured on the 14 stored games, 827 of 834 passes state depth and side, and 784 of 785 runs state a direction.

## 2026-11-03 — Real uniforms on the sprites

- The owner added their full 2026 uniform set and said not to infer uniform colors (OWN-028). The real plays now use what Gridiron's week 8 page lists for CHI at SEA: Chicago `B2`, Seattle `E` and field `SEA_2023-2026^3`. This replaces the white stand-in for Chicago and the guessed field `^1` used on 2026-11-02.
- Every frame has a map of which uniform part each pixel shows (`assets/sprites/regions`), made from the skeletons the frames were drawn from. The owner's art ties helmet to pants and jersey to socks, which real uniforms don't.
- `scripts/sprites/uniforms.py` measures each part at fixed places on Gridiron's sheet template and shades it with the owner's sheet's own ratios, which reproduce all 64 of its sets. All 202 single-version sheets measured, each checked beside its painted sprites. Three animated sheets show two versions and are refused until one is named ([research](../research/uniform-measurement-2026-11-03.md), ENG-027).
- GIFs now keep every sprite color exactly. The old encoder had turned Chicago's orange stripe yellow. The public preview plays were rebuilt with it.
- Limits are in R-037: one trim color per part, no helmet logos, thin sock stripes, placeholder skin tones.

## 2026-11-02 — Every sprite pose, drawn by PixelLab

- The owner connected PixelLab and approved its first frames as "incredibly close to the original" (OWN-026). Its skeleton animator redraws one of the owner's six originals into poses given as joints.
- 53 new frames replace the 34 hand-drawn ones: run in-betweens around the original three, dropback and throw, high, low and diving catches, the tackler's lunge, dive, wrap and drive, falling forward and backward, getting up, fumble recovery, kick, punt, snap, hold, slide, spike and celebrations. The stiff-arm attempt was dropped.
- Each pose is drawn once in a key palette and maps back to the 21 color classes, so it renders in all 32 teams and both skin tones (ENG-026). All 3,392 renders were produced and spot-checked by team.
- Poses carry no ball (OWN-027). One ball sprite from the owner's `arm` pose is drawn at the hand or chest from `assets/sprites/anchors.json`, which also records lift for jumps and dives. Preview plays use it.
- Re-created seven real plays from CHI at SEA with the new frames on the owner's Seattle field: a touchdown pass, a completed pass and tackle, a run with two tacklers, a sack, a field goal, a punt return and an interception (`scripts/sprites/real_plays.py`). Renders stay in ignored `data/` because the field is Gridiron art. Chicago wears a stand-in white road palette because the sheet only has home colors, and skin tones are placeholders.
- The pipeline is in `scripts/sprites/pixellab`, with every hand fix listed. It used 33.1 of the trial's 40 generations, including the color tests and two redraws.

## 2026-11-02 — Sprite review and the first Monday game

- The owner judged the 34 drawn sprite frames a stark downgrade from the 6 original poses (OWN-025). The app won't use them; new poses need a source at the original's quality.
- The PC slept until 53 minutes into CHI at SEA. The worker resumed by itself, filled in the first half and tracked the rest live. Sunday's delayed final checks ran on wake and filled in drives and team stats, closing R-032.

## 2026-11-01 — Sign-in from another local address

- The owner saw "Your account can't open this" when signing in. Their account and session were fine: the page was open at another name for this machine, which has no cookie and fails the sign-in origin check (R-036).
- Other loopback names now redirect to the configured address with path and query kept, checked in a real browser that already had a service worker installed on `localhost`. A refused sign-in now names the address. Not yet on the running app.

## 2026-11-01 — Scoreboards running and first slate measured

- Upgraded the running app with scoreboards after PHI at WSH ended, by owner approval: about 5 seconds offline, no schema change, backup taken.
- Checked the new code against a restored copy of the real database during a real game. It read all 14 games, and 58 real changes reached an open page with no reload.
- Fixed the corrected label: it was on 69% of plays because any new revision counted, and now needs a changed result or credited player (ENG-025).
- Fixed a repeated last-play label, tags touching the play text, and "unknown" scores read aloud for unplayed games.
- Recorded the [first slate](../research/live-slate-receipt-2026-11-01.md): 0 read failures and a median play delay of 36 seconds, replacing an early estimate of about 2 minutes. Closed R-025, R-026 and R-030.

## 2026-10-31 — Live capture and animation scope

- Added private raw copies of every response the live lane reads, adding no requests, with a 5 GiB limit and failures that never reach the feed (OWN-020, R-030). The worker was restarted with it at 2026-11-01 06:23 UTC; 553 backend tests and all static checks pass.
- Measured the owner's sprite sheet and tested it on one real play in scratch: 6 poses recolored, attractive stills, stepped motion. The owner chose the sprite look (OWN-022). Six test frames show upright and falling poses can come close, while a flat ground pose isn't good enough yet. No application code changed.
- Built Live scoreboards: down and distance, possession, timeouts, field position, score by quarter, venue, weather, broadcast and last play, with win probability, team stats, leaders and drives on the game page. Checked against all captured responses and on an isolated port. Not yet on the running app.
- Owner confirmed the art is theirs (OWN-024). Moved the sheet and frames to `assets/sprites` and pushed them alone to branch `claude/sprite-art`, with previews on a plain field.
- Owner approved the test frames (OWN-023). Drew the full private set of 40 frames and rendered five real plays. Nothing reads them in the app yet.
- Owner scoped animation to what is relevant to each play (OWN-021). Spec documents now describe labeled 3D re-creations of the players ESPN names and the ball, replacing the dashed schematic and the 600–1800 ms sequence limit (ENG-023).

## 2026-10-31 — M2 source and agent policy correction

- Recorded live-NFL-game/PBP-only Sleeper scope and GPT-6.1 Sol-only subagent policy. Removed fantasy normalization/mapping and disabled former acquisition commands before cache/network reads; current status/verification excludes retired captures. Historical evidence remains intact.
- Began M2 under the accepted invite/OIDC/member-binding and React/PWA architecture; no provider project, client or external service provisioned.

## 2026-10-31 — M1e supplemental and live sources

- Added immutable public observations and additive 0005 refresh reservations, safe fixed HTTP bounds, daily cross-process Sleeper cache and last-good/fenced publication. Verified directory 12,229/state/add/drop and two explicit candidate stats representations; direct identity hints join 40/121 owned athletes without alias/ownership mutation.
- Verified scoped ESPN scoreboard/summary/core-play sources and canonical participant references across four completed games/842 plays including overtime/tie; pinned 20 factual provider types. Added pure revision-aware offline replay with explicit no-play/missing/unknown behavior and no fantasy arithmetic or route tracking.
- Fixed all four Important independent-review findings with observed failing regressions: per-play page observation time, season-type scope, individual play reference scope and safe malformed-reference recovery. Full check 409 tests plus Ruff/mypy/AJV/foundation passed.
- Implemented exact-context/variant/dated-permission metadata gate and empty Gridiron manifest; fresh uniform/field terms and 2026 navigation verified, no media/contact/grants. Current active/corrected Live cases, source hint gaps and longer serving-threshold tuning remain explicit.
- Final offline proof 25 observations/66 unique objects and repeated actual 197-play capture replay with zero changes/provider calls. FFA snapshot/roster/entity/alias counts unchanged, no active refreshes. No UI, automatic supplemental scheduler, model, recommendation enablement, push or deployment. [Audit](../research/m1e-source-audit-2026-10-31.md), [guide](../engineering/supplemental-live-sources.md), [handoff](handoffs/2026-10-31-supplemental-live.md). M2 is next.

## 2026-10-31 — Comprehensive NFLverse foundation

- Imported the full published catalog: 1,140 logical files across 28 families, 1,087 tables/11,973,952 stored rows and 53 archive-only originals/metadata/reference files. Preserved all columns, historical/legacy/subtype/summary variants, raw data ZIPs and explicit benchmark/diagnostic distinctions. Alternate format mirrors remain cataloged; model ZIPs are excluded as non-observations.
- Added immutable source/Parquet objects, schema/coverage/terms manifests, additive 0003/0004 migrations, durable staged acquisition/publication and source/catalog ordering. All 786 hashless identities passed a second complete catalog check; offline verification covered 1,140 manifests/1,157 unique data objects without network calls.
- Verified exact GSIS/ESPN joins for 121/121 owned athletes and protected canonical-player HTTP reads. Two athletes without weekly rows remain missing. Backed up and closed five later conflicting supplemental aliases with original rows/reports/UUIDs/FFA facts preserved.
- Fixed all five Important independent-review findings with observed failing regressions; full check passes 357 tests plus Ruff/mypy/AJV/foundation. One uppercase-suffix compatibility minor affects zero selected files and remains deferred.
- Added resource-limited nested RDS fallback and explicit nested-history JSON preservation; no R runtime, model execution, member access, recommendations or deployment enabled. M1e supplemental/live-source proof is next. [Audit](../research/nflverse-data-audit-2026-10-31.md), [guide](../engineering/nflverse-ingestion.md), [handoff](handoffs/2026-10-31-nflverse.md).

## 2026-10-30 — Durable canonical FFA synchronization

- Stored exact scoped ESPN UUID aliases/observed affiliations, immutable full policies and scored rule versions, complete league documents and correction history through new `0002_ffa_sync` migration. First/new scoring-lineup contexts require completed ESPN reconciliation; recommendations remain disabled.
- Added private bounded immutable capture archives, offline replay, no-change confirmations, atomic leased publication/completion, durable schedules/retries/pause/freshness and a shared PostgreSQL request gate/circuit.
- Final independent review fixes contain extreme Decimal inputs and corrupt gzip, and recheck leased replay completion; 316 runtime tests plus static/contract/artifact checks pass.
- Added optional secret-and-loopback local reads with no-store, guarded real sync commands and private local profile setup; default API stays health-only and production/member access awaits M2.
- Live ESPN → PostgreSQL → HTTP proof: 8 teams/8 managers, 132 owned/923 available, 128 picks/56 matchups; 797 played games/121 provider zeros/56 lineups reconcile with zero issues. Four refreshes, including automatic-worker and final corrected-code checks, retain one snapshot/outbox; old replay does not promote or refresh. [Evidence](../research/ffa-sync-live-2026-10-30.json), [guide](../engineering/ffa-synchronization.md), [handoff](handoffs/2026-10-30-durable-ffa-sync.md).

## 2026-10-30 — Actual FFA scoring mapping and verification

- Mapped all 46 fetched scoring definitions into the shared exact engine, including D/ST role overrides, allowed-point/yard bands and disjoint field-goal ranges; corrected reference-document ID/contribution errors with pinned provenance.
- Added strict actual-game scope, explicit sparse-counter/no-game-zero handling, per-rule/player/lineup reconciliation and `espn-score-audit`.
- Final reviewed live proof: 797 played player-games +121 provider-zero entries, 56/56 lineup totals across periods 1–7, zero discrepancies. Nine private parsed-input archives replay identical results; eleven rare nonzero categories remain empirically unobserved and disclosed.
- Fixed independent review's cancelling zero-rate contribution and extreme-decimal failure paths; included the tested unbounded-range adaptation. Full runtime check passes 275 tests plus quality/contract checks. Recommendations remain disabled; no dependencies/migrations/provider writes/push/deployment.

## 2026-10-30 — Complete audited ESPN endpoint routing

- Closed the gap between the broad audit and the initial core reader: all 68 recognized successful variants across 19 allowlisted families are callable through the guarded provider client.
- Added corrected player/news/pro-schedule/standings routes, historical period reads, transactions, boxscores/live/rankings/cards, NFL core/site/web metadata and PNG assets. HTTP-success shells remain explicitly limited/metadata-only.
- Added `arbit-worker espn-endpoints [--live]`, full request reconstruction/preflight and safe partial evidence on failure. All 81 audit cases accounted; 13 intentionally excluded.
- Fixed three Important independent-review findings with RED→GREEN tests: nested capability loss, contradictory optional scope, and inconsistent audit outcomes. Final full runtime check: 209 passing tests and all quality/contract checks; post-review live run: 68/68 pass, zero failures.
- Owner explicitly requested proceeding to exact scoring mapping/reconciliation before recommendations. Reference stat-ID and appliedStats descriptions conflict with actual football data; normalization will use pinned provenance and observed source math.

## 2026-10-30 — M1b public ESPN reader

- Owner authorized development using verified public access and excluded message boards; corrected the obsolete 401 blocker and cloned the pinned reference under ignored `.references`.
- Added GET-only public HTTPS transport with response/timeout/pacing bounds, safe typed errors and Retry-After; observed league/player contracts retain exact settings and unknown data.
- Added ownership/context guards and full availability pagination through an empty terminal page; provider short-page caps do not silently truncate inventory. Historical roster/current-availability combinations are rejected.
- Added `uv run arbit-worker espn-inspect`, reporting safe counts/source evidence without a database or credentials. Fresh live proof: eight teams, 132 owned, 923 available, 46 scoring items, 128 picks, 56 matchups; seven requests.
- Full runtime check passes 110 tests plus Ruff/mypy/AJV/foundation checks. Contracts also validate the earlier real combined response and four available pages. Artifact validation excludes ignored local captures/reference checkouts while retaining project checks.
- Canonical identities, actual scoring reconciliation, durable production sync, member auth and UI remain future work. No dependency, provider setting, remote branch or deployment changed.

## 2026-10-30 — Public ESPN capability audit

- Owner enabled public league viewing for testing; no final access policy selected.
- Reviewed every tracked file at pseudo-r reference commit 097c42f; tested all 21 documented views/nine client request families through 81 cookie-free GET probes.
- Verified core data access, actual FFA settings, 923 available players, exact 132-player roster ownership match, 128 picks, 389 unique transactions and an NFL PBP sample.
- Recorded field/domain/filter discrepancies, explicit communication denial, legacy HTML responses and full sanitized request/checksum evidence. Raw bodies remain ignored local research data; no runtime code, dependencies, cookies, provider writes or production sync changed.

## 2026-10-30 — M1a runtime/core/snapshot implementation

- Recorded owner architecture/stack approval, dependency authorization and explicit UX/UI quality requirement.
- Added pinned Python/pnpm workspaces, frozen lockfiles, PostgreSQL image and reproducible local/check commands.
- Implemented fixed FFA config, temporal identities, exact rule-based scoring, migrations, atomic snapshots/outbox and lease-fenced durable jobs.
- Added synthetic-only worker composition and health/readiness-only API; no private data routes or production auth bypass.
- Verified 45 tests after review, including real database concurrency/retry/fencing/correction cases, isolated-schema migration/readiness and nonblocking exhausted-job cleanup. Fresh-schema standalone CLI and actual loopback HTTP smoke passed.
- Added runtime CI and updated documentation. Final branch review/verification details are in the M1a handoff. No real FFA access, frontend UI, model, push or deployment is claimed.

## 2026-10-30 — Initial planning foundation

- Preserved owner brief unchanged and recorded FFA league 1729878439 / season 2026 / portable local-first preference.
- Prepared product/feature requirements, 57-item traceability, system/data/API/model/design specifications and four proposed ADRs.
- Added cross-provider agent entry point, review/plan/implement/validate/document/handoff standards, validation guidance, operational runbook and templates.
- Defined dependency roadmap through Archive and integrated release, plus concrete first runtime/core/snapshot plan.
- Added initial contract schemas, synthetic recommendation example, semantic design tokens and responsibility-based repository scaffold with local/CI artifact checks.
- Researched primary provider/technology sources; recorded unauthenticated FFA settings 401 and one public ESPN completed-game summary 200. No private credential, provider write, paid hosting or product runtime was created.
- Verified foundation artifacts and nine rejection cases; fresh builder review found no material planning gaps. Initialized local Git on main without commit/remote; secrets/data/cache ignore checks passed. Actual evidence and remaining runtime limits are in the dated handoff.

## 2026-10-31 — M2 member application

Implemented invited OIDC accounts, opaque sessions, approved manager bindings, administrator access controls, generated contracts and the responsive Front Office/PWA. Added player search/drawer/watchlist/themes, historical/null/source handling, private-safe offline/update behavior and populated migration preservation proof. Google selected; real private client/member acceptance remains open. No external provisioning or deployment. [Handoff](handoffs/2026-10-31-member-application.md).

M2 final validation: 453 backend / 14 client tests and 7 Chromium scenarios pass after the Sol review’s account-switch, apostrophe-search and fixture-invitation fixes. No real Google/member login is claimed.

## 2026-10-31 — Private Google configuration prepared

Moved the owner-provided ignored configuration into root `.env.auth.local` and set mode 600. Verified Git exclusion, complete real-OIDC configuration, unauthenticated member boundary and local database readiness without exposing credentials or making provider calls. Actual Google/member sign-in remains unverified.

## 2026-10-31 — First-name manager assignment labels

Owner confirmed the real first-administrator Google/binding/Front Office flow. Manager choices now prefer verified ESPN first names plus team context, with handle fallback/disambiguation. Live sync populated eight first names and preserved all manager IDs/approved bindings. Original captures remain compatible; unused surnames/email/notification fields remain excluded.

## 2026-10-31 — Design reset and real-time platform

Owner decisions OWN-013–017 recorded. Replaced the generated-looking interface with an officiating-and-broadcast character, removed all slogan copy, and added `pnpm check:design`. Added `arbit-worker run`, migration `0007_realtime`, NFL team directory and schedule, live game state and play revisions, per-source freshness, a session-bound SSE stream, a Live scoreboard and plays, and per-device sessions. Fixed from real data: float noise in official totals, pregame 0–0 scores, standings in provider order, roster in provider order, data age measured from last change instead of last confirmation. Corrected stale documents. Verified on a restored copy, then applied to the running app on 2026-11-01 04:26 UTC as systemd user services. [Handoff](handoffs/2026-10-31-platform-reset.md).

## 2026-10-31 — Live prerequisites

Owner accepted the design (OWN-018) and moved Live ahead of M3 (OWN-019). Verified Gridiron URL patterns and publication timing, and stored week 8 art privately. Measured how much of a play ESPN's feed supplies. Recorded 19 prerequisites and a single-play quality gate for animation. No application code changed.
