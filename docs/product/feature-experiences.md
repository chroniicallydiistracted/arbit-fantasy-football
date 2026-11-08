# Arbit Feature Experience Specifications

Version 0.1 · 2026-10-30 · Proposed. These describe the complete intended experiences; implementation status is in [project status](../project/status.md).

## Shared frame and workflows

Desktop top-band navigation: Front Office, Draft, Scout, Market, Lineup, Live, Archive (phones use a bottom tab bar). Model is the common intelligence foundation; a secondary methodology/data-status entry exposes versions, uncertainty and source coverage without making technical administration a normal manager task. A context strip shows FFA, season, matchup period, a compact scorebug and data status; the band carries player search. Routes preserve selected player, period, filter, sorting and comparison context in the URL; private saved scenario IDs are authorized server-side.

First access: invitation → sign-in → administrator-bound team confirmation → Front Office. Missing binding shows a clear pending-assignment state. Each decision follows **overview → evidence → comparison/scenario → suggested action → ESPN**, with no implied external submission. A shared player drawer preserves workspace context; opening a full profile has a distinct URL. All modules share one player profile and recommendation detail component.

## Front Office (`/front-office`)

**Job:** understand this week's position and the most useful next decision.

**Content:** team/manager identity, record and league rank, current fantasy opponent, official points and separately labeled projections, roster/locks, positional strengths/depth/byes, relevant player trends and news, prioritized recommended decisions, and links to all modules. Recommendations come from shared Lineup/Market/Draft results, rather than another Front Office model.

**Flow:** select current or historical matchup → inspect key decision → open underlying module with identical snapshot and player context → save a comparison or continue to ESPN. Users can dismiss or watch a decision; dismissal is personal and does not remove underlying data. Desktop: team/matchup masthead, decision queue, roster with contextual analysis rail. Narrow: matchup, decisions, roster, standings in that order.

**Components:** TeamHeader, MatchupSummary, RecommendationCard, RosterTable, PositionalDepth, StandingsTable, SourceStatus. A newly synced league with no model run shows accurate league facts and a pending-analysis state. Missing/stale data is panel-specific, with the affected action disabled or labeled.

**Acceptance:** two fixture members receive their own roster and opponent; every insight links to evidence with the same rule/model version. Empty recommendations explain whether there are no pressing decisions or analysis is unavailable.

## Draft (`/draft`)

**Job:** prepare and make every selection in the context of the actual FFA draft.

**Preparation:** strategy scenarios, tiers, player profiles/comparisons, watchlist, draft slot and league configuration, byes, projected roster builds and availability by round/pick. Simulations let users vary draft position, strategy and uncertainty, with reproducible seed and assumptions.

**Live flow:** detect active draft → confirm own team/pick → reconcile full draft board → show top choices, expected availability at next selection, scarcity and roster needs → inspect alternatives → make selection in ESPN → observe authoritative pick and recompute. Board, available-player table, recommendation panel and team construction summary remain coordinated. Desktop keyboard shortcuts may focus search/board but cannot silently draft a player.

Manual draft-state entry/import is available only as an explicitly labeled fallback, with undo, correction history and reconciliation conflict handling. It never pretends to be an ESPN-synced draft. Paused, disconnected, picked-player race, undetermined order and unsupported draft format show distinct states. Do not assume snake format before reading settings. Every recommendation accounts for filled/remaining slots, all teams' picks, positional scarcity, scoring, opportunities, byes and current roster.

**Acceptance:** complete replay under configured format; two plausible picks yield measurably different later roster options; no selected player is recommended; reconnect/correction restores pick order; availability probabilities state prior and calibration limits for an inaugural league.

## Scout (`/scout`, `/scout/players/:id`, `/scout/compare`)

**Job:** understand a player's production, role, outlook and alternatives in depth.

Search/filter by player, team, position, availability, archetype, season and period. Profile header contains canonical identity, NFL team/position, current role/injury state with timestamp, FFA ownership, watchlist and compare action. Sections: overview; game log and history; advanced efficiency/opportunity; role/utilization/depth; upcoming schedule and defensive context; news with linked source/time; projections/rankings with uncertainty; archetypes/methodology. Tabs are deep links with visible active state.

