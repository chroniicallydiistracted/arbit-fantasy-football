# Handoff · 2026-11-08 · Live motion calibration

LV-003 and LV-005 apply. The owner asked for football movement and likely formations to drive timing, for a measured field scale, and for manual render review (OWN-057). The current NFL play-by-play and roster context continue to drive the animator. The private tracking archive and all derived comparisons remain offline (OWN-053).

## Implemented

- Pass targets move from the snap through an inferred stem and break. Pass release follows depth and available timing. Flight uses horizontal yards per second. A catch can carry momentum into the run, and the ball is tucked into the chest. A credited target continues into pursuit on one actor track.
- Runs use narrower pace ranges. Credited defenders converge on the moving carrier, including shared tackles on runs and passes. First contact can precede the official spot while the carrier moves through the wrap. The original fallback also keeps moving approaches from holding at their destination before contact.
- The official goal-line event is separate from deceleration and celebration. An uncaught kickoff touchback with only a generic end-zone description can bounce and roll to rest. The return, hit, loose ball and recovery on the reviewed compound kickoff remain distinct.
- The field and actors share the 120-by-53⅓-yard coordinate system. The board uses observed play time when available. Visual follow-through can continue after the clock stops.

## Evidence

- Manually inspected sequential Chromium renders of 13 stored Jacksonville–Baltimore plays, including short and deep passes, shared contact, a legacy scramble, two touchdowns, two touchbacks and a reviewed kickoff return. The isolated browser clock advanced in 125 ms steps. Private sheets, example GIFs, survey and matched results are under ignored `data/live-motion-review-2026-11-08/`.
- Replayed 30 archived games through both versions. The new preview produced 3,341 replacement scripts. The browser preview used 110 replacement scripts among 138 non-cancelled Thursday clips. Matched holdout evidence shows improvement in receiver release and pass arrival, with first-contact timing less accurate on the available matched sample. Scoring still skews early. The archive supplied no tracked kickoff touchbacks to validate the estimated roll.
- Python pytest passed 1,250 tests. Strict mypy checked 105 source files and targeted Ruff checks passed. TypeScript and 29 Vitest tests passed. The local pnpm launcher lacked its cached binary, so OpenAPI, generated TypeScript, tokens, design, PWA and Biome ran directly. Biome reported three existing reduced-motion CSS warnings. The staged fixture browser on port 8039 passed all five replay and correction scenarios. The staged API on port 8040 passed readiness, served the staged replay and required member sign-in for animation and art.
- Activated the revised opt-in preview on the authorized local web stack under `.superpowers/releases/live-animation-motion-2026-11-08`. Port 8000 returned readiness and the served replay HTML, browser bundle and service worker matched the staged files. Animation and art continued to require a member session. Only the member API restarted. The worker retained its prior PID. Restore the prior release path `live-animation-preview-2026-11-07` in `30-live-animation-preview.conf` and reload and restart the member API to roll back.

Full play-family coverage, closer first-contact and scoring timing, directional art and live delivery measurement remain M6 gates for default activation. [Plan](../../superpowers/plans/2026-11-08-live-motion-calibration.md) · [Prior activation](2026-11-07-live-animation-preview-activation.md)
