# ADR-005: Officiating and broadcast product character

Status: Accepted · 2026-10-31 · Owner direction OWN-016; concrete direction chosen by the primary developer, open to owner veto on review.

## Context

The owner reports the interface has drifted into AI-identifiable design. A 2026-10-31 audit confirms it. The M2 visual system combined a forest-green split screen, warm cream canvas, serif display type with a gold italic phrase, tracked uppercase eyebrows above every heading, numbered navigation, a period after the logo and heading, and generated taglines. Each is a common default of generated interfaces, and together they could belong to any product. Mechanically, spacing tokens were used 0 times, about 70 one-off font sizes were in use, and raw hex values lived in the stylesheet. Nothing enforced the system. Taglines included "A seat in the front office", "A considered view of the season", "Facts first. Insight follows." and "Your league. In perspective."

## Decision

Arbit derives from *arbiter* (brief §2.1). Its character comes from the people who actually rule on a football game and the graphics used to show it: **the officials and the broadcast booth.**

- **Vocabulary of signals, taken from the game.** The yellow first-down line and penalty flag mark a decision or a threshold. The blue line of scrimmage marks modeled values. Sideline-chain orange marks live or provisional values. The red challenge flag marks faults and corrections. Field green is reserved for gains and the field itself. These replace generic "brand", "accent" and "warning" colors, and they carry the product's required distinction between official, live and projected values.
- **Structure from broadcast graphics and the sports page.** Always-dark scoreboards, a persistent scorebug, hard-edged modules and dense agate tables. Referee stripes are the only decorative motif, used rarely.
- **Type.** Big Shoulders (tall American gothic, stadium signage) for display and numerals; Libre Franklin (the sports-page grotesque tradition) for text and tables. No serifs, no italics.
- **Language.** A referee states the call. Labels say what a thing is, empty states say what is missing and what would change it, and there are no slogans, taglines or marketing lines anywhere, including the sign-in page.
- **Enforcement.** `pnpm check:design` fails on raw colors or font sizes outside tokens, banned generic fonts, and banned phrases. The brief's §9.3 asks tooling to enforce gates where possible.

## Alternatives and consequences

Keeping the system and tuning its colors would leave its structure and voice intact, and that is what reads as generated. A neutral dashboard theme would be cleaner and just as anonymous. A neo-brutalist yellow-and-black treatment would be distinctive but is its own recognizable trend, so yellow stays a narrow signal and offset shadows are excluded. Dark-only would suit the broadcast reference but contradicts the existing account-level theme preference.

Stripes and football references can tip into novelty, so they stay structural, rare and functional. Team colors remain confined to team identity and Live. This replaces design-system v0.2 and its token set; migration is one pass through tokens, stylesheet and copy, with browser tests updated in the same change.

## Evidence

Token contrast through the foundation validator, four-viewport and axe browser checks, `pnpm check:design`, and owner review of the rendered product, passed 2026-10-31 (OWN-018). Related: UX-001/002/003/005, OWN-016; [design system](../../design/design-system.md).
