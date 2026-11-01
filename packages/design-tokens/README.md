# Design tokens

Semantic colors, type, spacing, layout and motion, with declared contrast pairs the foundation validator checks numerically. `node scripts/web/tokens.mjs` generates the client CSS and offline stylesheet; `make web-check` fails if they drift. Character and rules: [design system](../../docs/design/design-system.md).
