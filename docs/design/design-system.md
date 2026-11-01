# Arbit Design System Specification

Version 0.3 · 2026-10-31 · Implemented for the member shell and facts. Replaces the v0.2 system, which the owner rejected as AI-identifiable ([ADR-005](../architecture/decisions/005-officiating-character.md)). Future Live and advisor components remain specifications. Machine values: [tokens](../../packages/design-tokens/tokens.json). Screen workflows: [feature experiences](../product/feature-experiences.md).

## Character

Arbit is named for the arbiter. The interface takes its character from the people who rule on a football game and the graphics that show it: **officials and the broadcast booth.** It should read as a piece of football equipment, not a software template.

Every workspace answers: what matters, what evidence supports it, what the alternatives are, what the member can do. Hierarchy runs context → decision → evidence → supporting statistics. Density is a feature; members come to compare numbers.

## Language

This is a rule, not a preference: **no slogans, taglines or marketing lines anywhere in the product**, including the sign-in page. A referee states the call.

- Labels say what a thing is: "Roster", not "The team sheet".
- Empty and error states say what is missing, why and what would change it: "No roster saved for this matchup."
- Say what isn't built: "Not built yet. Sit and start calls need player projections." Don't promise ("coming soon", "insight follows").
- State uses exact words: **Official** for ESPN-published figures, **Final**, **In progress**, **Live** and **Provisional** for unconfirmed values, **Projected** for model output, **Current** and **Behind** for data age, and **Off** for a disabled capability. A recommendation is a **call**.
- Short sentences. No exclamation marks, no addressing the member's feelings, no "seamless", "effortless", "unlock", "elevate".
- Never expose IDs, training jargon or provider errors in member flows.

Recommendation copy follows **action → evidence → uncertainty → ESPN link**. Confidence labels describe evidence quality; a numeric probability appears only when validated and correctly named.

## Color: signals from the game

Everything is black and white until something needs attention. Each signal has one meaning, taken from what it means on a football broadcast, and never decorates.

| Role | Light | Dark | Football source | Meaning |
| --- | --- | --- | --- | --- |
| `canvas` / `surface` | `#E7E9EB` / `#FFFFFF` | `#0A0B0D` / `#15171B` | | Cool neutral only. Never cream |
| `ink` / `inkMuted` | `#0B0C0E` / `#4A5059` | `#F5F6F7` / `#AEB4BD` | | Text |
| `flag` | `#FFC600` | `#FFC600` | Penalty flag and first-down line | A decision or threshold: active tab, playoff line, own team. Fill only, with `onFlag` text |
| `los` | `#1257C9` | `#86B7FF` | Blue line of scrimmage | Modeled or projected values, and model state |
| `chain` | `#A93C05` | `#FF9A5C` | Orange sideline chains | Live, provisional, questionable, data behind |
| `challenge` | `#BA0E18` | `#FF8A91` | Red challenge flag | Faults, corrections, out, losses |
| `gain` | `#0A6B32` | `#5FD892` | Field | Wins and positive change. The field surface in Live |
| `board*` | constant | constant | Broadcast scoreboard | Always-dark band, scoreboards and drawer headers, in both themes |

`action` is black in light mode and yellow in dark. Team colors belong in team identity and Live, and never replace a signal. Status always has text as well as color. All token pairs are contrast-checked by the foundation validator.

**Excluded:** cream or warm paper backgrounds, forest green, gold or brass accents, gradients as decoration, drop shadows, glass, offset neo-brutalist shadows, pulsing dots.

## Type

- **Big Shoulders** for display: page and section titles, tabs, table headers, slot tags and all large numerals. Tall American gothic drawn from stadium signage. It is the only uppercase in the system and carries almost no tracking.
- **Libre Franklin** for text and tables: the sports-page grotesque tradition. Tabular lining figures everywhere.
- Roles: `agate` 12 px (secondary only), `data` 13, `ui` 14 (tables), `body` 16, `label` 17, `h3` 20, `h2` 26, `h1` 44, `score` up to 96, `gate` up to 176.

**Excluded:** serif display faces, italic emphasis, tracked uppercase eyebrows above headings, a period after a heading or logo, numbered navigation, Inter and the other generated-interface defaults listed in the lint.

## Space and shape

Spacing is the 4 px scale in tokens, used through `--space-*` and `--gutter`. Corners are square, or 2 px on controls. There are no elevation shadows; separation comes from rules, boards and surface change. Maximum content width is 1520 px.

## Motifs

Used rarely, always structurally.

- **Referee stripes:** the 4 px strip at the top of the window and the sign-in panel. Nothing else.
- **Hash marks:** the tick rule under a page title, drawn like yard-line hashes.
- **First-down line:** a solid yellow rule marks a threshold, such as the active tab, the current matchup or the playoff line.
- **Mark:** an original white A with a yellow first-down line running through it, on black. No NFL, ESPN or Gridiron media.

