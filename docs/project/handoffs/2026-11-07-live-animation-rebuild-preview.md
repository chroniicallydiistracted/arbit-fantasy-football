# Handoff · 2026-11-07 · Live animation rebuild preview

The owner approved the rebuild and its formation-aware handoff and center follow-through changes (OWN-055). A player has one identity and can change roles when the live description or structured credits support it. Every live script uses current NFL play-by-play, the existing roster context and authored motion rules. ESPN remains the emergency fallback. NGS remains offline under OWN-053 and OWN-054.

The working preview is on codex/live-animation-rebuild in the attached isolated worktree. It was seeded with the existing uncommitted source and documentation baseline. The running app, worker, database records and Git history were outside the implementation.

## Implemented

- NFL normalization retains provider identity, canonical crosswalk, display name, role, jersey and reported air yardage separately from existing scoring-facing participants. The animation read path applies the same adapter to older retained raw revisions. A target credited with the tackle has one track. An unrelated tackler keeps their own actor.
- Ordered actions preserve release, arrival, possession, return, contact, loose ball and recovery separately from official state. A next snap alone does not establish a physical endpoint. Shared tackles retain all credits.
- The v2 preview fits supported runs, passes, interceptions and kickoffs. Cubic tracks have continuous velocity and independent body heading. Generated motion and the provider clock have separate endpoints and timing diagnostics. The kickoff preview retains the catch, return, loose ball and recovery when supported by the effective ruling.
- The member endpoint accepts script_version=2 and the isolated game page uses the same query parameter. Other play families and unsupported input use existing scripts. The preview uses shared ball attachment geometry, keeps held balls in front of their carrier, bounds synthetic flight height to the viewport and preserves the terminal ball.
- A motion-changing correction shows the corrected endpoint and can be replayed. Caption-only updates keep the current playback time. The default endpoint and page continue to request the original script version.

## Verification

- With PYTHONPATH pointing to the attached checkout and the existing project virtual environment, `python -m pytest -q -p no:cacheprovider` passed 1,247 tests. `ruff check .`, the touched Python formatting check, `mypy` (105 files), OpenAPI and TypeScript regeneration comparisons and `git diff --check` exited 0.
- From apps/web, Biome on the touched files and `node_modules/.bin/tsc -b --noEmit` passed. `node_modules/.bin/vitest run` passed 27 tests. Design, token and static PWA checks passed. The broad web lint reported three pre-existing reduced-motion CSS warnings.
- The isolated fixture preview on port 8027 ran `node_modules/.bin/playwright test live-playback.spec.ts` using installed Chromium. All five scenarios passed, including same-key corrected geometry and a caption-only update.
- A read-only run of the existing Week 1 and Week 8 archive harness plus the stored Week 9 game produced 2,722 v2 clips in 31 games. It checked actor uniqueness, pose availability, continuous ball intervals, valid attachment references and the trajectory speed bound. This checks internal validity. The motion has not been evaluated against the NGS holdout.
- On the isolated preview on port 8028, Chromium drew 35 milestone frames across the six previously audited plays from stored NFL PBP and private art. The frames remain in ignored data/sprites/review/live-animation-v2-preview-2026-11-07. Both preview servers stopped after their checks.
- `python3 scripts/validate_foundation.py` passed after the handoff update.

## Gates still open

- Extend v2 to all supported families, including sacks, scrambles, punts, field goals, tries, standalone fumbles, penalties, kneels and spikes. Add shared-contact motion and special-teams variants, then compare fallback rates by family.
- Validate motion and directional poses on held-out games. The preview still uses the existing sprite atlas with mirrored and foreshortened poses. Direction-specific authored frames, detailed contact and first-seen field coverage need further work.
- Use the same browser timebase for all reference comparisons and measure overlapping-game delivery and render performance. Holdout review and owner activation review are release gates.

[Approved design](../../superpowers/specs/2026-11-07-live-animation-rebuild-design.md) · [Implementation plan](../../superpowers/plans/2026-11-07-live-animation-rebuild.md) · [Calibration handoff](2026-11-07-live-animation-calibration.md)
