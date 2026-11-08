# Observed NFL play coverage · November 5, 2026

The sample is 5,881 raw v2 records in 31 games. It includes the archived 16-game Week 1 response, the 14-game Week 8 response, and a fresh final Jacksonville–Baltimore v2 response. The audit ran the NFL normalizer, the production animation builder with the game and play reads supplied from those captures, and the browser's eligibility rule. It used nflverse player IDs, depth charts and schedule plus the stored team mapping. The available sample covers 14 provider type values.

| NFL `playType` | Raw records | Text rows or folded tries | Canvas and Jumbotron eligible |
|---|---:|---:|---:|
| `PASS` | 1,909 | 1,909 | 1,895 |
| `RUSH` | 1,738 | 1,738 | 1,700 |
| `TIMEOUT` | 717 | 717 | 0 |
| `KICK_OFF` | 331 | 331 | 322 |
| `PENALTY` | 315 | 315 | 0 |
| `PUNT` | 239 | 239 | 235 |
| `XP_KICK` | 156 | 156 folded | 156 |
| `SACK` | 150 | 150 | 149 |
| `FIELD_GOAL` | 120 | 120 | 120 |
| `END_QUARTER` | 96 | 96 | 0 |
| `UNSPECIFIED` | 33 | 16 | 2 |
| `END_GAME` | 31 | 31 | 0 |
| `GAME_START` | 31 | 0 | 0 |
| `PAT2` | 15 | 15 folded | 14 |
| **Total** | **5,881** | **5,662 rows and 171 folded tries** | **4,593** |

The normalizer omits 31 game-start markers and 17 blank unspecified records. It attaches tries to their touchdowns in the readable log. The API builds the board from every retained main play, including timeouts and penalties, and generates 4,919 scripts including tries. The browser skips cancelled entries and entries without a script. That removes 326 of the generated scripts, and all 328 cancelled records in the sample are text-only in the browser. The Jumbotron is attached to every eligible clip.

## Gaps

- **67 football actions or tries lack a clip.** These include 38 rushes, 14 passes, nine kickoffs, four punts, one sack and one two-point try. Cases include missing end or landing spots, aborted or complex fumbles, direct-snap trick passes, a lateral, a blocked punt, and the two-point try after a reviewed touchdown. The Thursday sample includes Derrick Henry's direct-snap pass to Zay Flowers.
- **315 standalone penalty records are filtered from the field.** They retain their text and board data. A penalty attached to an eligible play can still show a card. The audit found 164 penalty cards on eligible clips, plus cards for touchdowns, extra points, field goals, interceptions, fumbles, turnovers on downs, missed and blocked kicks, two-point conversions, and a safety.
- **845 administrative records are text-only.** Timeout, end-of-quarter and end-of-game records plus one unspecified record have no standalone clip. The board still processes them in sequence before the next eligible play.
- The **play log** shows the latest 100 retained rows by default, with no client pagination. The API accepts a limit up to 400. No-play and correction labels are visible, and the My players filter depends on identified participants.
- The **field renderer** draws supplied scripts and board state. Each game still needs its art bundle (R-043). The game header, drive summaries, team stats, leaders and win probability use the independent game summary and remain available when a play lacks a clip.

The separate Week 8 paced-script rule check reported two existing instances of a defender waiting at a catch spot (R-044). Coverage counts describe eligibility and data handling. Visual correctness across all clips and complete coverage of future provider values remain open.
