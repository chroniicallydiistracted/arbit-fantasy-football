# Arbit Design System Specification

Version0.2 · 2026-10-31 · M2 visual system implemented for the member shell and facts. Future feature/Live components remain specifications. See [feature experiences](../product/feature-experiences.md) for screen workflows and [tokens](../../packages/design-tokens/tokens.json) for machine-readable values.

## Product character and information hierarchy

A calm football front office: ink and warm paper, deep green for primary actions, restrained brass for the Geller Cup tradition. Dense analysis should feel readable and deliberate. Football team colors belong in team identifiers and Live context, not in place of semantic status colors. No decorative dashboard metrics without a decision or a clear meaning.

Each workspace answers: what matters, what evidence supports it, what alternatives exist, and what action the manager can take. The default hierarchy is page/team context → primary decision → evidence and comparison → supplementary statistics. Front Office is the entry point; the feature family shares profile, recommendation and matchup components. Model remains shared intelligence, with a plain-language methodology view.

## Visual tokens

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#F5F3ED` | `#101A18` |
| Surface | `#FFFFFF` | `#192622` |
| Primary text | `#182722` | `#F3F4EF` |
| Secondary text | `#506159` | `#B8C8BF` |
| Primary action | `#176044` | `#9AD8B3` |
| Action text | `#FFFFFF` | `#10251A` |
| Warning text | `#825200` | `#EFC36A` |
| Error text | `#AE2E35` | `#FFACAE` |
| Focus ring | `#176044` | `#9AD8B3` |

Use semantic variables, never arbitrary team-color text on unknown backgrounds. Brass `#A77828` is ornamental; use the tested warning token for small warning text. Borders use role-specific muted tones for decoration; form boundaries/focus must meet nontext contrast. Status always includes icon/text as well as color. Dark mode follows system preference with persistent account override; charts, field controls and asset framing have explicit dark treatments.

Typography: self-hosted OFL Instrument Sans for interface text and Newsreader for editorial headings, with system fallbacks. Scores use tabular numerals; IDs stay out of normal manager flows. Source mark is original SVG; PNG install variants are generated during build. Font notices ship with the static app. Type scale 12/14/16/20/24/32/40 px; body 16 px at 1.5 line-height; dense tables 14 px at 1.4; metadata 12 px only for secondary information. Strong numeric hierarchy must not hide units, horizon or source context.

Spacing base 4 px: 4/8/12/16/24/32/48/64. Corners 4/8/12 px; elevation restricted to dialogs/popovers. Content max 1600 px with 24–32 px desktop gutters; 12-column grid and 24 px gaps. Navigation width 232 px, header at least 64 px. Roster/research tables may use horizontal overflow rather than compressing values into unreadable columns.

## Navigation and responsive behavior

At ≥1280 px: persistent navigation, wide content, optional 320 px contextual rail. At 768–1279 px: collapsible navigation and stacked rail. Below 768 px: single column, compact top navigation/menu and a maximum of five direct bottom actions (Front Office, Lineup, Scout, Live, More); Draft/Market/Archive remain accessible through More. Active draft can offer a contextual shortcut without changing route semantics. These are layout breakpoints, not device detection.

Global player search is keyboard accessible; Esc closes overlays and returns focus. Team/season/week context is visible when it changes interpretation. Back navigation restores scroll/filter/comparison state. Touch controls target ≥44 px; no hover-only action. PWA safe areas, browser back behavior and install/update prompts use platform conventions. Accessibility and layout must be tested at 320, 768, 1280 and 1600 px, with 200% text zoom and reflow.

## Component inventory and behavior

| Component | Required behavior/states |
| --- | --- |
| AppShell / Navigation | Active route, keyboard order, mobile menu, team/period context, session expiration |
| Button / IconButton / Link | Primary/secondary/quiet/danger, loading, disabled reason, focus; links navigate, buttons act |
| FormField / Select / Search / SegmentedControl | Persistent label, help/error association, keyboard selection, debounced async loading, clear action |
| Card / Panel / Disclosure | Heading hierarchy, bounded density, expanded keyboard access; whole-card navigation must not swallow child buttons |
| PlayerIdentity / PlayerStatCard / ProfileDrawer | Team/position/ownership, current role, rich research sections, missing data, consistent player link |
| StatValue / StatTable / DataTable | Units/window, alignment, tabular digits, sort/filter/page or virtualization, sticky header with semantic table support |
| RecommendationCard / EvidenceDrawer | Action, benefit/horizon, alternatives, evidence/sample, freshness, uncertainty, methodology link, blocked reason |
| ProjectionInterval / TrendChart / ComparisonChart | Observed vs projected style, zero/baseline choice, consistent axes, table alternative, keyboard point inspection |
| TeamHeader / MatchupSummary / RosterSlot | Official vs projected score, eligibility/lock, own/opponent context, bye/inactive/empty states |
| DraftBoard / PickClock / AvailabilityEstimate | Current pick, selected/available, board corrections, offline/manual status, scenario assumptions |
| TradeBuilder / AddDropComparison | Package legality, both teams' effects, stale ownership, unknown waiver/deadline rules |
| GameScore / PlayTimeline / FieldReplay | Status/clock/possession, filters, corrections, pause/step/replay, schematic label and fallback |
| SourceStatus / EmptyState / ErrorState / Toast | Fresh/partial/stale/unavailable, recoverable action, timestamps; no generic success message for failed action |
| Dialog / Popover / Tabs / Tooltip | Appropriate semantics, focus trap only in modal, restore focus, close keyboard handling; essential information outside tooltip |

