# Decisions, Inputs and Open Questions

Updated 2026-10-31. Architecture and recommended stack approved by the owner on 2026-10-30; additional development dependencies are authorized, especially for UX/UI work.

## Confirmed product decisions

| ID | Decision | Evidence |
| --- | --- | --- |
| OWN-001 | Arbit, FFA companion, Front Office headquarters, eight-capability family, one redraft league | Owner brief v 1.0 |
| OWN-002 | ESPN league ID `1729878439`, season `2026` | Owner reply 2026-10-30 |
| OWN-003 | Portable, local-first proposal | Owner reply 2026-10-30 |
| OWN-004 | Owner's prior Gridiron direct asset URL patterns are not yet available | Owner reply 2026-10-30 |
| OWN-007 | Owner made FFA public, reviewed the successful API audit and authorized development using public access; message boards are not required | Owner request 2026-10-30 |
| OWN-006 | Architecture/stack approved; additional dependencies approved; deliberate, high-quality UX/UI and engineering required | Owner reply 2026-10-30 |
| OWN-005 | nflverse primary statistics; ESPN league truth; Sleeper supplemental; ESPN-first live research | Owner brief §§5–6 |
| OWN-028 | Uniform colors come from the owner's Gridiron uniform set, never inferred: "Do not infer the uniform colors. I have all 250 renditions and combinations of uniforms for every team in 2026." The set is in ignored `data/Gridiron_2026_Uniforms`, personal use only (OWN-015). A game uses the uniforms its Gridiron week page lists; a TBA or unnamed version is not shown as real | Owner statement 2026-11-03 |
| OWN-027 | Poses ship without the ball; the renderer draws one ball sprite at the hand or chest: "Wouldn't be better if we just render the poses for the actions, then superimpose a separate ball sprite when needed?" | Owner statement 2026-11-02 |
| OWN-026 | Owner connected PixelLab and approved its first frames, built on their original art: "These are actually perfect... These are incredibly close to the original." The goal is every pose sequence for every action, in both skin tones and all 32 teams. PixelLab's terms give the owner ownership of its output | Owner statement 2026-11-02 |
| OWN-025 | Owner reviewed the drawn frames: "the additional sprites you created are a good attempt, but overall are a stark downgrade from the original set I have." The 34 drawn frames are not used in the app. Only the sheet's 6 original poses meet the bar, and new poses need a source at that quality | Owner statement 2026-11-02 |
| OWN-024 | The sprite art belongs to the owner, and the animations should be pushed to the repository. The sheet and frames are public on branch `claude/sprite-art`. Gridiron art stays out (OWN-015) | Owner statement 2026-11-01 |
| OWN-023 | Owner approved the look of the test frames and asked for more poses and better versions of the test frames: "Yes these animations are good... overall I like it a lot." The single-play look gate is passed; new play types still get owner review on rendered video | Owner statement 2026-11-01 |
| OWN-022 | Use the pixel sprite look instead of 3D. New poses must be "as close to exact that we can get" to the owner's sheet | Owner statement 2026-11-01 |
| OWN-021 | Animate only what is relevant to the play: "We can animate everything that is relevant to the play. Other players and their positions do not need to be animated. We will animate the plays specifically." Replaces the spec's dashed schematic | Owner statement 2026-10-31 |
| OWN-020 | Approved raw live capture and one worker restart before the first live slate | Owner statement 2026-10-31 |
| OWN-019 | Move Live ahead of M3: research Gridiron URL patterns, fetch field and uniform art, then build Live scoreboards and game animation. Prerequisites first. Animation must be "more than just SVG draws, or low effort/quality stepped animations" | Owner statement 2026-10-31 |
| OWN-018 | Owner accepts the officiating-and-broadcast design: "I love the design. It's actually perfect." | Owner statement 2026-10-31, after the running app was upgraded |
| OWN-017 | Every changing source needs a solid sync worker; Live needs near-real-time workers; clients refresh live; members get a true authenticated app session. Drift into a "project app" is not acceptable: professional grade from here on | Owner direction 2026-10-31 |
| OWN-016 | Design has drifted to AI-identifiable tokens, CSS, coloration and slogan copy. Develop the design system further, including stylization, tokens, semantics, fonts, palette and product character. All projects are held to a unique, original design | Owner direction 2026-10-31; [ADR-005](../architecture/decisions/005-officiating-character.md) |
| OWN-015 | Gridiron Database: permission obtained privately for all images/assets, personal use only. URL patterns not yet fully researched | Owner statement 2026-10-31; the grant itself is held by the owner, not in this repository |
| OWN-014 | Hosting platform undecided; set up after application development finishes. Production origin will be `https://ffa.westfam.media` | Owner statement 2026-10-31 |
| OWN-013 | Audits/reviews may run, including by subagent, but no model with higher usage cost than the primary session's. The Sol-only rule existed to stop an expensive model running reviews | Owner statement 2026-10-31; supersedes the subagent clause of OWN-011 |
| OWN-011 | Sleeper only for relevant NFL live games/PBP; no fantasy data integration. ~~Use only GPT-6.1 Sol for every subagent~~ (see OWN-013) | Owner correction at start of M2, 2026-10-31; overrides broader earlier source interpretations and skill model defaults |
| OWN-010 | Proceed with M1e supplemental Sleeper, ESPN Live coverage and Gridiron prerequisites | Owner request 2026-10-31; [audit](../research/m1e-source-audit-2026-10-31.md) |
| OWN-009 | Proceed to M1d with all-encompassing NFLverse inclusion | Owner request 2026-10-31; [full audit](../research/nflverse-data-audit-2026-10-31.md) |
| OWN-008 | Every successful usable endpoint must be wired before mapping actual FFA rules and verifying ESPN totals; recommendations stay disabled until verification | Owner continuation 2026-10-30 |