Stat Card is a rich composed profile, not a single small tile: season and game totals, trend charts, contextual benchmarks, data dictionary tooltips, sample counts and source coverage. Player-specific measures differ for QB/RB/WR/TE/K/DST if those positions are relevant to FFA. Inapplicable measures show an explanation, not a zero. Historical team moves remain visible.

Compare two to four players with identical scoring/horizon/window filters, aligned units and downloadable accessible table if export permissions permit. Use consistent y-axis ranges for comparable charts; let users inspect a data point with keyboard. Adding a player preserves prior comparison. Mobile uses a comparison selector rather than four unreadable columns.

**Acceptance:** every advanced metric resolves to a definition/source/window; game-level FFA points reconcile with rules; news freshness and unavailable injury/route data are explicit; comparable profiles reuse the model results used by Lineup/Market/Draft.

## Lineup (`/lineup`)

**Job:** choose the best legal lineup and understand close decisions.

Select scoring period → load complete own roster, eligibility and lock constraints → review recommendation → compare alternatives → explore expected-points or matchup-win objective → inspect supporting player/defense evidence → continue to ESPN. A side-by-side actual/proposed lineup shows differences and expected effect; locked players remain fixed. Slot assignment must solve eligibility globally, including FLEX overlaps, rather than greedily ranking each position.

Evidence includes current/recent opportunity, efficiency, NFL team/opponent defense and positional matchup, injury/role coverage, uncertainty, and the opposing fantasy roster. Opponent context affects a matchup objective through joint outcome simulations; it does not claim certainty or encourage arbitrary risky choices. Show projection interval, objective/horizon, model methodology and assumptions. Explain when a suggestion is close enough that the data does not strongly favor one player.

Components: LineupSlotList, EligibilityBadge, LockStatus, PlayerComparison, ProjectionInterval, MatchupDistribution, EvidenceDrawer. Incomplete roster/rules, inactive player with uncertain source, postponed game, bye, empty slot and all-locked lineup each have a useful state. Lock state is rechecked on refresh and when an action is opened.

**Acceptance:** optimal assignments verified against exhaustive small rosters; two-way FLEX eligibility cannot duplicate a player; locked starters unchanged; missing evidence does not yield false precise confidence; every recommendation can be reproduced from its snapshot.

## Market (`/market/waivers`, `/market/trades`)

**Waivers:** filter by availability/position/horizon → ranked roster-specific upgrades → inspect usage/trend/matchup and floor/ceiling → compare own drop candidates → view legal add/drop package, bye/depth impact and known waiver deadline/budget/priority → continue to ESPN. Availability and bids are FFA-specific. A rostered player is never shown as acquirable, whatever an outside ownership figure says. Bench opportunity cost and required drops are part of the gain. FAAB advice is conditional on actual settings and sufficient evidence; unknown bids are not assumed.

**Trades:** scan team-needs compatibility → inspect suggested packages or build a custom proposal → compare both teams before/after, starters/depth/byes and rest-of-season values → inspect replacement/drop consequences and feasibility → save/share within authorized Arbit context or continue to ESPN. Both managers' benefit and key assumptions remain visible even for asymmetrical packages. No messages are sent automatically. No numerical acceptance probability until labels and evaluation support it; early feasibility is an explained rules/needs assessment.

**Components:** AvailabilityBadge, WaiverTable, AddDropComparison, TeamNeedsMatrix, TradeBuilder, PackageEvaluation, ValueHorizonControl. Concurrent ownership change invalidates the package and offers refresh without discarding the user's scenario. League trade deadline, undroppable players, veto/review rules and waiver eligibility come from settings, with explicit unknowns.

**Acceptance:** recommendations depend on the actual manager's deficiencies; both post-trade rosters and drop packages are legal; gains reuse shared evaluations; source refresh changes the available list and marks saved packages historical.

## Live (`/live`, `/live/games/:id`)

**Job:** follow NFL action and its effect on one's fantasy team and matchup.

