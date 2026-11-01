# Gridiron URL patterns and week 8 assets — 2026-10-31

Requested by the owner (OWN-019) under their private permission, personal use only (OWN-015). Images stay in the ignored `data/gridiron/` directory and may be served only inside the invite-only application. They never enter Git, the public shell or the service worker.

**Result:** the patterns are known and the art for all 14 week 8 games is on disk: 54 files, 10.6 MB, each with a receipt in `data/gridiron/2026/week-08/manifest.json` (URL, time, bytes, SHA-256, dimensions). Requests were sequential with a two-second wait. `robots.txt` only sets a crawl delay for msnbot.

## URL patterns

Read filenames from the site's pages. They cannot be built from a team and week alone: 3 of 270 uniform links end in `.PNG`, and a field's filename contains a year range (`DAL_2017-2026^1`) that its title (`DAL_2026^1`) doesn't. Eleven guessed sizes and folders for field images all returned 404.

| What | Pattern | Notes |
| --- | --- | --- |
| Week index | `https://gridiron-uniforms.com/GUD/controller/controller.php?action=weekly&year={Y}&week={W}&league=NFL` | `week=pre` also exists. One block per game. This is the source of truth for the mapping |
| Game ID | `{Y}_{AWAY}-{HOME}^{W}` | For example `2026_ARZ-DAL^8` |
| Game pages | `action=single-weekly&game_id={ID}`, `action=high-res-weekly&game_id={ID}` | Same controller |
| Uniform image | `/GUD/images/singles/{size}/{Y}_{TEAM}_{CODE}.{png or PNG}` | Size `th/` 134×168, no folder 400×500, `hr/` 1280×1600. `CODE` is the uniform (`A`, `C2`); `1TBA` means not announced |
| Field index | `https://www.gridiron-uniforms.com/fields/controller/controller.php?action=view-year-all&year={Y}` | 71 variants for 2026. `action=view-team-all&team_id=DAL&city=Dallas&name=Cowboys` lists one team |
| Regular-season field | `https://www.gridiron-uniforms.com/fields/images/regular-season/{TEAM}/{r235 or r1024}/{TEAM}_{YEARS}^{VARIANT}.png` | 1024×486 is the largest size linked |
| International field | `.../fields/images/international-series/{Y}/r1024/INT_{Y}^{N}.png` | The home team's own field does not apply |
| Playoff field | `.../fields/images/playoffs/{Y}/r1024/{TEAM}_{Y}^{ROUND}.png` | Rounds such as `conf`, `div`, `wc` |

Traps: the site uses `ARZ` where ESPN uses `ARI`; the other 31 codes joined all 14 games to ESPN event IDs. Links on the pages use `http://`, but `https://www` serves the same files. Encode `^` as `%5E`.

## When art is published

| Week | Games | Field listed | Uniform marked TBA |
| --- | --- | --- | --- |
| 1–7 (played) | 107 | 107 | 0 |
| 8 (mostly upcoming) | 14 | 3 | 2 |
| 9 (next) | 15 | 1 | 10 |

**Uniforms are mostly announced in advance. Fields are mostly listed after the game.** A guess doesn't solve this: across weeks 1–7 and all 32 teams, the last field a team used was its next home field in only 34 of 69 cases (49%). Variants of one team's field differ by 0% to 14.6% of pixels, so some mistakes would be invisible and others obvious. International games use a different field.

So each game needs a status: `listed` (posted by the site for this game), `candidate` (the home team's field, variant unconfirmed) or `not_announced`. A sync lane must recheck, because TBA uniforms and fields resolve later, and a game's art can be replaced until the page settles.

## What the art is

**Uniform sheets** are 1280×1600, opaque white background, flat illustrated. Each holds helmet left and right, jersey front and back, pants front and back, lower legs and cleats. They are drawn on one template. Measured across all 28 sheets, as the share of the common outline each sheet covers within 2 px:

| Region | Lowest | Median |
| --- | --- | --- |
| Helmets | 99.8% | 100% |
| Pants, lower legs, cleats | 99.8% | 100% |
| Jersey front | 86.2% (GB) | 100% |
| Jersey back | 84.2% (GB) | 100% |

Fixed-position cutting is therefore viable, with per-team checks on jerseys. Three limits: every jersey is numbered 11 and says NAME, so real numbers must be painted over them; a TBA sheet has the word stamped on it and can't be displayed as real; some teams have extra sock panels in the gutter. Colors sampled from fixed positions looked right by eye on the five sheets tried, not all 28. The background is white too, so white gear needs the outline to separate it from the background.

**Field sheets** are 1024×486, flat top-down. All 26 fetched have identical geometry: goal lines at x=107–108 and 915–916, sidelines at y=27 and y=458, about 8.07 px per yard, so one calibration fits all. That is sharp enough for a whole-field view and far too soft for a broadcast camera, where 40 yards across a 1080p screen needs about 48 px per yard. Lines and numbers must be redrawn procedurally, with logos and end-zone art rebuilt at higher resolution from the sheet.

## Week 8 on disk

All 28 uniforms are stored, along with every 2026 variant for home teams with no listed field.

| Game | ESPN event | Uniforms | Field |
| --- | --- | --- | --- |
| CAR at GB (played) | 401873023 | CAR `A`, GB `C` | Listed: `GB_2025-2026^2` |
| ARZ at DAL | 401873024 | ARZ `E`, DAL `A` | Listed: `DAL_2017-2026^1` |
| TEN at CIN | 401873031 | TEN `B2`, CIN `F` | Listed: `CIN_2024-2026^1` |
| ATL at TB | 401873025 | ATL `C2`, TB `A` | 2 candidates |
| BAL at BUF | 401873026 | BAL `C`, BUF `D` | 1 candidate |
| CLE at PIT | 401873027 | CLE `C`, PIT `D` | 1 candidate |
| IND at JAX | 401873028 | IND `C`, JAX `L` | 2 candidates |
| LV at NYJ | 401873029 | LV `A`, NYJ `D` | 3 candidates |
| MIN at DET | 401873030 | MIN `E`, DET `I` | 2 candidates |
| LAC at LAR | 401873032 | LAC `A`, LAR `D` | 3 candidates |
| KC at DEN | 401873033 | **KC TBA**, DEN `D` | 3 candidates |
| NE at MIA | 401873034 | NE `E`, MIA `A2` | 2 candidates |
| PHI at WSH | 401873035 | PHI `B`, WSH `F` | 1 candidate |
| CHI at SEA | 401873036 | **CHI TBA**, SEA `E` | 3 candidates |

## Not done or not verified

`config/gridiron-assets.json` is still empty, and nothing in the application reads these files yet. No sync lane exists, so this fetch goes stale as the site updates. The published art was not compared with what teams actually wore. A larger field source may exist under a route not linked from these pages; none was found.