## Accepted architecture decisions

| Record | Proposal | Status / adoption point |
| --- | --- | --- |
| [ADR-001](../architecture/decisions/001-modular-runtime.md) | React client + modular Python API/worker, native workspace tools | Accepted by owner 2026-10-30 |
| [ADR-002](../architecture/decisions/002-data-and-identity.md) | PostgreSQL + versioned Parquet, explicit aliases and immutable publication | Accepted; M1 data implementation |
| [ADR-003](../architecture/decisions/003-shared-intelligence.md) | Shared exact scoring and point-in-time evaluated models; no fabricated probabilities | Accepted; M1 scoring and M3 model implementation |
| [ADR-004](../architecture/decisions/004-access-live-and-pwa.md) | Separate invite/OIDC auth, server-only ESPN read access, SSE, static-only PWA caching | Accepted; M1 integration/M2 authentication |

Owner approval adopts these runtime choices. Hosting remains portable/local-first and no paid hosting is provisioned. Exact dependency versions are resolved and locked when the runtime is bootstrapped.

## Open inputs and decision rules

| ID | Missing input / unresolved capability | Impact | Next action and decision owner |
| --- | --- | --- | --- |
| Q-001 | Public source mode authorized for the current development phase; future private visibility is an optional change | Core reads work without cookies; message-board availability has no product impact | Public reader implemented and live-verified; configure and test server-side credentials only if visibility later becomes private |
| Q-002 | Actual settings retrieved; rule/category normalization, membership binding and scoring reconciliation remain | 46 scoring items, OFFLINE draft, actual slots/waivers/locks observed; usable normalized advice still requires validation | M1c mapped all 46 rules, reconciled completed weeks and persisted canonical FFA facts/rules/locks/eligibility and observed memberships; member account binding and lineup optimization remain |
| Q-003 | Resolved: Google (OWN-012); first administrator verified by owner. Remaining invited roster is an owner action at release | Second-member proof needs the hosted origin or a sign-in on the owner's machine | Release / OWN-014 |
| Q-004 | Permission resolved by OWN-015 (personal use, private app only). URL patterns resolved: [research](../research/gridiron-url-patterns-2026-10-31.md). Fields are mostly listed only after games, so a pre-game field is a candidate rather than confirmed | Limits field certainty before and during a game, not uniforms or the renderer | M6: sync lane and per-game status |
| Q-005 | nflverse per-dataset coverage and available historical release metadata | Determines usable in-season features and holdout periods | M1d full catalog/import/coverage and source-revision proofs complete; first local observation is not historical vintage evidence. M3 defines retrospective/vintage policy before backtests |
| Q-006 | Eligible Sleeper NFL live-game/PBP routes remain unverified | Sleeper cannot be a Live dependency yet | Fantasy routes/hints are retired, not future features. Verify only relevant game/PBP candidates in later source work; ESPN remains active |
| Q-007 | ESPN live endpoint coverage across event types/corrections | Determines exact Live event/graphic fidelity | M1e records four final games including overtime/tie, pregame, core participants and factual fixtures; active/delayed/corrected empirical coverage and latency remain M6 |
| Q-008 | Domain resolved (`ffa.westfam.media`, OWN-014). Platform, capacity, backup location and budget remain | Blocks external deployment only, after development finishes. Until then only this machine can reach Arbit | Before release: owner selects; keep runtime portable. Google needs the production redirect URI registered at that point |
| Q-009 | Empirical FFA draft/trade history and optional ADP source | Limits learned selection/acceptance likelihood | M5: use labeled scenario priors and qualitative feasibility until enough validated data exists |
| Q-010 | Exact first FFA season and archive finalization detail | Limits any imported prior results/Cup entry | M1/M7: confirm source history and actual championship outcome; preserve inaugural-season empty state |

