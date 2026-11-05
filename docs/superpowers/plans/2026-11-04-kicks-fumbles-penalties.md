# Task: Play scripts for kicks, fumbles and penalties (automation slice 3)

Status: done in code 2026-11-04; the owner's first review was fixed (OWN-035) and the clips re-rendered for a second look

- **Requirement IDs.** LV-003 (play graphics for punts, kickoffs, field goals and extra points). LV-005 (a revised play gets a new script).
- **Specifications and decisions.**
  - [Automation plan](2026-11-03-live-play-automation.md), items 2 and 11.
  - [Slice 1](2026-11-03-play-facts.md), [slice 2](2026-11-03-choreography.md).
  - Owner direction: OWN-029/030 (kicks through the posts; the full field), OWN-031 (ball spin), OWN-032 (only the players in the play), OWN-033 (natural motion), OWN-034.
  - Engineering decisions: ENG-029 (depth order and the net), ENG-030 (spin), ENG-032–034.
- **Baseline.**
  - Slice 1 gives facts for every play, with kick results on all 114 punts, 149 kickoffs and 57 field goals, and the try attached to each of the 74 touchdowns.
  - The 29 fumbles and 133 no-play penalties have facts but no template.
  - Slice 2's choreographer draws scrimmage plays with natural motion. The hand-made `real_plays.py` kicks were accepted by the owner, though they used a 7-yard hold; the data says 8.
- **Measured.**
  - **Penalties:** of the 133 no-play penalties, 61 are fouls before the snap (52 false starts) and 72 come after a play the text describes.
  - **Fumbles:** most have the form "FUMBLES (forcer), RECOVERED by TEAM-Name at SPOT", sometimes followed by a return.
- **Scope.**
  1. **Kicks.**
     - **Field goals:** snap to a holder 8 yards back, the kick end over end, and every result. A good kick goes between the uprights above the bar and into the net. Wide left or right passes outside that upright, a kick that hits an upright or the crossbar bounces off it, a short kick falls in front, and a blocked kick deflects off the blocker.
     - **The try after a touchdown:** its own script, an extra point from the 15 or a two-point try from the 2.
     - **Punts:** a long snap and a spiral to the landing spot. The result is a return, fair catch, touchback, out of bounds, downed or muffed.
     - **Kickoffs:** off a tee, end over end. The result is a return, touchback, out of bounds, short of the landing zone, onside or muffed.
     - **Spikes.**
     - **Who appears:** kick unit players the text names without an ESPN ID, such as "Center-C.Stoll", appear under their text name.
  2. **Fumbles.** The play up to the fumble, the ball loose, and the recovery: the recoverer falls on it and, if the text says so, returns it. Other fumble forms keep their text.
  3. **Penalties.**
     - **Fouls before the snap:** the penalized player at the line and a flag.
     - **Plays wiped out by a foul:** the play the text describes, then a flag, captioned "No Play".
     - **Accepted penalties on a play that counts:** a flag where the foul happened.
     - **How flags are drawn:** a new `props` list in the script, thrown in by an official who isn't drawn.
- **Exclusions.** Laterals, aborted snaps and multi-fumble plays stay as text. Officials and players ESPN doesn't name aren't drawn, except kick unit players the text names.
- **Acceptance.**
  - **Rules over every captured play:**
    - a kick lands on the facts' landing spot
    - a good kick crosses between the uprights above the bar
    - a wide-left miss passes on the near side
    - a return ends on ESPN's spot
    - a fumble's ball reaches the recoverer
    - every flag lands on the field
    - natural motion holds, and only the players in the play appear
  - **Evidence:** CHI at SEA's kicks, tries, fumbles and penalties rendered for the owner's review.
- **Rollback and data.** No migration and no change to the running app. The script contract gains `props` (version 1 stays valid; the list is empty when unused).

## Evidence and outcome

**What was built** (ENG-035).
- `libs/arbit-data/src/arbit_data/live/kicking.py` covers field goals, punts, kickoffs and `choreograph_try`.
- `libs/arbit-data/src/arbit_data/live/incidents.py` covers fumbles, the three kinds of penalty, flag placement and caption fitting with flags.
- `choreography.py` gained:
  - the `Prop` contract and `PlayScript.props`, with an optional `Actor.espn_id`
  - spikes
  - kick coverage in `_carry`
  - text names for kickers, punters, returners and blockers
  - captions that keep the return of a kick
  - `fit`, which shortens long captions
- `play_facts.py` gained `PlayFacts.before`.

**Rules over every captured play.** `uv run python scripts/live/check_play_scripts.py` checks all 14 captured games and reports 0 broken rules.
- **Scripts:** 2,182 of 2,196 football plays get one:
  - kicks and fumbles: 149 kickoffs, 114 punts, 57 field goals, 18 fumbles
  - penalties: 133 no-play penalties
  - slice 2 templates: 826 passes, 724 runs, 71 sacks, 42 scrambles, 24 interceptions, 18 kneels
  - spikes: 6