Component implementation should reuse proven accessible primitives when appropriate, with semantic HTML first. Document examples for default/loading/empty/error/stale/disabled/focus states. Use story-based visual checks when runtime exists. Do not create a component library disconnected from real feature workflows.

## Tables and visualization standards

Numeric columns right-align, textual identities left-align. Keep fixed precision appropriate to meaning; decimal fantasy totals follow the rule set and do not invent extra confidence through formatting. Column headings expose units and definitions. Pin player identity on wide comparison tables; preferences restore without changing data meaning. Virtualized tables must retain accessible row/column semantics or provide paginated accessible mode. Empty, filtered-zero, and unavailable are different states.

Use line charts for time trends, interval/dot charts for uncertain projections, bars for comparable quantities, and heatmaps only where a table legend makes values recoverable. Avoid radar charts as the default player comparison. Use direct labels and source/sample/cutoff. Observed values solid; modeled projections dashed/banded with text label. Missing intervals remain gaps. Color palettes use distinct hue/lightness plus shape/dash encoding, tested in color-vision simulations. Never use a three-dimensional effect to imply more evidence.

## Live graphical system

Field coordinate plane is normalized length 0–100 between goal lines, separate end zones, width proportional to 53 1/3 yards. The canonical play can be mirrored to the user's viewing orientation without changing data. Mark line of scrimmage, first-down distance where observed, ball direction and start/end positions. Paths are schematic, never claimed tracking data. Passing/rushing/turnover/sack/kicking events have distinct path/icon/text treatments; unknown events retain narrative. Verified team fields and weekly uniforms use an asset manifest; generic fallback is labeled. Text timeline and participant/fantasy facts remain useful if images fail.

Motion uses short 120–200 ms UI transitions; play sequences typically 600–1800 ms with visible replay controls. User-triggered playback only by default; reduced motion uses static start/end and narrative. Corrections are labeled and old effects updated, not played as another score. Screen readers receive throttled score/play summaries and can pause announcements.

## Loading, failure, and confidence language

Use stable-layout skeletons for first load with an accessible busy label. On refresh, preserve prior values and show their timestamp; a source failure must not erase unrelated successful panels. “No recommendations” distinguishes no material upgrade from incomplete analysis. A stale ownership snapshot says when it was observed and offers refresh; it cannot imply a pickup is currently possible. Offline shows connection status and safe shell; private data is not persisted in service-worker caches.

Recommendation copy: **Action → evidence → uncertainty → action link.** Example structure: “Consider [player] for [slot]. [Measured opportunity/matchup evidence]. [Risk or missing input]. Review in ESPN.” Examples use synthetic labels until supported by real results. Confidence labels describe evidence quality; numerical probabilities appear only when validated and correctly named. Do not expose backend IDs, training jargon or provider errors in normal manager flows; keep diagnostic details in authorized administration.

## Accessibility and design acceptance

Target WCAG 2.2 AA: text contrast ≥4.5:1 for normal text and ≥3:1 for large text; meaningful nontext boundaries/focus ≥3:1; visible focus not obscured by sticky UI; semantic landmarks/headings; keyboard-complete paths; error summaries; accessible names; reduced motion; 200% zoom and 320 px reflow. Announce async errors and important changes without focus theft. Automated checks complement manual keyboard/screen-reader testing of sign-in, research comparison, lineup, draft and Live.

The foundation validator checks declared token pairs, including text over canvas/surface and primary action text; this is token evidence, not a full interface accessibility audit. Feature release requires actual viewport/keyboard/contrast checks, labeled data provenance, error-state review and fidelity to the documented hierarchy. M2 now has actual four-viewport rendering, keyboard/focus/reflow and automated accessibility checks; native OS install/human screen-reader validation remains release work. See the [handoff](../project/handoffs/2026-10-31-member-application.md).