These are milestone prerequisites, not a demand for the owner to answer every question now. Engineering can proceed with contracts, sanitized fixtures and local runtime tasks while the remaining source/model/auth prerequisites are resolved. Material alternatives are documented before changing scope or cost.

## M1c implementation decisions

- Local operator inspection uses an optional random secret plus actual loopback peer, with no-store and no provider calls. This is a development-only read surface; accepted invite/OIDC member architecture and production startup block remain. [Guide](../engineering/ffa-synchronization.md).
- Native fantasy-team/matchup aliases include league/season scope; manager source membership never proves Arbit account ownership. Dated affiliations describe observations. M1d now implements exact GSIS/ESPN matching and backed-up alias corrections; ambiguous records remain in review.
- Parsed/redacted capture hashes differ from original HTTP body hashes. Unchanged observations confirm the existing revision; replay cannot move current or renew freshness. First/new scoring-lineup contexts require completed-period reconciliation; preseason/rollover needs a separate validation design.

## M1d implementation decisions

- All published core/ffverse logical partitions are included, with one preferred serialization per stem and explicit mirror/model/legacy/diagnostic/benchmark decisions. Data ZIPs remain intact archive originals; every table column and null is retained. [Audit](../research/nflverse-data-audit-2026-10-31.md).
- Hashless assets stage until a second complete source catalog confirms identity/size/revision. Immutable proofs and separate confirmation times constrain as-of reads; local hashes alone cannot authenticate mutable upstream revisions. Source/catalog order separately fences current pointers.
- Exact GSIS/ESPN pairs reuse existing UUIDs; entity-wide contradictory active provider IDs enter review. Five newly imported later supplemental aliases were corrected after backup by closing their validity and appending reviews, preserving original rows/reports. No name merge or historical backdating.
- Parquet/CSV use bounded Arrow processing; nested RDS uses a resource-limited data-only fallback and explicit JSON columns with original RDS retained. Dependencies are approved and frozen. No upstream model execution, source ranking promotion or recommendation enablement.

## M1e implementation decisions