- **Tries:** 72 of 74 get a script: 62 extra points and 10 two-point tries. The other two are ESPN scoring summaries with no play detail.
- **Stay as text:** 11 fumbles, 2 laterals and 1 trick play.
  - Of the 11 fumbles, 10 are aborted or loose snaps ("X to TEN 24 for -5 yards. FUMBLES") that the scope leaves as text. The other is a scoring summary.
- **Rules checked:**
  - **Placement:** a kick comes down on the facts' landing spot, or at the returner's hands within 1.6 yards. A return ends on ESPN's spot, and a return touchdown reaches the end zone.
  - **Place kicks:** a good field goal or extra point crosses between the uprights above the bar. Wide left passes on the near side and wide right on the far side.
  - **Fumbles:** the ball reaches the recoverer at ESPN's recovery spot, within reach of him.
  - **Flags:** every flag lands on the field, and every penalty has one.
  - **Motion and players:** the slice 2 natural-motion rules hold. Only players ESPN names appear, none twice, and a player with no ID has a text name.

**Tests.**
- **Data library: 550 pass.**
  - `test_kicks_fumbles_penalties.py`: 26 tests.
  - `test_choreography.py`: now runs its rule tests over every scripted case.
  - `test_play_facts.py`: tests `before`.
  - Three real CHI at SEA cases were added to the fixtures: a play wiped out by pass interference, a delay of game, and a fumble recovered and returned.
- **Full suite: 827 pass.**
- **Static checks:** Ruff, the format check, mypy, `pnpm check:contracts` (both script examples), `pnpm check:client` and `make check` pass.

**Measured while building.**
- **Kicker approach:** the hand-made approach was 3.4 yards a second, a slow-motion run. The kicker now starts two steps back and two over and comes at his own pace.
- **Tacklers on fumbles:** ESPN lists the play's tacklers and the return's together (R-041).
- **Flags:** thrown from one sideline, a far-side flag flew 30 yards. Each now comes from the nearest official and lands where the foul was: interference on the receiver as the ball arrives, roughing at the passer, a late hit where the play ended.

**Evidence for the owner.** `render_script.py --slice3` plus the four slice 2 plays with a flag render CHI at SEA's 44 clips into ignored `data/sprites/review/generated/`:
- 11 kickoffs, 8 punts, 4 field goals and 6 tries
- 10 plays wiped out or fouls before the snap
- 1 fumble returned
- 4 passes, runs and sacks with a flag

Checked by eye: the field goal, the fumble and the pass interference.

## Owner review, 2026-11-04 (OWN-035)

**Findings.**
- **"L. Jackson".** The owner saw a player named "L. Jackson" in the fumble who shouldn't be there. The only Jackson in that play is CHI's J.Jackson, ESPN 3930040, the guard flagged for a false start earlier in the game. ESPN's text and participants credit him with tackling Lawrence's return ("D.Lawrence to CHI 25 for no gain (J.Jackson)"). What was wrong was where he was drawn: past the line of scrimmage near the far sideline, standing for four seconds.
- **Start positions.** Defenders must start at or behind the line of scrimmage on most plays.
- **Kickoff coverage.** In a kickoff return, the tacklers started around the 50. That is the 2026 kickoff rule, coverage at the receiving 40 until the catch, and the owner chose to keep it.

**Measured.**
- **Committed slice 2 code:** 441 tacklers ran before the snap, and 13 players started on the wrong side of the line. A new tackler was placed within a sprint of the tackle wherever that was.
- **This slice before the fix:** 118 kickoff coverage players were at the receiving 40 (correct). Interception chasers started 9 yards past the line, fumble recoverers on the wrong side, and punt coverage up to a yard past the line.
- **Kickoff from the 20:** a free kick after a safety put its coverage at the receiving 40, 40 yards past the tee.

**Fixed** (ENG-036).
- **Where players start:** the offense on or behind the line, and the defense on or beyond it, at most 20 yards deep. Kickoff coverage is 25 yards past the tee, whatever the kick spot.
- **Movement:** nobody runs before the snap. A new tackler starts within the sprint he has time for after it, and the carrier weaves if he needs longer.
- **Offensive chasers** hold their ground at the line until they break. A first try had them leave at the snap like receivers, and J.Jackson then stood near the play for two seconds.
- **Punt coverage** releases at the snap.
- **J.Jackson** now lines up on Chicago's side of the line and comes after Lawrence.
- **New checks:** the start rule, the kickoff line and "nobody runs before the snap" are in `check_play_scripts.py` and in a test over every scripted fixture. Both report 0 broken rules.

**Effect.**
- **Carriers holding the ball:** they don't stand with it any more than in slice 2. The 42 scrambles are the quarterback in the pocket, as before.
- **Exception:** on six kick and return plays, the returner hesitates 0.7 to 1.2 seconds before the tackle, either because he was swarmed for no gain or because his kickoff coverage could only leave at the catch.
- **Re-rendered:** every CHI at SEA clip, slice 2 included.