## Layout and navigation

- **Band:** always-dark top band with wordmark, workspace tabs, search and account. Not a left sidebar: tables get the width.
- **Context strip:** FFA, season, matchup period, compact scorebug on other workspaces, and data status.
- **Front Office:** scoreboard and season strip across the top; roster and league table beneath.
- **Breakpoints:** ≥1100 px one-row band with rail; 768–1099 px tabs on a second row, single column; below 768 px a bottom tab bar with at most five direct actions (Front Office, Lineup, Scout, Live, More), with Draft, Market, Archive and account under More.

These are layout breakpoints, not device detection. Layout must work at 320, 768, 1280 and 1600 px, and at 200% text zoom. Touch targets are at least 44 px on controls, and no action is hover-only. Wide tables scroll in their own container rather than compressing values.

## Components

| Component | Required behavior and states |
| --- | --- |
| Band / Tabs / BottomTabs | Active route with first-down marker, keyboard order, More sheet closes on Esc and returns focus |
| Button / Link | Primary, default, quiet; loading and disabled with reason; links navigate, buttons act |
| Field / Select / Search | Persistent label, help and error association, debounced async search, Esc clears |
| ScoreBoard / SeasonStrip | Official or Live authority label, Final or In progress, own team marked, unknown scores as a muted dash, results by period |
| AgateTable | Grouped rows, units in headers, tabular digits, numeric right, identity left. Empty, filtered-zero and unavailable are different states |
| PlayerDrawer | Pins its snapshot, modal focus handling, restores focus on close, states missing data |
| SourceStatus | Current, Behind or Refresh failed, with age from the source's observation time |
| RecommendationCard / EvidenceDrawer | Action, benefit and horizon, alternatives, evidence and sample, freshness, uncertainty, methodology link, blocked reason. Modeled values in `los` |
| ProjectionInterval / TrendChart / ComparisonChart | Observed solid, projected dashed or banded with text label, consistent axes, table alternative, keyboard point inspection |
| DraftBoard / TradeBuilder / AddDropComparison | Selected and available, package legality, both teams' effects, stale ownership, unknown rules |
| GameScore / PlayTimeline / FieldReplay | Status, clock, possession, filters, corrections, pause and replay, schematic label, fallback |

Reuse accessible primitives where they help; prefer semantic HTML. Build components against real workflows, not a disconnected library.

## Tables and charts

Numeric columns right-align; identities left-align. Precision follows the rule set and never invents confidence. Line charts for time trends, interval or dot charts for uncertain projections, bars for comparable quantities, heatmaps only with a recoverable table. No radar charts by default and no 3D. Observed values are solid, modeled values dashed or banded in `los` with a text label. Missing intervals stay gaps. Palettes combine hue, lightness and shape, and are tested in color-vision simulation.

## Live graphics

The field plane is normalized 0–100 between goal lines with separate end zones and width proportional to 53⅓ yards. A play can mirror to the viewer's orientation without changing data. Mark the line of scrimmage in `los`, the first-down line in `flag`, ball direction and start and end positions. Paths are schematic, never claimed as tracking. Pass, rush, turnover, sack and kicking events have distinct path, icon and text treatments, and unknown events keep their narrative. Verified Gridiron fields and uniforms use the asset manifest and are served only inside the private application (OWN-015); a generic fallback is labeled. The timeline and fantasy facts stay useful if images fail.

UI transitions run 120–200 ms; play sequences 600–1800 ms with visible controls. Playback is user-triggered by default; reduced motion uses static start and end frames with narrative. Corrections are labeled and old effects updated, never played as another score. Screen readers receive throttled summaries and can pause announcements.

## Loading, failure and freshness

First load shows the running-stripe indicator with an accessible label. Refresh keeps prior values and their timestamp; a source failure doesn't erase unrelated panels. "No recommendations" distinguishes no material upgrade from incomplete analysis. Stale ownership says when it was observed and cannot imply a pickup is possible. Offline shows connection status only; private data is never persisted in service-worker caches.

## Enforcement and acceptance

`pnpm check:design` (part of `make web-check`) fails on raw colors, raw font sizes, off-scale spacing, shadows, italics, banned fonts, and slogan phrases in the interface. Add a phrase when one slips through. The foundation validator checks token contrast. These catch regressions; they cannot judge originality, which needs review of the rendered product.

Target is WCAG 2.2 AA: text contrast ≥4.5:1 (≥3:1 large), nontext and focus ≥3:1, focus never obscured by sticky UI, semantic landmarks and headings, keyboard-complete paths, accessible names, error summaries, reduced motion, 200% zoom and 320 px reflow. Async errors and important changes are announced without focus theft. Browser checks cover four viewports, axe and keyboard flows. A human screen-reader pass and native install remain release work.
