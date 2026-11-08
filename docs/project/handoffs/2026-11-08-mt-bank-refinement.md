# Handoff — 2026-11-08 — M&T Bank geometry refinement

## State and owner direction

**Private model refinement implemented and checked; visual acceptance and Live integration remain open.** The owner reaffirmed “Perfect M&T Bank first, then expand” in this session. This continues ENG-048 and LV-003. Do not treat the earlier 32 recolored bowls as accepted stadium likenesses.

The choreography/render refactor is concurrent in this shared working tree. This task did not edit `live_art.py`, `preview.py`, the Live client, choreography, contracts or published art. Their existing dirty changes are not this task's work. No commit, deployment, service restart or published-art pointer change occurred.

## What changed

- `scripts/sprites/venue3d.py`: added `seating_section(mesh, front, back, part, tier)`, using measured front/back rails rather than independently normalized radial heights. It rejects malformed, nonfinite, zero-depth and crossed sections. Added an unlit tunnel material and individual seat detail.
- `tests/contracts/test_venue3d.py`: five synthetic cases covering shared rails, invalid geometry and dark tunnel entrances. No private reference is a CI input.
- Private `data/stadiums/mt-bank/model.py`: replaced schematic upper-corner wedges with three separate measured decks; leveled the lower tier's back edge; recalibrated lower and club heights; replaced offset suite boxes with continuous facades; added raised portal structures; removed overlapping skirt/fascia surfaces; corrected corner light faces. The model has 8,809 triangles in the reference review.
- Private `study.py` / `study.json`: corner lamp traces now reproduce from the measurement generator, fixing the independent review finding that regeneration erased them.
- Private `render_ref.py`: regulation field markings make projection visible in the comparison.
- Private `render_live.py`: predominantly purple/neutral-dark crowd, with gold as an accent. The source palette repeats gold in positions 2 and 3; those are not a verified black kit color.
- Private `review.py`: repeatable comparison, current/taller Live-camera previews and a hashed input/verification receipt.

References and measurements remain private under `data/`, consistent with ENG-048. No source-image texture is used on the stadium model. Source pixels appear only in the explicitly labeled comparison panel.

## Review artifacts

Under `data/stadiums/review/mt-bank-refinement/`:

- `reference-comparison.png`: supplied view above the new model, matching camera and matching crop (source rows 0–1040 of 1440).
- `before-after.png`: previous model above refined model. The baseline existed at half resolution and was enlarged before composing this comparison.
- `whole-stadium-day.png`, `whole-stadium-night.png`: review-only taller frame, rows −180 through 799.
- `current-frame-day.png`, `current-frame-night.png`: existing frame, rows 183 through 799.
- `receipt.json`: input hashes, camera/crop information, explicit limitations and field-preservation counts.

The omitted bottom of the reference comparison contains the camera-side foreground seating/apron, which remains unfinished and is outside the Live camera's visible stadium. The complete unmodified reference and full model image remain available in their original directories.

Reproduce from the repository root:

```sh
uv run --offline python data/stadiums/mt-bank/study.py
uv run --offline python data/stadiums/mt-bank/review.py
```

`review.py` requires the existing private reference pack, calibration, local team-color inputs and Baltimore field asset. It fails if those are unavailable; it does not fetch or publish assets. It uses the installed DejaVu Sans font for review labels.

## Actual validation

- `uv run --offline pytest -q tests/contracts/test_venue3d.py tests/contracts/test_stadium.py` — **15 passed**, exit 0.
- New seating tests first failed with the missing helper. The review's crossed-rail regression failed with “DID NOT RAISE” before the convexity check; both now pass.
- `uv run --offline ruff check scripts/sprites/venue3d.py tests/contracts/test_venue3d.py` — passed, exit 0.
- `uv run --offline ruff format --check tests/contracts/test_venue3d.py` — passed, exit 0.
- `uv run --offline python data/stadiums/mt-bank/review.py` — passed, exit 0; **509,969 field-interior pixels** identical to the existing camera's field projection in each lighting mode. Current-frame images also exactly equal the corresponding crops of the taller previews.
- Measurement reproduction check: rerunning `study.py` reproduced both `end_light_faces` exactly.
- `python3 scripts/validate_foundation.py` — passed, exit 0 after documentation updates.
- Independent reviewer compared this task with `/tmp/arbit-stadium-baseline`, found the lost corner-light regeneration and crossed-rail issue, and independently confirmed unchanged field pixels. Both findings were fixed. The reviewer also identified visual gaps; corner recesses and suite density were further reduced, while the limitations below remain explicit.

No application build or browser suite was run: this slice changes offline review tooling, not the installed application. The owner's running app was not used for a build or test.

The standard command runner could not start because the host lacks `bwrap`; authorized host execution was used for local file inspection and checks. No automatic approval review rejected an action.

## Remaining work and next gate

**M6 venue likeness remains open.** This is closer to the reference, not an identical reconstruction or a completed all-stadium feature.

1. Owner reviews the M&T Bank structure before the other venues are rebuilt, per their explicit direction.
2. Decide the Live framing: the current fixed crop removes most of the distinguishing upper deck and the lights. The taller study adds 363 rows above the existing frame while preserving field coordinates. No client/camera contract was changed here; coordinate any integration with the concurrent renderer refactor.
3. Reference lighting/shadows, foreground seating/apron, full portal/rail details, and exact seat-by-seat geometry remain unmatched. End-deck depths are inferred from one view. The inherited reference-camera corner fit still has 26.04 px RMS error at 2560×1440; do not claim survey-grade alignment.
4. After likeness/framing acceptance, integrate the model through the venue-selected art build, verify a staged authenticated game, and then expand to other domestic venues. International/neutral sites retain the documented generic fallback.
5. Publishing remains separate from local preparation; follow the existing game-window and approval requirements.

## Recovery

The pre-edit renderer and complete private M&T study were copied to `/tmp/arbit-stadium-baseline/`. Restore only task-owned files if needed; never reset the shared dirty tree. The durable record is this handoff and the private hashed receipt; `/tmp` is only a temporary recovery aid.

[Plan](../../superpowers/plans/2026-11-08-mt-bank-refinement.md) · [Earlier venue handoff](2026-11-08-stadium-venues.md)

## Owner follow-up, 2026-11-08

The owner clarified that the farther of two right field-wall cutouts is the players' tunnel. The initial follow-up had placed the tunnel in the lower cutout. The seating map puts the farther opening between sections 109 and 111 and the lower one between 115 and 117.

The model reserves both openings before generating seating faces and walls. The farther opening has a concrete approach, a recessed portal and a dark interior. The lower one remains a separate open recess. Both footprints follow the seating map, with widths and depths estimated from the supplied view. The farther player tunnel appears in both the reference and current Live cameras.

- The clearance check projected lower-bowl triangles onto each opening's footprint. It found 8 intersections in the farther opening and 10 in the lower opening in the original model. The revised model has zero in either.
- Rasterization showed 951 pixels of the farther tunnel's interior in the reference view and 1,031 in the current Live frame.
- `uv run --offline python data/stadiums/mt-bank/study.py` reproduced both cutout estimates. `uv run --offline python data/stadiums/mt-bank/review.py` rebuilt the previews, including `player-tunnel-detail.png`, and matched all 509,969 field pixels per lighting mode.
- `uv run --offline pytest -q tests/contracts/test_venue3d.py tests/contracts/test_stadium.py` passed all 15 tests.
- `python3 scripts/validate_foundation.py` and `git diff --check` passed.

This correction is part of the M&T Bank review before expansion to other venues.
