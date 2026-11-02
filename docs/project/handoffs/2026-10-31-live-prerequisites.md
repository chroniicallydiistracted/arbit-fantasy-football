# Handoff — 2026-10-31 — Live prerequisites

## Current state

Branch `claude/platform-reset`, local commits only. The app on `:8000` and the worker run as user services from the [platform reset](2026-10-31-platform-reset.md). The owner then approved live capture and one worker restart (OWN-020), which ran at 2026-11-01 06:23 UTC. The API was not restarted.

The owner accepted the design (OWN-018) and moved Live ahead of M3 (OWN-019), asking for prerequisites first and rejecting basic or stepped animation.

## Completed work

- [Gridiron URL patterns](../../research/gridiron-url-patterns-2026-10-31.md): patterns, publication timing and art measurements.
- Week 8 art for all 14 games in ignored `data/gridiron/2026/week-08/`: 54 files with receipts in `manifest.json`, personal use only.
- [Prerequisites](../../research/live-animation-prerequisites-2026-10-31.md): 19 items, the re-creation limit, a quality bar, a single-play review gate and an order.
- Raw live capture in `libs/arbit-data/src/arbit_data/live/capture.py`, on by default in the worker's live lane ([operations](../../engineering/supplemental-live-sources.md#raw-live-capture)).
- Owner scoped animation to the players ESPN names and the ball (OWN-021). Spec documents updated; the permanent label is ENG-023.
- Decisions and risks recorded: OWN-018, OWN-019, R-028 closed, R-005 revised, R-030 and R-031 added. UX-005 is verified.

## Verification

`make runtime-check` passed: 553 backend tests, Ruff, mypy, contracts and the foundation validator. After the restart, the worker logged all three lanes started and no failures, the first scoreboard was stored and its hash checked, permissions are owner-only, and `/health/ready` returned 200 with the API process unchanged. Findings are measurements of real files and pages, cited in the two research documents. One game's plays is thin evidence for the coverage rates.

**Not verified:** capture during a live game (synthetic tests cover scoreboard, plays and summary reads; the real run starts at kickoff) and capture size per Sunday; Mixamo's football clips and current terms; the CGTrader model's helmet, pads and license; three.js's official WebGPU status; the live `situation` block; performance on any real device.

## Owner inputs needed

None. The owner approved the scoreboard upgrade, which ran 2026-11-01 21:25 (UTC−7) after PHI at WSH ended, offline about 5 seconds with a backup taken. Signed-in pages on the running app are the owner's to confirm, since only they hold that session.

The GitHub repository is public. Only `claude/sprite-art` is pushed from this work: the sprite art alone (OWN-024). `claude/platform-reset` stays local until the owner asks. Review renders in `data/sprites/` include Gridiron field art, so they stay ignored (OWN-015).

## Resume here

1. Done: the [first slate](../../research/live-slate-receipt-2026-11-01.md) is measured, and R-025, R-026 and R-030 are closed. Check that drives and team stats appeared on Sunday's finals after their 12-hour checks (R-032), and watch CHI at SEA on 2026-11-03 01:15 UTC as the first live game on the running app.
2. Build the Gridiron sync lane and private delivery, then recoloring to real uniforms and the app's play renderer, using `assets/sprites`. Scoreboard follow-ups: player box scores, scoring plays and injuries. The full frame set is drawn ([status](../../research/live-animation-prerequisites-2026-10-31.md#sprite-direction--owner-decision-2026-11-01)), so only the weakest frames and missing poses remain. Refetch KC and CHI uniforms and newly listed fields before using them.
