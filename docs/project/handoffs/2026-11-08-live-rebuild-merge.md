# Handoff — 2026-11-08 — Committing the shared tree and merging the Live rebuild

## Current state

At the owner's request ("commit all work thus far, and merge all branches to main"), `main` now holds all the uncommitted work from the shared working tree and Codex's `codex/live-animation-rebuild` (`8074c8f`). That was the only branch not already merged. The owner pushed `main` to GitHub afterwards.

- **Running app:**
  - The member API still serves the release snapshot of `8074c8f` through its systemd drop-in, and that commit is now in `main`.
  - The worker was restarted on the merged tree at 17:45 on 2026-11-08 (UTC−7), by owner request, between the late games and the night game. No migration was needed (0009 was already applied). All five lanes started, the NFL lane found week 9's 15 games, and the first minute had no errors or restarts.
  - Its first read republished the finished game 401873049 once: every current play gained `motion_evidence`, and 10 plays got corrected end positions (punts and a turnover on downs now end where the play text says; the final run leaves the next down unknown). The 8 plays logged as cancelled were already cancelled; none changed state.
- **Public address and stadiums:** both are unchanged by the merge ([public address](2026-11-08-public-address.md), [M&T Bank](2026-11-08-mt-bank-refinement.md)).

## Completed work

Four commits on `main`, then the merge:
1. `cfbd6d5`: the shared tree's Live and stadium work from Nov 5–8. This includes early drafts of the animation rebuild that Codex later finished.
2. `a0afb04`: the public address (ENG-049).
3. `0f448c2`: the fresh-polling and browser-leg measurements (R-042).
4. `f7e4532`: the project records.

**How the conflicts were resolved.** Codex's worktree was forked from the shared tree at about 13:10 on 2026-11-07. Each file was decided from the base, `main`'s copy, Codex's final version, and Codex's intermediate release `live-animation-preview-2026-11-07`:
- **Codex's version** for `Live.tsx`, `LiveField.tsx`, `live-playback.spec.ts`, `animation.py`, `choreography.py`, `play_facts.py` and the rebuild plan.
  - `main`'s copies held no line that wasn't also in the base, Codex's final or its intermediate release.
  - Codex's intermediate already held `main`'s later play-timing changes, which the final then replaced. For example, the pile "stumble" became `run_by`.
- **`main`'s version** for `context.py`, `live_art.py`, `stadium.py` and `test_stadium.py`.
  - Codex never edited these after the fork, since their worktree times are 13:08–13:10 on Nov 7.
  - `main`'s copies are that same version plus the stadium-venue work (ENG-047).
- **Clean merges:**
  - Six files merged to exactly Codex's version: `nfl_api.py`, the member contracts and routes, `openapi.json`, `api.ts` and `scene.ts`.
  - `positions.py` merged to exactly `main`'s.
- **Project docs, combined by hand:**
  - Status keeps both sides' paragraphs.
  - The changelog keeps both sides' sections.
  - Known issues keep `main`'s resolved R-042 and the new sections.
  - The decision register keeps Codex's OWN-055–057 and `main`'s OWN-058 and ENG-047–049.
- **Decision numbering:** `main` had numbered two decisions OWN-054. The NGS-archive decision keeps OWN-054, as on Codex's branch. The stadium-design decision became **OWN-059**, and its references were updated (ENG-047, status, changelog, the stadium plan and handoff, `venue3d.py`).

## Verification

All checks ran on the merged tree in a separate scratch worktree before `main` was fast-forwarded, so the running worker never saw a half-merged file.

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | 195 files formatted |
| `uv run mypy` | no issues, 105 source files |
| `uv run pytest -q -p no:cacheprovider` | 1,258 passed, 1 failed (below) |
| `node scripts/validate-contracts.mjs` | passed |
| `node scripts/web/check-generated.mjs` | OpenAPI and generated TypeScript are current |
| `node scripts/web/design-lint.mjs` | design rules pass |
| `node --test scripts/web/static-worker.test.mjs` | 1 passed |
| `node ../../scripts/web/tokens.mjs --check` | passed |
| `biome check` | passed, with the 3 reduced-motion CSS warnings Codex's release already noted |
| `tsc -b --noEmit` | passed |
| `vitest run` | 29 passed |

- **The one failure:** `test_foundation_references` was caused by `node_modules` links added to the scratch worktree during the run. After removing them, `pytest tests/contracts/test_foundation_references.py` passed, and `python3 scripts/validate_foundation.py` passed.
- **Not run:** the isolated browser suite. Every web and API file after the merge is byte-identical to Codex's release, which passed its five playback scenarios and is what the app serves now.

## Resume here

- Remaining work is unchanged:
  - Live default activation (M6 gates in the [motion handoff](2026-11-08-live-motion-calibration.md))
  - the M&T Bank likeness review
  - R-052 and R-053 for the public address

[Status](../status.md) · [Decisions](../decision-register.md)