- Daily Sleeper directory reservations persist across processes and failed/uncertain requests. The actual batch policy marks stale at one interval or failed refresh; architecture's longer serving windows remain proposals for measured M6 tuning. No automatic supplemental/live scheduler.
- Candidate stats 200 responses do not imply documented support, verified FFA scoring or a supported play feed. Supplemental hints remain read-only; 40/121 owned direct matches are a visible coverage limit, not a reason to name-match.
- Explicit public core play references supply athletes absent from the summary. Scoped origin/event/play checks never fetch embedded URLs. Per-play page observation time governs revision ordering; a newer summary/page cannot restamp older cached facts.
- Gridiron `eligible_metadata` is always distinct from local image readiness. Empty manifest and missing grants remain fallback; no image bytes or external messages are authorized by M1e. Both site's uniform and field permissions require genuine evidence.

## M2 owner overrides

OWN-011 supersedes the broader Sleeper interpretation used in M1e. Preserve past receipts as history without consuming those datasets. All subagents must explicitly use `gpt-6.1-sol`; no Astra or other model is authorized. M2 is authorized under the accepted invite-only OIDC/member-binding and React/PWA architecture. Sign-in provider choice was requested early; provider-neutral work proceeds without credentials in chat.

| OWN-012 | 2026-10-31 | Google selected for M2 sign-in | Fixed official issuer/endpoints/hosts, private local client configuration; no client provisioned |
| ENG-021 | 2026-10-31 | Biome handles frontend lint/format with strict TypeScript, Vitest and Playwright | One frozen toolchain replaces proposed ESLint; generated types/tokens checked for drift |
| ENG-027 | 2026-11-03 | A frame is painted in a real uniform from a map of which part each pixel shows, made from the skeleton it was drawn from. Colors are measured at fixed places on Gridiron's sheet template, and shades use the owner's sheet's own ratios. GIFs keep every sprite color exactly | The owner's classes tie helmet to pants and jersey to socks, which real uniforms don't. Measuring at template places needs no per-team choice, and the ratios reproduce all 64 of the owner's sets. The old 128-color encoder turned Chicago's orange into yellow. [Research](../research/uniform-measurement-2026-11-03.md) |
| ENG-026 | 2026-11-02 | New frames are drawn by PixelLab's skeleton animator from an original frame recolored to a key palette: the owner's Arizona colors with the four black trims and the two whites made distinct. Each pixel then maps back to one of the 21 color classes, so one drawing renders in all 64 sets. The approved fall keeps its Arizona pixels and takes only ambiguous classes from a key redraw | Drawing per team would cost 64 times as much and vary between teams. A real team set as the key drifted across classes, and a loud synthetic key bled into the helmet |
| ENG-025 | 2026-11-01 | A play is labeled corrected only when its period, yardage, kind, scoring flag or score value, or a credited offensive or kicking player, differs from what ESPN first reported. Every revision stays in the history | Counting any new revision labeled 69% of plays on real data; this labels 2.5% overall and 8% on games captured live. Wording, tacklers, clock and raw score changes are ESPN's drafts settling, and an overturned score changes the scoring fields. [Receipt](../research/live-slate-receipt-2026-11-01.md) |
| ENG-024 | 2026-11-01 | Scoreboard detail adds no migration on game night; the summary is stored in the existing `boxscore` column | The worker reads every column, so a pending migration could stop live scoring if it restarted first. [Plan](../superpowers/plans/2026-11-01-live-scoreboards.md) |
| ENG-023 | 2026-10-31 | Play animation keeps a permanent "Re-creation from play-by-play" label with ESPN's facts one action away | Movement between ESPN's spots is generated, and the no-fabricated-tracking invariant still applies under OWN-021 |
| ENG-022 | 2026-10-31 | M2 facts use named typed fields and a shared snapshot object | Supersedes generic data/meta proposal for implemented routes; generated contracts, Decimal/null and safe problem errors retained |