Select game/slate → see score/status/clock, possession, team stats and roster relevance → filter all plays / own roster / fantasy scoring → select a play → watch its re-creation and read the narrative, participants, game statistics and provisional fantasy effects → replay or step to next play. Fantasy matchup panel distinguishes ESPN official totals from Arbit live estimates. A selected historical play stays selected while new plays arrive; provide a “return to latest” button rather than jumping the view.

On a single game's page, the other game cards keep the slate card styling and share one horizontally scrolling row above the full-width field. The Jumbotron provides the main visual score during play re-creations. The live score has a screen-reader equivalent, and the game details and score by quarter expand below the field. The full scoreboard is visible when the field cannot show a Jumbotron. Timeouts, penalties and period endings update the Jumbotron in place. Selecting a play from the log opens its replay or text. A correction keeps the selected play and labels a cancelled replay No Play. Partial re-creations describe the unshown action in text.

Each play is animated with pixel sprites in a side-on broadcast view (OWN-022): pass, rush, QB sneak, sack, interception, FG, PAT and other normalized play types; turnovers can change possession/direction during a sequence. Only what is relevant to the play appears: the players ESPN names on it and the ball, landing on ESPN's exact spots (OWN-021). Other players and their positions are not animated. Movement between ESPN's facts is generated, so the animation keeps a permanent "Re-creation from play-by-play" label, ESPN's facts stay one action away, and it is never presented as tracking. Unknown field position/type falls back to readable text and player/event information. Motion is pausable, skippable, keyboard-operable and respects reduced motion; no endless distracting autoplay.

Verified weekly uniforms flank the field and the appropriate field asset forms its surface; every asset has an exact variant/source record. A game uses its verified exact field when available. Otherwise it uses the venue's most-used verified field this season, breaking ties by most recent use and labeling the field as usual. Without a verified venue field, the app shows a labeled plain field. Unknown uniform variants show a labeled plain kit. Owner-provided patterns and permission checks remain prerequisites for Gridiron reuse, not prerequisites for text-based Live work.

States: pregame, delayed/postponed, halftime, overtime, final-provisional, final-reconciled, stale/disconnected, corrected event and feed unsupported. New-play announcements are throttled and polite; no focus theft. Duplicate/late/canceled plays update history and fantasy effects idempotently.

**Acceptance:** replay fixtures cover all named play types, both directions, overtime, penalties/no-play, turnover returns, duplicate/reordered plays and score corrections; roster filters match canonical participant IDs; no claim of exact movement from PBP alone.

## Archive (`/archive`, `/archive/seasons/:season`)

**Job:** preserve FFA history and the Geller Cup tradition.

Season selector → final standings and bracket/outcomes → champion/team/manager and trophy custody → season/team/player records and historical comparisons. Trophy history records the winning team name and championship year, with the manager holding the Cup through the offseason; each next season is a fresh redraft. Preserve names as they were that season.

Records use explicit definition, scoring version, regular/postseason scope and ties. Current season is provisional; historical corrections show revision audit. Inaugural-season empty state explains that history is forming, with no invented champions. An administrator confirms imported final results against ESPN and the league's actual championship outcome before publishing a Cup entry.

**Acceptance:** renamed teams do not rewrite prior winners; ties and multiweek playoffs handled; cross-season scoring differences disclosed; a pending inaugural season has no fictional historical records.

## Arbit Model (shared service; optional `/methodology`)

**Job:** make every advisor use coherent evidence and measured methods.

The user-facing methodology view explains features, source coverage, uncertainty, baseline comparisons, model release and known gaps in plain language. It may expose rankings and archetype exploration, but does not become a competing copy of Scout. Administrative training/configuration lives separately from a manager's workflow. Exact modeling contracts and release criteria: [Model specification](../architecture/model-specification.md).

## M2 implemented experience

Front Office now implements saved official team/roster/matchup/standings facts, historical period and position filters in URLs, pinned player drawer/search, private watchlist/theme preferences and administrator invitation/team approval/revocation/suspension/reactivation controls. Unknown scores remain dashes; historical selection with no roster capture withholds the roster. Current standings remain labeled current. Analysis and other modules explicitly identify future capability. Google access requires private client setup; [local operator/member guide](../engineering/member-application.md). Native install and human assistive-technology acceptance remain open.
