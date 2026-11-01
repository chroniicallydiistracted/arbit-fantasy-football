# Live scoreboards and game animation: prerequisites — 2026-10-31

Owner direction (OWN-019): build Live scoreboards and game animation next, and avoid basic or low-quality animation: "more than just SVG draws, or low effort/quality stepped animations." This records what stands between today's code and that result. Art findings are in [Gridiron URL patterns](gridiron-url-patterns-2026-10-31.md).

## The limit that shapes everything

**No public feed says where players are.** ESPN's plays have no coordinates, and no public live tracking feed turned up in research. The animation is therefore a re-creation from the play description, like a broadcast graphic. Measured on all 197 stored plays, from one final game (CAR at GB):

| From ESPN, so shown as fact | Coverage |
| --- | --- |
| Start and end spot, down and distance | 197 of 197 |
| Who threw, caught, ran, tackled, kicked or returned | 166 of 166 football plays |
| Pass depth and side (`pass short left`) | 76 of 78; the others are a two-point summary and a spike |
| Run direction (`left tackle`) | 49 of 49 |
| Play type, yards, score, turnover and penalty flags, clock, wall-clock time | All |

**Re-created, never in the feed:** route shapes, the ball's position across the field's width, snap-to-throw timing, ball arc and contact. One game is thin evidence. Tomorrow's slate tests these rates on 13 more.

**Owner decision (OWN-021):** "We can animate everything that is relevant to the play. Other players and their positions do not need to be animated. We will animate the plays specifically." So a play shows the players ESPN names and the ball, with no invented formations, blockers or pursuit. It keeps a permanent "Re-creation from play-by-play" label and a view of the observed facts (ENG-023), lands on ESPN's exact spots and is never presented as tracking. The spec documents are updated to match.

Distinct players named per football play, across the same 167 plays:

| Players | 0 | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- | --- |
| Plays | 1 | 11 | 49 | 81 | 23 | 2 |

That is a much smaller scene than 22 players, so each player can carry more detail. The risk moves to composition: a small cast on a full field could look empty, so camera framing has to make it look deliberate.

## Prerequisites

Status: ✓ ready, ◐ partly ready, ✗ missing.

| # | Prerequisite | Status | What it takes |
| --- | --- | --- | --- |
| 1 | Real play data | ✓ | Stored as append-only revisions with corrections |
| 2 | Field and uniform art | ◐ | Week 8 fetched. Needs a sync lane and game status |
| 3 | Live game situation | ◐ | Possession, down and distance, timeouts and red zone are expected in ESPN's `situation` block only during games. Its shape is unobserved and the code doesn't store it. Raw copies of every live read have been kept since 2026-11-01 06:23 UTC (R-030), so tomorrow's first real look is retained |
| 4 | Other scoreboard data | ✗ | ESPN offers venue, weather, broadcast, leaders, team colors, drives (25 in the sample game) and win probability per play (197 points). All are discarded. No schema change needed: `nfl_game.payload` is JSON |
| 5 | Play latency measurement | ◐ | `wallclock` and `first_observed_at` are stored, so tomorrow measures it (R-025) |
| 6 | Play interpreter | ✗ | Turn text and participants into a structured script. Testable now against stored plays |
| 7 | Choreography engine | ✗ | Motion for each named role and a timing solver that lands on ESPN's spot. No formations, assignments or pursuit (OWN-021). `ftn_charting` (through week 7) and `nextgen_stats` may calibrate timing; columns still to profile, and FTN carries CC-BY-SA attribution |
| 8 | Renderer | ✗ | Real-time 3D in the browser. Recommended: three.js on WebGL2 first. WebGPU only after device testing: Safari added it in version 26, and one engine developer reported it unusable on iOS 26.2 |
| 9 | Player model | ✗ **owner** | Rigged football player with helmet and pads. With at most 5 on screen in the stored game, one high-detail version may be enough. This most decides whether it looks premium or cheap. One [CGTrader listing](https://www.cgtrader.com/3d-models/character/fantasy-character/american-football-player-071fb94a-4e1d-4bce-b191-0ec5e6d95ccc) is rigged, offers glTF with 3,500 and 48,000-face versions and is sold royalty-free; helmet, pads and license details need checking before purchase |
| 10 | Motion clips | ✗ **owner** | Run, cut, throw, catch, tackle, kick, punt, hold, snap, get-up. Mixamo is free and reportedly allows use embedded in games, not redistribution of the raw files; football clip coverage and current Adobe terms are unverified, and it needs the owner's Adobe account. Layered with procedural foot planting and blending so plays don't look canned |
| 11 | Uniform-to-player textures | ◐ | The shared template makes this automatic once one model is mapped to it. Real numbers must replace the 11. Team-specific number fonts can't be reproduced from a single 11 |
| 12 | Field rebuild | ◐ | One calibration fits all. Redraw lines procedurally, rebuild logos at high resolution, add a turf shader |
| 13 | Private asset delivery | ✗ | Gridiron-derived files need a session-checked route with private caching, outside the public shell and service worker |
| 14 | Security policy | ✗ | Compressed-asset and physics decoders need `'wasm-unsafe-eval'`, which `script-src 'self'` blocks today. Scope it to Live if possible |
| 15 | Load strategy | ✗ | Split 3D into the game page only. The whole client is 540 KB today, and models and textures add megabytes |
| 16 | Device floor | ✗ **owner** | Which phones and computers must run this smoothly. It sets model detail and quality tiers. With few players on screen, the field and per-player shading become the main costs |
| 17 | Review tooling | ◐ | Chromium here renders WebGL2 in software only, with no WebGPU. The host's RTX 3070 Ti isn't reachable from it. So review video comes from deterministic frame-by-frame capture, and frame rates must be measured on real devices. Blender, ffmpeg and glTF compression tools are not installed but are free to add |
| 18 | Accessibility | ◐ | Text feed stays the equivalent. Reduced motion, keyboard replay and step controls are required (LV-003) |
| 19 | Corrections while animating | ◐ | Revisions exist. Needs a play queue, and a rule for replaying a play that ESPN changes or cancels |

## Quality bar

These are acceptance criteria for LV-003, not aims:

- Continuous skeletal motion with blending and planted feet. No stepped frames, no sliding figures, no shapes along a path.
- The ball flies on a physical arc and arrives when and where the receiver does.
- Every play ends on ESPN's exact spot, with the correct players involved and no others.
- Camera framing makes the small cast look deliberate, not like an empty field.
- Broadcast camera work rather than a fixed top-down view, with real weekly field and uniforms.
- The label stays visible and the observed facts stay one action away.

**Gate:** one real play goes first: a pass from CAR at GB, the one game with listed field and uniforms and stored plays. The owner reviews rendered video of it. No other play type is built until that look is approved, because the player model and motion could still miss the bar and be expensive to change later.

## Proposed order

1. **Done 2026-11-01:** raw copies of the responses the worker already fetches, adding no ESPN requests (OWN-020).
2. **Scoreboards:** items 3–5, using real captured games. No owner assets needed.
3. **Gridiron sync and private delivery:** items 2 and 13.
4. **Single-play slice:** items 6–12, 14, 15 and 17, ending at the owner's review gate.
5. **All play types:** pass, run, sneak, sack, interception, field goal, PAT, punt, kickoff, fumble and penalty, plus corrections, accessibility and full-slate performance.

Not ready for tomorrow's games: the animation. M3 and M4 move later as a result, with the league in week 8 of 14 and the trade deadline on 2026-12-02.
