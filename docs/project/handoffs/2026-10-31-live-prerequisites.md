# Handoff — 2026-10-31 — Live prerequisites

## Current state

Branch `claude/platform-reset`, local commits only. The app on `:8000` and the worker run as user services from the [platform reset](2026-10-31-platform-reset.md). This session changed no application code and did not touch the running services.

The owner accepted the design (OWN-018) and moved Live ahead of M3 (OWN-019), asking for prerequisites first and rejecting basic or stepped animation.

## Completed work

- [Gridiron URL patterns](../../research/gridiron-url-patterns-2026-10-31.md): patterns, publication timing and art measurements.
- Week 8 art for all 14 games in ignored `data/gridiron/2026/week-08/`: 54 files with receipts in `manifest.json`, personal use only.
- [Prerequisites](../../research/live-animation-prerequisites-2026-10-31.md): 19 items, the re-creation limit, a quality bar, a single-play review gate and an order.
- Decisions and risks recorded: OWN-018, OWN-019, R-028 closed, R-005 revised, R-030 and R-031 added. UX-005 is verified.

## Verification

`python3 scripts/validate_foundation.py` passed. Findings are measurements of real files and pages, cited in the two research documents. One game's plays is thin evidence for the coverage rates.

**Not verified:** Mixamo's football clips and current terms; the CGTrader model's helmet, pads and license; three.js's official WebGPU status; the live `situation` block; performance on any real device.

## Owner inputs needed

1. Before 2026-11-01 18:00 UTC: approve the raw live sampler and one worker restart (R-030).
2. Allow a labeled full re-creation in place of the spec's dashed schematic.
3. Player model and motion clips: budget and an Adobe account, or another route.
4. Which phones and computers must run this smoothly.

## Resume here

1. If approved before kickoff, add the sampler, keeping only responses the worker already fetches, and restart the worker.
2. After the slate, read the logs, record latency and correction evidence, and close R-025 and the statistics question in R-026.
3. Build scoreboards, then the Gridiron sync lane and private delivery, then the single-play slice for owner review. Refetch KC and CHI uniforms and newly listed fields before using them.
