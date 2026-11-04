# Next Gen Stats highlight tracking — 2026-11-03

The owner asked whether nflverse holds Next Gen Stats (NGS) tracking with player positions. If it doesn't, the alternative is to collect NGS highlight plays through the URL structure the NGS site itself uses. They saved one play's site files and network responses to ignored `data/nfl_ngs_scrub`. This note records what those files contain, what nflverse contains, and the terms that apply. The captured data stays in `data/`. This repository is public, so no tracking values are copied here.

## nflverse has no positions

The 28 nflverse dataset families we import (SRC-21) were checked:
- **`nextgen_stats`.** The three tables, `ngs_passing`, `ngs_rushing` and `ngs_receiving`, are weekly per-player averages: time to throw, completion over expected, separation, cushion and rushing yards over expected. They hold no coordinates.
- **`pbp_participation`.** It lists who was on the field and their personnel, with no positions. It has no 2026 file and is published after the season.
- **`ftn_charting`.** This is the richest per-play source: hash, quarterback alignment, number of backs, defenders in the box, pass rushers, blitzers, motion, play action, screen and RPO. It covers 2026 weeks 1–7, a few days after each game.

## What the NGS site serves

The play the owner saved is CHI at SEA on 2026-11-02, NGS game `2026110200`, play `3824`: D.Swift's 5-yard touchdown run. NGS `playId` matches the sequence number in ESPN's play ID (`401873036` + `3824`), so NGS plays join ESPN's stored plays directly.

| Route (`nextgenstats.nfl.com/api/…`) | What it returned |
| --- | --- |
| `highlights/tracking/game/play/withBall/min?gameId=&playId=` | All 22 players by name, position and number, each with 287 samples of `time`, `x`, `y` at 10 per second. That runs from the offensive huddle to after the whistle, 28.7 seconds. The ball has 66 samples of `x`, `y`, from just before the snap to just after the touchdown, with **no height**. Players have no speed, direction or facing in this `min` form. Events with times: huddle start and break, line set, ball snap, handoff, first contact, touchdown, play submitted. A health flag marks player and ball tracking as OK |
| `highlights/participation/game/play?gameId=&playId=` | Each player's role on the play, such as defender location, ball carrier, lined up at quarterback and ran a route, plus timeouts left and the play's situation |
| `plays/isHighlight?gameId=&playId=` | Whether a play is a highlight |
| `plays/highlights?limit=&season=` | Paged list of highlight plays: **1,568** so far in 2026, each with its play facts |
| `league/schedule`, `league/teams`, `league/schedule/current` | Schedule and team reference |

**Coverage.** Only plays marked as highlights have tracking. CHI at SEA has 9 highlights among its 159 football plays. Two of the 9 are plays we already re-create by hand: J.Smith-Njigba's 43-yard touchdown catch (`1939`) and the sack (`2316`). Whether non-highlight plays return tracking wasn't tested: it would take a request to the site, and the terms below come first. How soon a highlight appears after the play is also unknown.

**What it would and wouldn't give the animation.** For a highlight, the tracking would give every player's real path and the ball's ground track, timed to the snap, so the re-creation label could become "Tracked positions". It wouldn't give the ball's height or arc, any player's facing or pose, or anything at all for about 17 plays in 18. So the choreographer stays the default, and tracking would replace it only for highlights.

## Terms

- `nextgenstats.nfl.com/robots.txt` allows every path.
- The site's footer links to NFL's Terms of Service (`nfl.com/help/terms`, which redirects to `nfl.com/legal/terms`). Section 1.3 allows use "solely for your own individual non-commercial and informational purposes".
- The same section also says: "Systematic retrieval of data or other content from the Services, whether to create or compile, directly or indirectly, a collection, compilation, database, or directory, is prohibited absent our express prior written consent."
- A worker lane that fetches highlight tracking and stores it is that kind of systematic retrieval into a database, whatever the purpose. Using it is the owner's decision (Q-011). **Decision 2026-11-03: skipped for now, maybe revisited later (OWN-032).** Nothing fetches from NGS, and the owner's saved files stay in `data/`.

Sources: the owner's capture in `data/nfl_ngs_scrub` (read only, never executed), the stored nflverse files, [NFL Terms of Service](https://www.nfl.com/legal/terms), `https://nextgenstats.nfl.com/robots.txt` (fetched 2026-11-03).
