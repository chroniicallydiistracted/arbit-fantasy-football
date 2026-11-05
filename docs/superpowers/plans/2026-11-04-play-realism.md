# Task: Play realism from the owner's clip review (OWN-037)

Status: done in code 2026-11-04 (ENG-038); the owner's answers are OWN-038. The comparison clips are rendered for the owner's second look at the video.

- **Requirement IDs.**
  - LV-003: canonical play graphics.
  - Owner direction: OWN-032 (only the players in the play), OWN-033 (natural motion), OWN-035 and OWN-036 (where players start, by position), OWN-037 (this review).
- **Owner review (OWN-037).** The owner compared the 16 play-type clips (`data/sprites/review/play-types/`) with the game's video.
- **Fixtures prepared.** All are real ESPN plays in `tests/fixtures/live/play-facts.examples.json`; every existing rule still passes on them. Five are new:
  - `pass_deep_tackled_by_safety`: CHI at SEA Q2 9:34, clip 01.
  - `interception_intended_receiver`: Penix intended for J.Dotson, a pick that wasn't tipped.
  - `defensive_holding_wipes_out_sack`: CHI at SEA Q3 2:21.
  - `offensive_pass_interference`: CHI at SEA Q3 0:14.
  - `illegal_contact_declined`: CHI at SEA Q4 4:03.

  `tests/fixtures/live/team-units.example.json` gives each team's starting center, long snapper and quarterback from its 2026 depth chart, such as SEA J.Sundell, C.Stoll and S.Darnold, and the four colors nflverse lists for each team.

## The items

### 1 and 2. Coverage defenders track the receiver and arrive on time

- **Owner, in short.** A backpedalling defender should track the receiver with a natural backpedal, not head straight for the catch spot. He should begin tracking in time to meet the receiver at the tackle, never arrive early. In clip 01 the safety backpedals, reaches the tackle spot, backpedals away, then runs back up to tackle.
- **Measured in clip 01.**
  - J.Love backpedals 3 yards and then waits at 16 yards for 1.9 seconds. His wait cycles the quarterback's drop-back frames, which read as more backpedalling (item 4).
  - Burden runs past him. Love then runs to 25.4 yards, past the tackle at 23, and lunges back.
- **Causes.** Every new tackler aims 2.4 yards in front of the carrier, even one behind him. Defenders wait instead of covering.
- **Fix.**
  - A defender named on a pass is drawn from the snap as the receiver's cover man: the pass defender, the interceptor, and a linebacker or defensive back who makes the tackle.
  - He backpedals at a natural pace, mirroring the receiver across the field and keeping a cushion that shrinks as the receiver closes.
  - When the cushion runs out, or the ball is thrown, he turns and runs at the receiver. He meets him at the catch or, through the run after it, at the tackle.
  - The tackle comes from wherever he is: behind, beside or in front.
- **Rules added to the checks.**
  - No defender is within a yard of the catch spot before the catch.
  - No tackler passes the meeting point and comes back.
  - A backpedal moves away from the line at no more than a backpedal's pace.
  - A cover man stays deeper than a deep receiver until the throw.
- **Fixtures.** `pass_deep_tackled_by_safety`, `pass_without_yards_after_catch`, `pass_incomplete_qb_hit`.

### 3. The ball and the receiver arrive together

- **Owner, in short.**
  - The throw's timing decides it. The receiver is never slowed.
  - Ball speed doesn't change on long passes.
  - A short pass that can't make it in time at normal speed becomes a bullet with little arc. Deep passes are never bullets.
