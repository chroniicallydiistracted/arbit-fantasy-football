# First live slate receipt — Week 8, 2026-11-01

Closes R-025, the statistics question in R-026 and the measurement in R-030. Measured after PHI at WSH ended, from the worker's private captures and the play history. The worker made every read; measuring added none.

## What was watched

Four games were captured live: PHI at WSH from kickoff, and LAC at LAR, KC at DEN and NE at MIA from 21:50 UTC. The host PC slept through the nine early games, so their plays were collected afterward and say nothing about live behavior (R-029).

## Results

| Measure | Result |
| --- | --- |
| ESPN reads | 4,385 since 2026-11-01 06:23 UTC: 1,356 scoreboards, 2,380 play pages, 649 summaries |
| Read failures | 0, including no rate limits |
| Request rate | 32 in the busiest minute; 9 in the median minute with games active |
| Play delay | 616 plays from their ESPN timestamp to first stored: 20 s at the 10th percentile, **36 s median**, 55 s at the 90th, 94 s at the 99th |
| Longest delay | 3,683 s. Not investigated; it is close to the one-hour final check |
| Capture size | 79 MB on disk from 1.67 GB of responses |
| Statistics lane | First real import logged `statistics_imported` at 2026-11-01 10:00:10 UTC. Duration isn't logged. `data/nflverse` is 1.3 GB |
| Worker memory | 3.5 GB peak over 22 hours, a period that includes that import |

The 36-second median replaces an estimate of about 2 minutes from the first 20 minutes of observation (138 plays). That early sample overstated the delay, and the cause wasn't investigated.

## Corrections

| Plays shown (no-plays excluded) | Count | Gained a revision | Result or credit changed |
| --- | --- | --- | --- |
| All games | 2,298 | 1,578 (69%) | 57 (2.5%) |
| Games captured live | 689 | 662 (96%) | 55 (8%) |

A new revision usually isn't a correction. ESPN re-stamps most plays, and its first drafts settle: tacklers get added, "right end" becomes "right tackle", the clock moves a second, blanks get filled in, and a touchdown's score rises when its extra point is attached. Real corrections look like a sack going from -12 to -11 yards or a catch overturned to an incomplete pass. ENG-025 records the rule. Use the live-captured row when judging behavior, because games collected afterward never saw the first drafts.

## Real-time on a real game

New code ran against a restored copy of the real database with its own worker reading ESPN, while a browser held PHI at WSH open for 18 minutes with no reload. The page's text changed 58 times, including Washington's score going from 19 to 25 to 27, with no server or console errors. In the one change timed closely, "1st & 10" reached the page within a second of the worker's read.

The same check read all 14 real games through the new code without a failure, including 13 stored before the summary format changed. Moving one game's final check forward on the copy filled in its drives and team stats.

## Capture retention

Keep everything this season. Only four games were captured live, so a full Sunday may reach roughly three times this size, which still leaves the 5 GiB limit about 20 Sundays away. Reaching it stops capture and logs `CAPTURE_FULL`; nothing is deleted.

## Not measured

- Signed-in pages on the running app, since only the owner holds that session. The check above used the same code on a copy of the same data.
- Delay on a phone or over a network, since hosting is deferred.
- Recovery after a crash or a Windows restart (R-029).
