# M1e supplemental sources, live coverage and asset prerequisites

> **For agentic workers:** Use superpowers:executing-plans inline. Meaningful RED→GREEN regressions per task, one fresh final whole-branch reviewer, one Important/Critical fix pass.

**Goal:** Make supplemental source acquisition reproducible and bounded; prove ESPN NFL game/play capabilities with real source-backed fixtures; enforce explicit Gridiron variant/permission prerequisites.

**Architecture:** Reuse PostgreSQL request gates and immutable object storage. Store public source observations and refresh reservations separately from authoritative FFA snapshots. Sleeper directory/state/trends are supplemental only; candidate stats remain research. Normalize ESPN games/plays once, extract only explicitly supplied participant IDs, and demonstrate revision-aware replay without calculating fantasy points. Asset records resolve to a labeled fallback unless exact context and permission evidence are present.

**Tech stack:** Existing Python/Pydantic/SQLAlchemy/PostgreSQL/worker, standard-library bounded HTTP and immutable objects. No new framework, UI, model, member authentication or cloud service.

**Spec:** Accepted data architecture and ADR002/004; roadmap M1e; DATA-003/004, DATA-005/006 prerequisites, LV-001/002/003/004/005 source prerequisites. Owner explicitly requested this milestone; existing architecture/dependency approval continues. No new product scope or permission gate is needed.

## Global constraints

- Single ESPN FFA league1729878439/configured2026; no Sleeper league adapter, account or transaction. Supplemental trends are not FFA ownership/availability. Recommendations remain disabled.
- Fixed public GETs only; no cookies/proxies, redirects or automatic dereferencing of payload URLs. Safe failures, byte/time/page bounds, independent Sleeper pacing and shared ESPN budget. Source metadata is evidence, not a service guarantee.
- Sleeper full directory at most once per24hours across processes, including reservations before uncertain requests. State hourly/trends15minutes are local policies. Cached reads must not renew source age; failures preserve last good data and visible staleness.
- New additive0005migration only; no applied DDL edits, snapshot resets or destructive alias changes. Exact existing IDs may produce read-only mapping evidence; no automatic alias creation/merge from supplemental inputs.
- Preserve source bodies, hashes, observation times and all original fields. Unknown/null is not zero. Local observations do not establish historical vintages.
- Live estimates/official FFA totals remain distinct. No fantasy-point derivation from narrative or source points. No invented routes or stadium orientation. Missing participants/coordinates use unknown fallbacks.
- Candidate statistics are explicitly undocumented even if HTTP200; successful response does not make a supported play feed. Record bounded candidate outcomes and field coverage.
- No Gridiron image download, hotlink activation, scraping campaign or outbound contact. Exact owner patterns, context/variant and permission evidence are prerequisites. Empty/unverified manifest yields labeled fallback, not an error that blocks independent work.
- Use dedicated local branch codex/m1e-supplemental-live at2a8f35a; existing host native-worktree limitation remains, no repeated helper retry. No push, merge, deployment or long-running server/importer left running.

## Review focus

- Concurrent/failed directory acquisition must not bypass the daily reservation; late workers cannot overwrite newer source state, and cached data cannot become fresh merely by being read.
- Malformed/huge JSON, redirects, credential-bearing or injected paths and drifting page counts must fail safely before publication; raw body/receipt integrity must be independently replayable.
- Supplemental conflicting IDs and D/ST rows cannot attach to human athletes or become authoritative FFA availability; season/state mismatches stay explicit.
- ESPN summary lacks per-play athletes in the observed sample; core collection supplies them. Preserve reference scope without fetching embedded URLs; partial/overlapping/out-of-order/corrected/no-play snapshots cannot silently erase known plays or double-apply scoring.
- Asset scope/permission ambiguity, neutral venues, week/type differences and expired authorization must select fallback; visual existence is not reuse permission or verified weekly variant.

## Task1 — Durable public observations and bounded requests

Files: new `arbit_data/public_sources/{requests,transport,repository,service}.py`, `0005_public_sources` migration, schema/db revision, shared gate provider, unit/integration tests.

Interfaces: `SourceRequest` has canonical key/provider/url/response-kind/ttl/usage; `build_source_request(kind, season=2026, week=None, event_id=None, page=1)` produces only allowlisted paths. `PublicTransport.fetch(request) -> PublicResponse(body,payload,receipt)` uses fixed-origin validation,32MiB/30second bounds, strict finite JSON/unique keys, no redirects/proxy/credentials. `SourceService.acquire(request, normalize) -> ObservationResult` reserves persistent refresh before request, uses independent/shared gate, saves original/normalized/manifest objects then atomically publishes with token/expiry fence. `load_observation` checks immutable hashes; status gives age/error without raw bodies. Two additive tables: observations and refresh/current/reservation.

