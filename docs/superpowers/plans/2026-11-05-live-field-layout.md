# Live field layout and play coverage

The owner asked for an audit of observed NFL play types across the Live pipeline, a single horizontal row of the existing game cards above the detail view, and priority for the Jumbotron.

- Requirements LV-001, LV-002, LV-003, LV-004, LV-005, UX-002 and UX-003. Use the [feature experience](../../product/feature-experiences.md#live-live-livegamesid) and [design system](../../design/design-system.md#live-graphics).
- Run the shipped normalizer, play facts, choreographer and board builder on the available Week 1 and Week 8 full-slate NFL responses and Week 9 Thursday game. Count raw types, list/folded rows, scripts, and actual canvas eligibility separately. Check the log's API and browser filters and the independent game-summary features. Record actual gaps and the bounds of the sample.
- In `Live.tsx` and `styles.css`, make the detail-view game cards one horizontally scrolling row. Reuse the existing cards, ordering, and styles. The field gets the full content width. The slate overview keeps its grid.
- In `GameBoard.tsx` and `LiveField.tsx`, keep the readable live score and put the full game details in a disclosure below a functioning Jumbotron. When the field has no board, show the full scoreboard above it.
- Verify the narrow and desktop layouts, scroll and keyboard navigation, the field and score disclosure, and the fallback on an isolated app. The backend play and art interfaces stay the same.