- **Measured.** In clip 01 Burden reaches the catch spot at 3.26 seconds and the ball at 4.02. Short receivers settle and wait by design (OWN-033's "settle facing the quarterback and come back to the ball"), which this replaces.
- **Fix.**
  - The catch happens when the receiver gets there. Release is the catch minus the flight at normal speed: 26 yards a second short and 22 deep, unchanged.
  - If the quarterback can't throw that early, a short pass flies faster, up to 32 yards a second. The renderer's arc flattens on its own with the shorter flight.
  - Past that, and on any deep pass, the route runs longer.
  - A comeback or curl catch is a turn on arrival, not a wait.
- **Rules.** No standing pose for the receiver in the 0.6 seconds before a catch. Deep passes fly at the deep pace. Short passes fly no faster than 32 yards a second.
- **Fixtures.** Every pass case.

### 4. Waiting players don't borrow the quarterback's pose

- **Owner, in short.** The pose before the windup, holding the ball, is right for the quarterback. Others should use the idle pose or a ready pose.
- **Measured.**
  - The "wait in place" step gives everyone the quarterback's `drop_b` and `drop_c` frames. Those are the frames he holds the ball in before the windup.
  - The DROP cycle used for a defender's backpedal uses the same frames.
- **Fix.**
  - **Before the snap:** players hold `ready`.
  - **After the snap:** players waiting sway in `ready`, and players done with the play stand in `stand`.
  - **Quarterback:** only he uses the pocket frames.
  - **Backpedal:** defenders backpedal with the renderer's empty-handed copies of the drop frames.
  - If those still read as holding a ball, a backpedal pose from PixelLab needs the owner's approval.
- **Rule.** No player but the quarterback shows a drop-back frame, apart from the empty-handed backpedal.

### 5. Interceptions: the intended receiver is drawn, and nobody waits for the ball

- **Owner, in short.** The interceptor arrives and waits, as if the pass were thrown to him. The intended receiver named in the text should be drawn. Both should arrive at about the interception spot with the ball, the interceptor closer to it.
- **Measured.**
  - **Intended receivers:** ESPN lists the intended receiver among "other" players on most of the 28 captured interceptions. In clip 03 that's AJ Barner, SEA tight end. He can be matched by name and team through the depth charts.
  - **Clip 03 was tipped.** The pick is 3 yards behind the line, and "(A.Booker)" after "INTERCEPTED by J.Lynch" names Chicago's left end. Three of the 28 picks have a name there, which looks like the player who tipped it.
- **Fix.**
  - The intended receiver runs his route to the ball's spot. The interceptor covers him (item 1) and undercuts, catching at the spot as the ball arrives, with the receiver a step away.
  - A tipped pass is deflected by the named defender, then caught.
- **Fixtures.** `interception_return` (tipped, clip 03), `interception_intended_receiver`.

### 6. The sacked quarterback moves and escapes right

- **Owner, in short.** The quarterback steps back to the sack spot and stands. He should move naturally and scramble slightly right before the sack.
- **Measured.** After his drop he works his pocket frames in place until the hit (clip 04).
- **Fix.** The drop, a set with pocket footwork, then an escape to his right (the far side) at his pace for 0.6 to 1 second. The sacker meets him there, at ESPN's spot.
- **Rule.** The quarterback runs in the last half second before a sack.
- **Fixtures.** `sack`, `defensive_holding_wipes_out_sack`, plus the face-mask sack (clip 16).

### 7. The team's snapper snaps the ball

- **Owner, in short.** On every snapped play the team's primary snapper, from the pre-game depth chart, snaps the ball, then stays in position and takes no part in the play.
- **Fix.**
  - **Who:** the starting center on scrimmage plays, and the long snapper on punts, field goals and tries, from the depth chart before the game (`team-units` fixture). ESPN's text name, when given ("Center-C.Stoll"), wins.
  - **The snap:** he snaps from `snap_ready` into `snap_release`, and the ball leaves from his hands.
  - **After the snap:** he stays over the ball in his stance with a slight sway.
  - This adds a player ESPN doesn't name, at the owner's direction.
- **Rules.** The snapper stays within half a yard of the line all play. The ball's first flight starts at his hands.
- **Needed.** A mapping from ESPN's team IDs to nflverse's team abbreviations. The live app needs it too (slice 7).

### 8. Runs show the quarterback handing off

- **Owner, in short.** Running plays should show the quarterback immediately handing off to the rusher.
- **Fix.**
  - **Who:** the offense's quarterback is drawn on runs. He's the team's last passer in the same game, else its depth chart starter.
  - **The handoff:** he takes the snap and hands off at once, by about 0.5 seconds after the snap. The ball goes from his hands to the rusher's chest at the mesh.
  - **After:** he carries out his fake or stays in the backfield standing.
- **Rule.** On a run the ball goes from the snapper to the quarterback to the rusher, with the handoff no more than 0.8 seconds after the snap.
- **Poses.** There is no handoff frame. Existing frames can approximate it, or PixelLab can draw a handoff and a take; that's the owner's call.
- **Fixture.** `run_gap`: R.Johnson, with C.Williams at quarterback and G.Bradbury at center.

### 9. Name tags in team colors, without the box

- **Owner, in short.** Remove the label background and color the names in the team's two best colors that aren't black.
- **Data.** The four colors nflverse lists for each team are imported and exported to the `team-units` fixture.
- **Measured.**
  - **Contrast:** for 21 of 32 teams, the most readable color that isn't black-like falls under 3:1 against the turf on its own. An outline has to carry it.
  - **Outline options:**
    - **The team's darkest color:** the letters stand out from it at 4.4:1 or better for 27 teams. It is weakest for Buffalo, Tennessee, Houston, Miami and Baltimore.
    - **The second team color:** it is itself under 2.5:1 against the turf for 29 teams.
- **Preview.** `scripts/sprites/name_tag_preview.py` writes `data/sprites/review/name-tags-preview.png`, with every team on both turf shades in today's boxed style and three without the box:
  - A: the fill outlined in the second color
  - B: a thin outline in the team's darkest color
  - C: a shadow in the second color
- **Owner's choice.** The style.

### 10. Defensive pass interference, and the fouls around it

- **Owner's rules.**
  - **Timing:** the restriction begins when the ball is released and ends when it is touched. Contact before the throw is defensive holding.
  - **Where:** it applies more than a yard past the line.
  - **Catchability:** the ball must be catchable.
  - **The common actions:** playing through the receiver's back, an arm bar or grab, or cutting off his path.
- **Measured in the captures.** 13 DPI plays (11 wiping out the play), 21 defensive holding, 6 illegal contact and 3 offensive pass interference. Most of the CHI at SEA ones are fixtures.
- **Fix.**
  - **DPI:**
    - **Contact:** after the release and before the ball arrives, more than a yard past the line. The cover man (item 1) makes contact with one of the three actions, chosen per play, and the receiver stumbles.
    - **The ball:** it arrives where he would have caught it and falls incomplete.
    - **The flag:** thrown at the contact by the nearest official.
  - **Defensive holding:** a grab before the throw, flagged then.
  - **Illegal contact:** contact more than 5 yards past the line before the throw.
  - **Offensive pass interference:** the receiver pushes off during the flight.
- **Rules.**
  - DPI contact is after the release, before the arrival, and more than a yard past the line.
  - The ball lands within 2 yards of the receiver's path.
  - The flag is thrown at the contact.
- **Fixtures.** `penalty_wipes_out_pass` (DPI, clip 15), `defensive_holding_wipes_out_sack`, `offensive_pass_interference`, `illegal_contact_declined`, `declined_penalty`.

## Order, owner inputs and evidence

- **Order.**
  1. Poses (4)
  2. Pass timing (3)
  3. Coverage (1, 2)
  4. Interceptions (5)
  5. The DPI family (10)
  6. The sack (6)
  7. The snapper and the run quarterback (7, 8)
  8. Name tags (9)
- **Owner inputs.**
  - **Name tags:** style A, B or C.
  - **Poses:** existing frames or PixelLab for the handoff and, if needed, the backpedal.
  - **Tips:** confirm from the video that Booker tipped the clip 03 pass.
  - **Snapper:** after the snap he stays in his stance with a slight sway.
  - **The fouls around DPI:** apply the same contact depiction to holding, illegal contact and offensive pass interference.
- **Evidence.**
  - **Checks:** the rule check and renderer audit, with the new rules, over every captured play.
  - **Tests:** a test for each item on its fixtures.
  - **Renders:** the 16 play-type clips again, plus the interception without a tip and the DPI, holding and OPI plays, for the owner to compare with the video.
- **Supersedes and amends.**
  - Item 3 replaces OWN-033's short receiver who settles and comes back.
  - Items 5, 7 and 8 add players ESPN doesn't name, or names only as "other", amending OWN-032 at the owner's direction.

## Owner answers (OWN-038) and outcome

**Answers.**
- **Name tags:** style C.
- **PixelLab:** may draw a handoff, a backpedal and an idle set; the handoff is the quarterback handing off to a running back.
- **Clip 03:** the pass was tipped and caught by another defender.
- **Snapper:** stays in the field goal snapper's position, or strafes.
- **Fouls:** the other coverage fouls are drawn too, and officials throw the flags.

**Sprites.** 7 PixelLab generations; the trial's 40 are spent and 3 of today's bonus remain.
- **Player poses:** 11 frames in `assets/sprites/frames/situational.txt`, from the owner's standing player: two stances, two idle weight shifts, a four-frame backpedal, the handoff and follow-through, and the take. Their anchors and region maps are installed.
- **The official:** made from the owner's standing player with one edit. Eight posed frames are in `assets/sprites/officials/`: idle, a four-frame jog, the reach, the throw and the follow-through.
  - **Fixed palette:** officials never take team colors. The shirt uses the jersey letters, so he centers like a player.
  - **Converter:** `scripts/sprites/pixellab/officials.py` removes the yellow flag the model painted into three frames, and a motion streak.

**Built** (ENG-038). Every item above, in the planned order.
- **Choreographer:** `choreography.py`, `kicking.py` and `incidents.py`.
- **Units:** each team's center, long snapper and quarterback through a game, from `scripts/live/positions.py` `GameUnits`.
- **Renderer:** the backpedal and official jog cycles, the officials' palette, the handoff's hand, and style C tags in team colors from nflverse.
- **Script contract:** actors may now be on the `official` side.

**Found by the audit and fixed.**
- **A shadowed variable:** a cover man who had to turn and run aimed 9 yards short of the play.
- **Route lengthening:** a route lengthened twice was measured from the straight route, so the throw left before the quarterback had the ball.
- **Tacklers backing off and coming again:** they had stopped near the tackle spot. Cover men now stay in coverage through a completed catch, and a close chaser sets and comes straight in.
- **Cover men at the catch spot:** they could stand there. Cover men now drop at the snap and keep a 2-yard cushion.
- **A cover man who couldn't get there:** his spot now sets how long the route runs, never his speed.
- **A foul on the wrong player:** holding was drawn on someone it wasn't called on. Fouls are now drawn only on their player.
- **Out-of-bounds plays:** a cover man ended frozen in a three-second "run". He now shoves the carrier out, or trails him into the end zone.
- **Flags:** an official could jog before the snap, and two could start on one spot.

**Checks.** All pass.

| Check | Result |
| --- | --- |
| `check_play_scripts.py`, with positions and units | 0 broken rules over all 14 captured games |
| `check_play_scripts.py --no-positions` | 0 broken rules |
| `audit_render.py` | 2,254 scripts, 0 problems |
| `uv run pytest -q` | 1,085 passed |
| Ruff, format, mypy, `pnpm check:contracts`, `pnpm check:client`, `make check` | Passed |

**New rules in the rule check:**
- the receiver and ball arrive together, and he doesn't wait for it
- no pass is faster than a bullet
- no defender waits at the catch spot
- no tackler backs off and comes again
- the snapper stays over the ball
- the handoff comes right after the snap
- the sacked quarterback escapes
- officials are allowed, unnamed

**Tests:** `test_realism.py` covers each item on its real plays.

**Renders.** `render_script.py --types` writes 19 comparison clips, with position tags and style C names, to `data/sprites/review/play-types-2/`. That's the 16 play types plus offensive pass interference, holding that wiped out a sack, and illegal contact, all from CHI at SEA. The full game was re-rendered in batches as the draw-everything check. The untipped interception (`interception_intended_receiver`) is an Atlanta game, whose uniforms aren't measured, so it is checked by tests rather than rendered.

