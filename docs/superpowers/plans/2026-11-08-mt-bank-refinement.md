# M&T Bank geometry refinement implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the scoped refinement. Preserve concurrent choreography/render work.

**Goal:** Bring the M&T Bank model closer to the supplied centered-seat reference before expanding to other stadiums, as the owner confirmed on November 8.

**Architecture:** Keep the existing private reference camera and venue measurements. Correct the actual 3D seating/structure geometry and render a repeatable comparison with the reference, plus both the existing live crop and a whole-building study. No live asset publication or camera-contract change.

**Tech Stack:** Existing Python, NumPy, Pillow software renderer; no new dependencies.

**Spec:** [Venue handoff](../../project/handoffs/2026-11-08-stadium-venues.md), ENG-048 and LV-003. The owner explicitly confirmed “Perfect M&T Bank first, then expand.” This preserves that review gate for the remaining venues.

## Constraints and review focus

- Preserve the shared dirty working tree; do not commit other contributors' files or modify choreography, live client, or atlas build code.
- Reference pixels and measured geometry remain in ignored data/. New reusable rendering helpers and synthetic tests may be tracked.
- Do not disguise unresolved likeness with recolored generic bowls. Check straight tier edges, actual corner openings, suite proportions and end boards in the reference camera.
- Preserve the exact field projection in the live-camera study. A taller review image is not an approved change to the application's framing.
- Missing references must remain an explicit local prerequisite, not silently generate an allegedly accurate venue.

## Tasks

- [x] Diagnose and record projected tier/structure mismatches against the reference; save the pre-edit study in /tmp/arbit-stadium-baseline.
- [x] Correct private data/stadiums/mt-bank/model.py and measurements as needed. Add reusable geometry helpers in scripts/sprites/venue3d.py only where justified, covered by synthetic tests in tests/contracts/test_venue3d.py.
- [x] Improve repeatable review tooling so the reference comparison includes a regulation-size field and clear views of the relevant structures. Generate new private outputs without replacing published game bundles.
- [x] Validate focused rendering/geometry regressions, existing stadium contracts and foundation documents. Inspect comparison and live-camera outputs visually.
- [x] Obtain one independent review of this task's actual diff, resolve substantive findings, and record the precise achieved scope and remaining visual acceptance in status/changelog/handoff.

## Validation and rollback

Run `uv run --offline pytest -q tests/contracts/test_venue3d.py tests/contracts/test_stadium.py`, targeted Ruff checks, and `python3 scripts/validate_foundation.py`. Reproduce images with the private review script recorded in the handoff. Restore only task-owned changes from the initial snapshot if necessary. No database, provider, worker, deployment or API contract change.

## Execution ledger

- Initial inspection: previous work already has all-venue band recoloring and an unintegrated M&T Bank model. The current model has obvious reference mismatches; earlier claims of aligned geometry are not taken as acceptance.
- Ruling: refine within the existing workspace and private study, with an explicit baseline copy. A clean checkout would omit the untracked renderer and private inputs needed here. No git commit is part of this slice.

- Implemented the scoped private refinement and regenerated reference/current/taller views; no application integration or release claimed.
- Review finding fixed: measurement regeneration now retains both corner lamp faces exactly.
- Review finding fixed: crossed rails rejected; regression observed failing before the fix. Focused suite: 15 passed.
- Private review confirms 509,969 field pixels unchanged per lighting mode. Foundation and focused Ruff checks pass.
- Ruling: keep the inherited camera and current Live crop; the taller frame is review-only until the owner chooses framing. Cost if unchanged: upper deck/lights remain outside the running view.
- Remaining visual limits: reference lighting, foreground details, inferred end depths and inherited 26.04 px corner-fit error. These require owner likeness review before expansion; see the dated handoff.

## Follow-up: right field-wall player tunnel

The owner identified the cutout as the players' tunnel and confirmed it has no seating. This continues LV-003 and ENG-048. The seating map's narrow break between sections 115 and 117 is a location cue. Its width does not describe the tunnel opening.

- Record the tunnel footprint estimate in the private measurement generator and its generated study.
- Trim the neighboring lower-bowl surfaces and wall to the tunnel clearance in the private model. Add a concrete approach and a recessed, dark passage.
- Rebuild the private camera previews. Check the opening from the reference and Live cameras, confirm the field-pixel proof, and record the inferred dimensions in the handoff.

### Owner clarification on the two right-wall cutouts

The farther cutout is the player tunnel. Keep the lower opening and move the recessed tunnel structure to the break between sections 109 and 111. Verify both openings are clear of seating and the farther one appears in the Live frame.
