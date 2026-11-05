# Formation, personnel and position sources for play alignment — 2026-11-04

The owner asked whether the live data or nflverse play-by-play describes formations for offense and defense beyond pass or run. The aim is to give the players drawn on a play a general pre-snap location from their NFL position, not their tracked location. All counts come from our own captures (`data/live-captures`, 14 games, 2,604 plays) and the imported nflverse objects (`data/nflverse`). Nothing was fetched.

## What each source has

| Source | When it's available | Formation and personnel | Defense | Per-player position |
| --- | --- | --- | --- | --- |
| ESPN live core plays (what the worker reads) | Live, seconds after each play | Only in the text: "(Shotgun)" on 1,028 plays, "(No Huddle, Shotgun)" 112, "(No Huddle)" 30, "(Run formation)" 3, "(Punt formation)" 3. No under-center, pistol or personnel field. Pass depth and side, run direction and gap are in the text | Nothing | No; the participants are ESPN IDs with roles |
| nflverse play-by-play | After the game is final | `shotgun`, `no_huddle`, `qb_dropback`, `pass_location`, `run_location`, `run_gap`, no more than ESPN's text | Nothing | No |
| nflverse participation (from NFL Next Gen Stats) | 2016–2025 only; **no 2026 file** | `offense_formation` (shotgun, under center, pistol) and `offense_personnel` ("1 C, 2 G, 1 QB, 1 RB, 2 T, 1 TE, 3 WR") | `defense_personnel`, `defenders_in_box`, `number_of_pass_rushers`, `defense_coverage_type` (Cover 0 to 6, 2-man), man or zone. Also the targeted receiver's `route`, time to throw and pressure | All 22 players' IDs and positions |
| FTN charting | 2026 weeks 1–7 imported (18,191 plays), a few days after games | `qb_location` (shotgun, under center, pistol), backfield count, motion, play action, screen, RPO, starting hash | Box count, pass rushers, blitzers | No |
| nflverse 2026 rosters | Any time | — | — | `position` and `depth_chart_position`: T, G, C, TE, WR, RB, FB, QB, DE, DT, NT, OLB, ILB, MLB, CB, FS, SS, K, P, LS |
| nflverse 2026 depth charts (ESPN-sourced, 268 snapshots, 2026-03-22 to 10-31) | Any time, updated through the week | Each team's base offense ("3WR 1TE") with slots LT, LG, C, RG, RT, TE, WR, RB, FB, QB | Base 3-4 or 4-3 with LDE, NT or DT, RDE, WLB, MLB or LILB and RILB, SLB, LCB, RCB, SS, FS, NB | Each player's slot and rank, plus special teams PK, P, H, LS, PR, KR |

**Coverage of the players we draw.**
- **Depth charts:** 1,003 of the 1,009 players ESPN names in the captured plays are in the 2026 depth charts by ESPN ID.
- **Depth charts or roster:** 1,008 are in one or the other.

## What it means for the animation

- **Live per-play facts:** shotgun or not, no huddle, the play's direction, gap, depth and side. Real formation, personnel and defensive alignment aren't live from any source we hold. The richest one, participation, has no 2026 file and is published after games.
- **Every player's position is available before kickoff**, matched by ESPN ID through the depth charts. That gives a general pre-snap spot for each player ESPN names, by slot:
  - left tackle at the line just left of the center
  - right cornerback wide on the defense's right, a few yards off
  - weakside linebacker on the edge
  - free safety deep in the middle
- **Example, the fumble from the owner's review (OWN-035):**
  - J.Jackson is Chicago's starting right guard. He would line up beside the center.
  - D.Lawrence is Seattle's weakside linebacker in a 3-4, rushing off the edge. He would line up on the line outside the tackle; the current code started him 18 yards deep.
  - J.Jobe is the right cornerback, and C.Loveland the tight end.
- **Limits:**
  - The depth chart is a team's base alignment, not that play's. A nickel corner, a slot receiver or a tight end split wide won't always be where the base chart puts him.
  - Wide receivers' slots don't say which side or whether in the slot.
  - The ball's hash isn't live: FTN has it after games, so the drawn ball position stays a guess.
- **Historical tendencies:** participation 2016–2025 and FTN 2026 can supply rates, such as how often a team is in shotgun with 11 personnel, or how deep safeties play on 3rd and long, to make the general alignment plausible. They can't tell us what happened on the live play.

**Outcome.** The owner chose to build it on 2026-11-04 (OWN-036). It is ENG-037; the [task record](../superpowers/plans/2026-11-04-play-alignment.md) has the evidence.
