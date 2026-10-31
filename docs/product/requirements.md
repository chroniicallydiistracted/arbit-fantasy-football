# Requirement Traceability

Version 0.1 · 2026-10-30. The [owner brief](vision-source.txt) is preserved unchanged. IDs below are stable verification obligations; **specified does not mean implemented**. The machine-readable [registry](requirements.json) is the authority for IDs, owner specifications, planned acceptance, and milestones. If requirements change, update both records together.

All original sections 1–12 map below. Shared requirements apply to every affected module, not only their first milestone. Later milestones retain the full scope; [roadmap](../project/roadmap.md) defines dependencies and release gates.

| ID | Requirement | Source sections | Milestone | Planned acceptance |
| --- | --- | --- | --- | --- |
| CTX-001 | One FFA redraft league; independent Arbit identity and Front Office headquarters | 1, 2, 3.1, 3.2 | M0 | Configuration fixes ESPN league 1729878439 and season 2026; no multi-league product workflow. |
| CTX-002 | Personalized manager/team/roster/matchup context in every advisor | 3.3 | M2 | Two authenticated member fixtures see their assigned teams; binding cannot be self-forged. |
| CTX-003 | Inaugural history, annual redraft, Geller Cup team/year and offseason custody | 3.4 | M7 | No fabricated prior champion; verified finals preserve team name, year and manager. |
| FO-001 | Team identity, roster, matchup, standings and relevant player performance | 4.1 | M2 | One published snapshot consistently supplies all own-team overview panels. |
| FO-002 | Strengths, weaknesses, positional needs, lineup considerations and actionable module links | 4.1 | M3 | Decision cards reuse advisor results, evidence and snapshot; no duplicate scoring/model. |
| DR-001 | Preparation, strategy, simulations, scenarios and player comparisons | 4.2 | M5 | Seeded full-draft scenarios compare options and resulting roster construction. |
| DR-002 | Actual league size/scoring/slots, draft format/order, own pick, all selections and available pool | 4.2 | M5 | Configured-format draft replay tracks every team; selected players leave availability. |
| DR-003 | Dynamic recommendations: filled/remaining needs, scarcity, projected value, byes and priorities | 4.2 | M5 | Replaying different selections changes recommendations and documents roster/bye tradeoffs. |
| DR-004 | Round/pick selection likelihood and next-pick availability with explanations | 4.2 | M5 | Simulation assumptions/calibration status are visible; no invented learned FFA probabilities. |
| DR-005 | Live tracking, corrections, stale protection and labeled manual fallback | 4.2 | M5 | Disconnect/correction/resync fixtures restore the board and suspend stale current-pick advice. |
| LN-001 | Full-roster weekly sit/start and globally legal optimized lineup | 4.3 | M4 | Exhaustive small-case oracle verifies unique-player slot assignment with locks and byes. |
| LN-002 | NFL/defensive positional matchups, recent trends, utilization and FFA opponent context | 4.3 | M4 | Evidence and objective use both own roster and actual opponent with sourced inputs. |
| LN-003 | Individual comparisons, outlooks, statistical reasons, projections and confidence | 4.3 | M4 | Alternative selection exposes horizon, gain, interval and evidence limitations. |
| WA-001 | Continuously updated complete FFA free-agent and waiver availability | 4.4A | M4 | Pagination covers the full pool; a new ownership revision invalidates pickup advice. |
| WA-002 | Recent/history/trends, opportunity, projections, upcoming matchups and position filters | 4.4A | M4 | Filtered weekly upgrades retain comparable windows, sources and FFA scoring. |
| WA-003 | Roster-specific weaknesses, legal add/drop alternatives and meaningful upgrade value | 4.4A | M4 | Legal package improves actual roster utility after required drops, with uncertainty. |
| TR-001 | All-team needs, strengths, depth, byes and roster compatibility | 4.4B | M5 | League needs matrix derives from every current roster and shared evaluations. |
| TR-002 | Suggested multi-player packages, player values and both managers benefits | 4.4B | M5 | Both post-trade rosters and drops are legal; before/after utility uses one horizon. |
| TR-003 | Feasibility and likelihood assessment with honest evidence limits | 4.4B | M5 | Qualitative early feasibility is labeled; numerical acceptance requires labeled held-out validation. |
| TR-004 | Custom proposal evaluation, comparisons and opportunity prioritization | 4.4B | M5 | Saved/custom packages retain snapshot/rules and flag changed ownership or deadlines. |
| SC-001 | Search/discovery, identity, history/current/game-level statistics and role | 4.5 | M3 | Profile resolves one canonical entity across provider IDs, team changes and seasons. |
| SC-002 | Advanced metrics, trends, news, depth chart, utilization and future matchups | 4.5 | M3 | Every metric/news item has source/time/definition; unavailable feeds remain explicit gaps. |
| SC-003 | FFA points, outlooks, projections, rankings and positional evaluation | 4.5 | M3 | Profile and advisors show the same scoring/model versions and uncertainty. |
| SC-004 | Rich interactive stat cards, statistical exploration and side-by-side comparisons | 4.5 | M3 | Two-to-four-player comparison aligns units/windows; chart information has a table equivalent. |
| SC-005 | Data-derived archetypes with explainable roles and performance profiles | 4.5 | M3 | Versioned labels show contributing metrics/sample; insufficient data yields unclassified. |
| LV-001 | Live scores/status/teams, game statistics and player participation/performance | 4.6 | M6 | Pregame/live/overtime/final/stale fixtures display correct state and provenance. |
| LV-002 | PBP, fantasy scoring, own-roster filters and fantasy matchup connection | 4.6 | M6 | Canonical participants drive filtering; official ESPN fantasy and live estimates remain distinct. |
| LV-003 | Interactive passing/rushing/sneak/sack/interception/FG/PAT and other play graphics | 4.6 | M6 | Named event replay fixtures and unknown fallback work with keyboard and reduced motion. |
| LV-004 | Gridiron field assets and verified matchup/week uniforms beside the field | 4.6, 5.5 | M6 | Asset manifest verifies source/variant/permission; missing variant is labeled fallback. |
| LV-005 | Late, duplicate, canceled and revised events update score and graphics consistently | 4.6, 6.4 | M6 | Replaying overlapping/corrected events changes effective scores once and preserves revision history. |
| MD-001 | nflverse-first shared intelligence and reusable evaluations across modules | 4.7, 5.2, 6.5 | M3 | All advisors consume common evaluation artifacts; external fantasy projections are benchmark-only. |
| MD-002 | Historical/statistical analysis, projections, rankings, matchups and roster values | 4.7 | M3 | A point-in-time evaluation set supports weekly/draft/rest-of-season horizons explicitly. |
| MD-003 | Advanced comparisons, trends, archetypes and decision-specific analysis | 4.7 | M3 | Interpretable or measured ML features explain contribution and evidence coverage. |
| MD-004 | Reproducibility, ML where appropriate, backtesting and validation | 4.7, 8.4 | M3 | Temporal holdout, baseline/subgroup metrics, leakage checks, lineage and rollback artifact recorded. |
| AR-001 | Historical standings/results/champions and Geller Cup history | 4.8 | M7 | Only verified season-final outcomes publish champions with audited correction history. |
| AR-002 | Season/team/player records, historical performance and comparisons | 4.8 | M7 | Record definitions and original scoring are visible; renamed teams preserve prior names. |
| DATA-001 | Complete ESPN league/settings/managers/teams/rosters/ownership/waivers/matchups/standings/draft | 5.1, 6.2 | M1 | Access proof, pagination, completeness and all actual rule categories are checked with sanitized fixtures. |
| DATA-002 | nflverse retrieval, historical storage, normalization/features/rankings/model processing | 5.2, 6.3 | M1 | Versioned manifests pin checksums, coverage, schema, publication/cutoff and attribution. |
| DATA-003 | Research applicable Sleeper scoring/player/game/play data; supplemental only | 5.3 | M1 | Documented endpoints separated from unproven candidates; no second league provider. |
| DATA-004 | Research ESPN NFL live endpoints before other gap sources | 5.4 | M1 | Scoreboard/summary coverage matrix and representative play-type fixtures establish actual capabilities. |
| DATA-005 | Unified players/teams/league/stats/games/draft/scoring/events/evaluations/recommendations | 6.1 | M1 | Aliases separate human/NFL team/DST/fantasy entities and unresolved identities cannot silently merge. |
| DATA-006 | Reliable snapshots, sync, correction handling and shared access | 6.2, 6.3, 6.4, 6.5 | M1 | Partial sync cannot replace current state; replay is idempotent and freshness failures visible. |
| DATA-007 | Single exact-rule scoring service and season-specific eligibility/lock rules | 4.2, 4.3, 4.4, 6.1 | M1 | Decimal scoring reconciles tested rules with ESPN; unknown rules block affected advice. |
| UX-001 | Design principles, visual identity, typography, color, spacing and layout | 7.1, 7.3 | M0 | Documented semantic tokens include verified text/focus contrast pairs and responsive rules. |
| UX-002 | Reusable navigation/cards/tables/charts/forms/controls and feature UX specifications | 7.3, 7.4 | M2 | All module workflows and component states documented; implemented shared components tested in context. |
| UX-003 | Loading/empty/error/stale states, accessible interactions and dense data readability | 7.1, 7.3 | M2 | Keyboard/screen-reader/zoom/reflow and chart table alternatives checked on implemented flows. |
| UX-004 | Desktop web and installable PWA with appropriate responsive/offline experience | 7.2 | M2 | Manifest/install/update/offline flow works; private API/auth responses excluded from worker caches. |
| ENG-001 | Justified frontend/backend/database/integrations/ML/live/PWA/deployment architecture | 8.1, 8.2 | M0 | Architecture compares alternatives, labels proposal status and records unresolved provider/hosting decisions. |
| ENG-002 | Clear feature boundaries, shared services, typed contracts and modular development | 8.3, 8.4 | M1 | Core has no provider imports; generated clients/contracts prevent duplicate wire/scoring logic. |
| ENG-003 | Tests, validation, errors, performance, environments and maintainable traceable changes | 8.4 | M2 | Appropriate unit/integration/browser/operational checks and budgets evidenced at each release gate. |
| ENG-004 | Authentication, user sessions and safe private provider integration | 3.3, 8.1 | M2 | OIDC/session/CSRF/authorization/revocation checks pass; ESPN cookies never reach browser/logs/Git. |
| GOV-001 | Authoritative product/architecture/development/continuity documentation | 9.1, 9.2, 9.4 | M0 | A fresh agent can locate specifications, status, decisions, known issues and latest handoff. |
| GOV-002 | Review/plan/implement/validate/document/handoff gates and code conventions | 9.3 | M0 | Task records identify affected requirements, evidence and risks; CI verifies foundation artifacts. |
| GOV-003 | Change history, ADRs/research/issues/status/tasks and cross-provider handoffs | 9.2, 9.4 | M0 | Every completed session updates status/changelog/handoff without relying on chat memory. |
| PLAN-001 | Dependency-aware phased roadmap retaining complete advanced scope | 10, 11 | M0 | Every requirement maps to a milestone, dependency, acceptance gate and planned verification. |
| PLAN-002 | Seven initial planning/specification/governance/scaffold deliverables | 11 | M0 | README links all seven deliverables; source brief preserved byte-for-byte. |
| SUCCESS-001 | Unified understandable data-driven intelligence usable throughout the fantasy season | 12 | M7 | End-to-end manager workflows exercise all modules with shared league/model context and honest limitations. |

M1d implementation evidence for DATA-002/005 and MD-004 prerequisites: [full NFLverse handoff](../project/handoffs/2026-10-31-nflverse.md). Acquisition, manifests and exact owned-athlete crosswalks are verified; semantic features, historical-vintage/model validation and broader product obligations remain open.
