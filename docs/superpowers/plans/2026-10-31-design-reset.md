# Design reset implementation plan

**Goal:** Replace the generated-looking M2 visual system and copy with an original character the repository can enforce (OWN-016, [ADR-005](../../architecture/decisions/005-officiating-character.md)).

**Requirements:** UX-001, UX-002, UX-003, UX-005, FO-001. **Spec:** [design system](../../design/design-system.md), [feature experiences](../../product/feature-experiences.md).

**Scope:** tokens, fonts, mark, stylesheet, application shell, sign-in, Front Office, player drawer, watchlist, preferences, administrator controls, placeholder workspaces, offline page and all interface copy. **Excluded:** new analysis or recommendations; invented data to fill space.

**Files:** `packages/design-tokens/tokens.json`, `scripts/web/tokens.mjs`, new `scripts/web/design-lint.mjs`; `apps/web/src/*`, `apps/web/public/*`, `apps/web/tests/browser/member.spec.ts`; `services/api/src/arbit_api/static_shell.py` (font-notice allow-list), `member_contracts.py`, `member_routes.py`; `docs/design/design-system.md`.

**Read-model changes the layout needs:** roster ordered by lineup slot instead of provider ID; standings ordered by reported seed; a season strip of own results by matchup period, computed on the server; the configured playoff team count from stored rules. All are existing facts; none is hardcoded or client-side arithmetic.

## Tasks

1. **Tokens and enforcement.** Replace the palette and add spacing, type and board roles. Generate full CSS variables. Add `check:design` to `make web-check`: no hex or raw font size outside tokens, no banned font names, no banned phrases, no italics. RED: run it against the old stylesheet and observe failure.
2. **Identity.** New original mark, self-hosted OFL fonts with notices, install icons, manifest and theme colors, offline page.
3. **Shell.** Broadcast top band with wordmark, workspace tabs, search and account; context strip with season, period, compact scorebug and data status; bottom tab bar below 768 px (closes the existing deviation from the spec).
4. **Front Office.** Scoreboard matchup, season strip, grouped agate roster, league table with playoff line, source status, compact recommendation status.
5. **Everything else.** Player drawer, watchlist, preferences, administrator controls, placeholders, sign-in, errors.
6. **Copy.** Plain language across the product per the design system's language rules.

## Validation

`pnpm check:design`, `make web-check`, `make runtime-check`, the browser suite on an isolated port (four viewports, axe, 200% zoom, reduced motion, offline and update flows), and screenshots reviewed in light, dark and narrow layouts. Owner review is the acceptance gate for character; automated checks cannot establish originality.

**Rollback:** commits are isolated on `claude/platform-reset`.
