# Task: The stadium board in the full-field view (slice 5)

Status: accepted by the owner and committed, 2026-11-05 (ENG-039, OWN-039, ENG-040, OWN-040: "The scoreboard looks phenomenal!"). The owner asked "Lets run slice 5".

- **Requirement IDs.**
  - LV-003: canonical play graphics.
  - LV-005: late, revised and cancelled plays. A board is recomputed from stored revisions, like a script.
- **Specifications and decisions.**
  - OWN-030: "a scoreboard, or jumbotron" in the scene.
  - OWN-032: only the players in the play. The board adds no players.
  - OWN-038: style C team colors on name tags.
  - Item 10 and slice 5 of the [automation plan](2026-11-03-live-play-automation.md).
  - The [design system](../../design/design-system.md) and ADR-005: officiating and broadcast character, always-dark scoreboards, colors as game signals.
- **Baseline.**
  - Each stored play revision has ESPN's period, clock and the score after the play (a touchdown's score already includes its try), with the start and end spots, downs, distances and possession.
  - Timeouts aren't stored per play. The game's `situation` has them only for the moment it was read. The plays record them as text instead:
    - 107 timeouts read "Timeout #N by CODE at M:SS." ESPN numbers them within each half: #1 50 times, #2 38 times, #3 20 times.
    - A lost challenge ends "(Timeout #N.)", with the team only named in the text before it ("Dallas challenged …").
  - The review renderer draws the full-field view at 1920 pixels and crops to the field. The space above the far sideline is dark.

## Scope

**The board's state, in the shared library** (`libs/arbit-data/src/arbit_data/live/board.py`). It is one implementation, so the review renderer now and the browser in slice 7 show the same facts. For each play it gives two states:
- **Before**, at the snap:
  - quarter and clock
  - each team's code, score and timeouts left
  - possession
  - down and distance, or kickoff, extra point or two-point try; "& GOAL" when the line to gain is the goal line
  - the ball's spot
- **After**, once the play is over: the score after it, and ESPN's end spot, down and possession.

It also gives the results shown in large type after the play:

| Result | When |
| --- | --- |
| TOUCHDOWN | Any touchdown, offense or defense |
| FIELD GOAL GOOD | Field goal good |
| NO GOOD, BLOCKED | Missed or blocked field goals and tries |
| SAFETY | A safety |
| INTERCEPTED | An interception |
| FUMBLE | A fumble the other team recovers |
| TURNOVER ON DOWNS | A fourth down that ends with the other team's ball |
| EXTRA POINT GOOD, TWO-POINT GOOD | A good try |

A turnover returned for a score shows both cards, in order.

**Score rules:**
- **Before a play:** the score after the play before it.
- **After a touchdown:** the touchdown's own points. The try that follows has its own board, ending at ESPN's score.

