# Live Game Animation Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the M6 choreographer and browser renderer so live play-by-play produces accurate football events and plausible game-speed motion.

**Architecture:** Normalize evidence before resolving ordered actions, then fit a versioned timeline of shared landmarks, actor motion and ball state. The existing member API negotiates a script version during isolated development. The browser and private review use the same scene evaluator and timebase.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, React, TypeScript, Canvas 2D, existing atlas tooling, pytest, Vitest and Chromium.

**Spec:** [Live Game animation rebuild design](../specs/2026-11-07-live-animation-rebuild-design.md).

**Requirements:** LV-003 and LV-005 directly. Preserve LV-001, LV-002 and LV-004 at the game state, play feed, identity and private art boundaries.

## Global constraints

- NFL detail is primary. ESPN is the emergency fallback. Live requests build from available current PBP, with no NGS dependency.
- Private NGS research calibrates authored football rules offline. Capture-specific paths, fitted artifacts and derived tables stay in ignored data.
- Preserve current art character, cast scope, keyboard controls, reduced motion and the re-creation label.
- Use one actor per identity. Phase roles are credited or supported by play evidence. No name-specific exceptions or rule assigning every target to tackle the interceptor.
- Independently preserve observed duration, clock, official outcome and generated motion. Maintain natural movement and explicit partial/text fallbacks.
- Build on the current working tree, which contains the prior unreleased slices. Keep code and build checks isolated from the running app. Activate only after family coverage and owner review.

## Review focus

- Prior NFL payloads retain raw stats but have no typed motion evidence. Reconstruct it through the same adapter using the verified crosswalk.
- A target and a tackler can be the same player or two different players. Test both and the missing-target case.
- A corrected kickoff changes possession twice within one play. Verify that a recovered result retains the caught kick and return and that an uncredited recovery stays unresolved.
- Motion data can be late, contradictory or impossible within the provider interval. Preserve authoritative state and classify the partial/overrun outcome.
- Same-key corrections and queue backlogs must not silently replace a selected action or flash its old score after correction.

## Slice 1 · Typed evidence and ordered actions

**Files:** `libs/arbit-data/src/arbit_data/live/{contracts,nfl_api,play_facts,actions,animation,choreography}.py`. Tests in `libs/arbit-data/tests/{test_nfl_api,test_live_actions}.py`.

**Interfaces:** `nfl_api.motion_evidence(record, ids) -> MotionEvidence` is used at ingest and to enrich older retained NFL records on read. `actions.sequence(play: LivePlay, facts: PlayFacts) -> ActionSequence` returns unique identified participants, ordered steps, provenance and unknowns without building motion. It receives the current revision via the canonical play. Use `interpret` for source-neutral football semantics.

- [ ] Add focused failures for a stored/converted interception with one multi-role athlete and one with separate athletes. Assert the typed target ID, correct side and role reuse. Add a kickoff reversal, a missing crosswalk and an ESPN unknown-duration case.
- [ ] Normalize the relevant raw NFL names, provider identities, credited roles, numbered description and unique yardage evidence once. Preserve the existing scoring-facing participants and consume typed roles in the animation interpreter.
- [ ] Build ordered events for scrimmage passes, runs and sacks, kicks and their returns, possession changes and recoveries. Carry official state separately. Express unknown landmarks and provider evidence without defaulting missing numeric values to zero.
- [ ] Verify focused tests and a read-only archived replay through the application builder. Verify no player-name branches, no real provider dependency, and existing replay behavior for other plays.

## Slice 2 · Phase timing and trajectories

**Files:** `libs/arbit-data/src/arbit_data/live/{motion,trajectory,timing,animation}.py`, focused `test_live_motion.py`. Reuse existing field frame, units, alignment evidence, and fitting logic where valid.

**Interfaces:** `motion.plan(actions: ActionSequence, context: MotionContext) -> PlayScriptV2 | None`. `PlayScriptV2` carries actor motion, ball ownership/trajectory, action milestones, and separate provider and rendered timing. `trajectory.sample(track, seconds)` evaluates position and heading from shared cubic control data. Stable geometry seeds depend on play identity and motion-relevant inputs.

- [ ] Add failing coverage for handoff/exchange and center follow-through, receiver and ball arrival, smooth turns, credited pursuit, rapid release, compound turnover and an impossible timing budget. Assert continuous positions, distinct arrival/possession and physically feasible intervals.
- [ ] Build phase plans and constrained paths for passes, runs, sacks, interceptions and kicks. Extend to tries, fumbles, penalties, kneels and spikes. Use an explicit partial/text result when required anchors or participant identities are unresolved. Keep observed clock, motion and display separate.
- [ ] Compare selected traces with the offline development sample. Measure per-family continuity, timing residuals and fallback counts over archived ordinary PBP before freezing the holdout criteria.

## Slice 3 · Versioned API, renderer and playback

**Files:** `services/api/src/arbit_api/{member_routes,member_contracts}.py`, `libs/arbit-data/src/arbit_data/live/animation.py`, `apps/web/src/live/{LiveField,scene}.tsx` or corresponding TypeScript modules, atlas tooling in `scripts/sprites/live_art.py`, generated OpenAPI/TypeScript and contract fixtures.

**Interfaces:** `GET /api/v1/live/games/{event_id}/animation?script_version=2` opts into the replacement. The default response remains v1 during development. One scene sampler draws a v2 script at time t in playback and review. Ball attachment, world transforms and terminal state come from that sampler.

- [ ] Add contract and renderer tests for version compatibility, direction changes, attachment continuity at throw/catch and handoff, ball flight bounds and terminal visibility. Add a browser case for motion-changing same-key correction with active and reduced-motion playback.
- [ ] Add v2 transport, browser evaluation, sprite/foot anchors, directional poses and compatible fallbacks, one camera projection and bounded caching. Retain keyboard controls, text fallback and canonical board state. Route score-changing corrections to a corrected state without swapping an old trajectory mid-frame.
- [ ] Regenerate and verify contracts, run focused web tests and sample real v2 frames in the isolated member browser.

## Slice 4 · Private comparison and activation evidence

**Files:** `scripts/sprites/ngs_compare.py` or a browser-based successor, existing archived play checks, the M6 verification and handoff records.

- [ ] Render generated and reference motion from a shared timebase. Preserve tracked horizontal ball coordinates and label inferred possession, height and pose separately. Lock the held-out games and phase, route, alignment and speed measures before scoring v2.
- [ ] Verify coverage parity across supported play families, separate inferred and source-backed values, capture mobile/desktop and both directions, and measure frame cost and overlapping-game delivery. Replay synthetic late, corrected and missing-field cases independently from archived data.
- [ ] Run foundation, backend/contracts, web and isolated browser checks. Record regressions and unresolved source or art coverage. Present private clips and a local activation candidate for owner review.

Keep changes scoped to each slice. Record verified slices and commands in dated handoffs. Any commits or branch integration follow existing repository authorization and preserve the unrelated working-tree changes.
