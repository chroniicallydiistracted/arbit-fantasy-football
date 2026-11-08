# Live animation audit repairs

Requirements LV-001–005, DATA-006, DATA-008 and ENG-005. Preserve the NFL API as the primary game source, ESPN as the emergency fallback and league authority, point-in-time revisions, private artwork, and the distinction between observed action and re-creation.

The owner confirmed that stoppages update the Jumbotron in place, a removed selection retains its corrected text and a No Play notice, and complex plays may show the verified part and result with a textual explanation of the unknown action.

1. **Source ownership.** Store confirmed detail phase with the NFL publication in `store.py` and `nfl_feed.py`. Guard ESPN fallback publication under the same game lock. A verified NFL final owns the replay; an expired live detail still permits fallback. Re-read older final rows without confirmation. Reconcile fallback-only rows when the final NFL collection is verified. Test races, invalid final details, repeated polls and corrections on an isolated database.
2. **Facts, tries and choreography.** In `play_facts.py`, `nfl_api.py`, `animation.py`, `board.py`, `choreography.py`, `incidents.py` and `kicking.py`, recover observed action spots and aliases, use independent try facts/timing, and repair actor timelines. Extend coverage for the verified direct-snap, lateral, fumble and blocked-kick cases. Render only the known part when the feed leaves an action uncertain, preserving text and outcome.
3. **Playback and board.** In `LiveField.tsx`, `scene.ts`, `led.ts` and `Live.tsx`, keep a stable play/part selection across updates, follow new plays with reduced motion, draw the terminal ball, and update the Jumbotron in place for stoppages and final. Let members select a log entry directly and read its state or text fallback. Reproduce audit cases in Chromium on an isolated app.
4. **Serving and art.** Verify event targeting, compressed private animation reads and exact art availability. Keep missing variants labeled and resolve material art or release choices with the owner.
5. **Validation.** Run focused red/green regressions, the archived 31-game audit, runtime and web checks, and isolated browser coverage. Record exact evidence and any remaining gaps. A database repair or live release uses reviewed migration and rollback evidence.

[Audit](../../research/live-animation-pipeline-audit-2026-11-05.md) and [primary source plan](2026-11-05-nfl-api-primary.md).