- [ ] Write failing tests for route injection/options, bounded actual HTTP stack, duplicate/nonfinite JSON, truncation/429/cooldown; two concurrent daily reservations, failure preserving prior current, expired/late publication and cached age.
- [ ] Run focused tests; expected missing modules/behavior FAIL. Implement and verify focused PostgreSQL/HTTP tests plus Ruff/mypy PASS; commit.

## Task2 — Sleeper supplemental contracts and exact join evidence

Files: `arbit_data/sleeper/{contracts,reader,mapping}.py`, focused tests.

Interfaces: `normalize_sleeper(kind,payload)` validates full dictionary IDs vs row IDs, separate D/ST rows, state and trend structures, retains extras/raw originals and explicit source attribution/usage. `identity_coverage(uow,players,cutoff)` resolves only exact already trusted GSIS/ESPN aliases; disagreements/missing/duplicates remain counts/reasons, no alias mutation. Documented resources: directory/state/add/drop. Two probed stats representations remain candidate/benchmark and cannot supply FFA points.

- [ ] RED tests: invalid/mismatched/duplicate IDs, missing values, D/ST isolation, season mismatch signal, trend count vs ownership distinction and conflicting/read-only mapping.
- [ ] Implement, focused tests PASS; live directory once through durable cache, cached rerun no new directory call, safe actual coverage receipt. Commit.

## Task3 — ESPN game/play normalization and source-backed replay

Files: `espn/endpoints.py` (scoped scoreboard and core play collection), `arbit_data/live/{contracts,normalize,reader,replay}.py`, observed minimal fixture JSON and provenance, unit tests.

Interfaces: scoreboard supports explicit season/type/week; core plays supports event/limit/page without dereferencing payload refs. Reader bounds20pages/6000plays, checks count/page scope and deduplicates consistent overlap, rejects drift. `normalize_game`/`normalize_play` preserve provider ID/type/text/scores/clock/period, multiple effects and explicit athlete/team refs; parse reference IDs only from expected public ESPN NFL paths. Schematic offense-relative distances carry no physical-route claim and never compare yards-to-endzone across a turnover as one direction. `merge_observations(previous,current)` is pure revision-aware replay: duplicate stable, older observations ignored, explicit no-play cancels, missing play is not a tombstone. It emits no fantasy arithmetic.

- [ ] RED tests for named play types, unknown fallback, participants from public refs and hostile/private ref rejection, turnover endpoint frames, null positions, duplicate/conflicting pages, numeric sequence ordering, revised/canceled/late/reordered/omitted plays and overtime/status distinctions.
- [ ] Implement and verify focused tests PASS. Probe bounded representative 2026 games and preserve minimal factual source fixtures/provenance; synthetic corrections/states are distinctly labeled. Active/delayed/correction live observations not available now remain empirical gaps. Commit.

## Task4 — Gridiron context and permission gate

Files: `arbit_data/assets.py`, empty operator manifest `config/gridiron-assets.json`, focused tests and prerequisite research.

Interfaces: typed `AssetRecord` pins kind, game/season/season-type/week/team/venue/variant, source page/image URL, checksum/media dimensions, exact-context verification and permission grant/evidence/expiry/attribution. `resolve_asset(context,records,as_of)` returns verified local metadata only when exactly one valid matching record exists, otherwise labeled fallback with reasons. No downloader or URL-to-variant inference.

- [ ] RED tests: empty manifest, ambiguous/mismatched game/week/team/neutral venue, unverified variant, missing/expired permission, unsafe URLs and positive exact verified record.
- [ ] Implement, focused tests PASS. Verify actual source navigation/terms through primary pages, record owner-pattern and grant gaps; no media or contact. Commit.

## Task5 — Operator commands, full source audit and handoff

Files: worker `source_commands.py` + main registration, command tests, source-audit JSON/Markdown and play-fixture provenance, source/operator guide, project status/requirements/architecture/handoff.

Interfaces: `sleeper-sync` (all four documented supplemental resources), `sleeper-probe --season --week` (two explicit candidate stats), `live-inspect --season --week --events ID...` (bounded scoreboard/summary/core collection), `sources-status`, `sources-verify`, `live-replay --observation HASH`, `assets-check`. Local database/object directory guards reuse existing operator setup. Prints safe counts/hashes/gaps only, no member/source text. Offline replay/verification require no source calls.

- [ ] RED CLI tests for argument bounds, cached/no-network reads, safe partial failures and original FFA snapshot unchanged. Implement, focused PASS.
- [ ] Full runtime check and populated-schema upgrade PASS; real documented/candidate/live calls through implementation, exact mapping/participant coverage and offline replay/checksums measured. No core endpoint availability inferred from one sample.
- [ ] One final independent reviewer required by executing-plans; fix Important/Critical via observed RED→GREEN regressions and whole suite; minors deferred explicitly. No second review.
- [ ] Update AGENTS/README/source register/requirements/status/roadmap/issues/changelog/API/data operations and dated handoff with actual commands, decisions, empirical gaps, next M2 gate. Commit clean local branch; no active processes at finish.