**Timeout rules:**
- **The count:** each half starts with 3 for each team, and overtime with 2 (the NFL's regular-season rule). ESPN's own number decides how many are used: "Timeout #2" means two.
- **A lost challenge:** charged to the team its text names, by the team's location or full name.
- **Unknown stays unknown:** if a challenge can't be matched to a team, both teams' timeouts show as unknown until the half ends. A play without a score keeps the last known score unless it's a scoring play, which shows an unknown score.

**Interpretations recorded here (ENG-039):**
- **Missed kicks get a card.** The plan names results for scoring plays and turnovers. A missed field goal or try also changes the game, and a stadium board shows "NO GOOD", so it gets a card too.
- **Team colors match the name tags.** The plan said measured uniform colors, but a measured jersey can be dark navy, unreadable on a black board. Team codes use the same style C colors as the name tags (OWN-038), so a team's color matches between its players' tags and the board.
- **The clock stays at the snap.** ESPN gives the clock at each snap, not when the play ends, and the time run off between plays isn't known. The board shows the snap clock through the play rather than inventing a running clock.

**The board in the scene**, drawn by the review renderer (`scripts/sprites/board.py`):
- **Where:** a stadium board centered above the far sideline, facing the camera.
- **How it's drawn:** in board pixels of 3 screen pixels, each lit as an LED dot, with unlit dots showing the matrix.
- **Letters:** our own 5-by-7 pixel glyphs in `assets/sprites/board/glyphs.txt`, doubled for large type. No licensed font. Team logos were added after the owner's review (OWN-039, below).
- **Colors** follow the game's signals in the design system:
  - team codes in their tag colors
  - down and distance in the yellow of the line to gain
  - the ball's spot in the blue of the line of scrimmage
  - scores and the clock in white
  - a small ball glyph marks possession
  - timeouts left are lit pips
- **When:** the board shows the before state until the whistle. Each result card then shows for 2 seconds, without flashing, and the board turns to the after state. A clip runs long enough to show every card. Cards first wiped in; after the owner's review they scroll in (OWN-039).

**The script's whistle.** The script gains `whistle`, the moment the play is over: its last movement, before the closing hold. The board and the browser's play queue both need it.

**Not in scope:**
- The browser's board, which is slice 7.
- The page scoreboard, which stays the readable, accessible source of the same facts. The board is decoration and will be hidden from screen readers in slice 7.
- Licensed fonts. (Logos were out of scope until the owner asked for them, OWN-039.)

## Files and interfaces

**Created:**
- `libs/arbit-data/src/arbit_data/live/board.py`: `PlayBoard`, `BoardState`, `BoardSide`, `BoardSpot`, `BoardResult`, and `GameBoard(teams, codes, names).boards(play, facts)`.
- `packages/contracts/schemas/play-board.schema.json` and `tests/fixtures/live/play-board.example.json`.
- `tests/fixtures/live/board-plays.example.json`: real ESPN play sequences.
- `libs/arbit-data/tests/test_board.py`.
- `assets/sprites/board/glyphs.txt`.
- `scripts/sprites/board.py`.
- `scripts/live/check_boards.py`.

**Changed:**
- `choreography.py`: `PlayScript.whistle`.
- `preview.py`: a backdrop drawn behind the field, and the crop.
- `render_script.py` and `audit_render.py`.
- Schema export and contract validation.

## Acceptance

**Tests on real plays:**
- the first play's board
- scores before and after a touchdown and its try
- timeouts from called timeouts and from a lost challenge, the reset at halftime, and the unknown challenger
- down, distance, goal to go and the spot
- the after state of a punt and a kickoff
- each result card

**`check_boards.py` over every captured game:**
- Each game's last board equals ESPN's final score.
- Scores never go down.
- Timeouts stay from 0 to 3.
- Where a captured scoreboard's `situation` names the play just finished, its timeouts equal the board's.

**The renderer audit** checks that every glyph a board needs exists and that each board's text fits its cell.

**Evidence:** the CHI at SEA game rendered with the board, for the owner's review.

## Migration, rollback, data

None. Boards are computed from stored revisions. The running app is unchanged until slice 7.

## Evidence and outcome

**Built as planned** (ENG-039):
- **Facts:** `board.py` in the shared library, with its contract and example. The script gains `whistle`.
- **Drawing:** the glyphs, `scripts/sprites/board.py`, the renderer's backdrop and crop, and the board in every review clip.
- **Checks:** `check_boards.py`, and the board checks in the renderer audit.
- **Fixture:** `export_board_fixtures.py` writes three whole real games (571 plays, 243 kB): CHI at SEA, ARI at DAL with overtime and a lost challenge, and IND at JAX with an interception returned for a touchdown.

**Checking against ESPN's scoreboard found and fixed:**
- **A score that went down.** ESPN puts a try's points on its touchdown, then recorded a delay of game on BUF's try with the score before the kick. A play that scores nothing no longer lowers a score.
- **A name both teams share.** Both Los Angeles teams have the location "Los Angeles", so a challenge naming only that would have been charged to whichever team came last. It now names neither, and the timeouts show as unknown.

It also showed that the first scoreboard reads after a play can still show the timeouts and score from before it, so the check compares each play with the last read that names it.

**`uv run python scripts/live/check_boards.py`** over all 14 captured games:

| Compared with ESPN's scoreboard | Count | Board differs |
| --- | --- | --- |
| Final score | 14 | 0 |
| Score after a play | 691 | 0 |
| Timeouts after a play | 691 | 0 |
| Down and distance | 641 | 0 |
| Possession | 602 | 0 |

23 reads where ESPN disagrees with itself are reported separately:
- 17 where its play record and its scoreboard give a different down and distance, as when it re-spots the ball a yard after the play
- 1 where they give a different possession
- 5 where its score is a play out of step with its own "last play"

In each the board shows ESPN's play record, or the score one play away.

| Check | Result |
| --- | --- |
| `test_board.py` | 24 tests on the three real games, 36 after the owner's review |
| `test_choreography.py` whistle rule | 34 fixture plays |
| `audit_render.py` | 2,254 scripts and 2,676 boards, 0 problems |
| `check_play_scripts.py` | 0 broken rules |
| `uv run pytest -q` | 1,143 passed, 1,155 after the owner's review |
| Ruff, format, mypy, `pnpm check:contracts` (5 examples), `pnpm check:client`, `make check` | Passed |

**Looked at by eye:**
- **The field goal:** "4TH & 4" and "BALL ON SEA 25" at the snap, the "FIELD GOAL GOOD" card for CHI wiping in, then 10–3 with the bottom row clear.
- **The first touchdown:** "2ND & GOAL" at the SEA 1, then "TOUCHDOWN" for CHI, then 6–0 with "EXTRA POINT".
- **Its try:** "EXTRA POINT GOOD", then 7–0.
- **The interception:** Chicago's ball, 1st & goal at the SEA 6, as the return in ESPN's text ends.

**Renders:** `render_script.py --board` writes the 19 comparison plays to `data/sprites/review/board/`, and the whole game was re-rendered with the board.

**Limitations:**
- **The clock** holds the snap's time through the play.
- **Timeouts** depend on ESPN's text numbering them, which it did on all 108 timeouts and 4 challenges captured.
- **Overtime timeouts** use the regular-season rule.
- **The browser's board** is slice 7.

## Owner review (OWN-039) and changes (ENG-040)

**The owner's review:** "It looks really good!" They asked for:
- **Scrolling:** results scroll in from the side of the team they are for, instead of wiping in.
- **Colors:** good results green, bad ones red, penalties yellow.
- **Flags on the board:** each penalty shows the foul, the team and the player's jersey number.
- **Team logos:** each team's logo in the same LED style, on its side, outside its score.

They are also building a route from the NFL API into an nflreadr pipeline that gives each play's start and end clock, enough to run the clock during a render.

**Built:**
- **Scroll.** A card enters from the away team's side (left) or the home team's (right), easing to a stop in 0.6 seconds. Each step is a whole LED column, as a real board moves.
- **Colors.** `BoardResult.tone` is set in the library, using the design system's dark-mode signals:

  | Tone | Color | Results |
  | --- | --- | --- |
  | `good` | `gain` green | touchdown, field goal, extra point, two-point try, safety |
  | `bad` | `challenge` red | interception, lost fumble, turnover on downs, no good, blocked |
  | `flag` | `flag` yellow | penalty |

  A safety is a score, so it's green.
- **Penalty cards.**
  - **What it shows:** ESPN's name for the foul in large type, on two lines when it needs them ("DEFENSIVE PASS" / "INTERFERENCE"). Below is the team in its color, the player's number in white, and DECLINED or OFFSETTING dimmer.
  - **Order:** cards come after the play's own result.
  - **Finding the number.** nflverse's weekly roster has jersey numbers, but many players have no ESPN ID in it, Jonah Jackson among them. So the number is looked up on the flagged team's roster for the game's week: first by the ESPN ID ESPN names the player by, then by the text's name. ESPN writes "Ja.Williams" for Jaylon Williams, so a name matches a roster player whose first name starts with the text's letters and whose last name ends with its last name. By name, exactly one player matched for 214 of the 215 named fouls in the captures, and none was ambiguous.
  - **Without a number:** a team foul such as delay of game has none, and neither does a player missing from his team's roster that week.
- **Logos.**
  - **Source and storage:** `scripts/sprites/fetch_logos.py` read all 32 teams' ESPN logos, in the light and dark-background versions, from the addresses in nflverse's teams table. They are stored with a manifest in the ignored `data/logos/espn/` and never committed: logos are the teams' trademarks, kept like the Gridiron art.
  - **On the board:** each is the dark-background logo drawn as 30 by 30 LED dots in six flat colors at its team's outer edge. The board grew from 232 to 256 board pixels to fit them. Without the files it draws without logos.
- **Clock.** `GameBoard.boards(play, facts, clock_end=)` puts the end-of-play clock on the after state. When it differs from the snap's, the renderer runs the clock down from the snap and lands on it at the whistle; without it, the clock holds. It is ready for the owner's feed. Until then no captured source has the end clock, so it was checked with a made-up end time: 5:25 at the snap, 5:19 at the whistle.

**Evidence:**

| Check | Result |
| --- | --- |
| `check_boards.py` | 0 problems; all earlier comparisons unchanged. Penalty cards: 214 numbered, 11 team fouls, 1 player not on his team's roster that week (T.Woolen, PHI) |
| `audit_render.py` | 2,254 scripts and 2,676 boards, 0 problems: every foul name fits in two large lines, every glyph exists (a "#" was added), every team in the captures has a logo |
| `test_board.py` | 36 tests. New ones: the tone of every result in three real games, every named foul's number on that player's own team, Jonah Jackson found by name, team fouls without a number, declined fouls, flags after the play's result, and the end-of-play clock |
| `uv run pytest -q` | 1,155 passed |
| Ruff, format, mypy, `pnpm check:contracts`, `pnpm check:client`, `check_play_scripts.py` | Passed, 0 broken rules |

**Looked at by eye:**
- **Chicago's touchdown and pass interference:** green "TOUCHDOWN" and yellow "DEFENSIVE PASS / INTERFERENCE" scroll in from the left.
- **Seattle's touchdown and offensive interference:** both scroll in from the right, the interference with "SEA #11".
- **The false start:** "FALSE START" with "CHI #73". Then 1st & 15.
- **The logos:** the Bears and Seahawks read at their outer edges.

