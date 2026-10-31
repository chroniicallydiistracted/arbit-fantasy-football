# M1e — Supplemental sources, ESPN live coverage and asset prerequisites

**Historical source scope:** At the start of M2, the owner excluded all Sleeper fantasy inputs and limited Sleeper to relevant live NFL games/PBP only. The former directory/state/trend/stat/hint integrations described below are retired; receipts retain their historical meaning and are not application inputs. See OWN-011.

Completed **2026-10-31**, local branch **`codex/m1e-supplemental-live`**, base `2a8f35a`. M1e implements the accepted roadmap's source prerequisites; it does not ship the M6 Live interface or enable recommendations. Requirements DATA-003/004 are verified for their source-research acceptance; DATA-005/006 and LV-001–005 have partial foundation evidence and remain broader obligations.

## Delivered and observed

- Durable public observations preserve original bytes, normalized JSON and immutable manifests, with daily cross-process directory reservations, last-good pointers, safe failures, expiry/token fencing and independent/shared provider gates. Additive `0005_public_sources` is applied locally. No applied earlier migration changed.
- Sleeper's directory/state/add/drop endpoints all returned 200. The directory has 12,229 records, with same-hash/time cached repeat and no second directory request. Read-only exact aliases yield 5,685 linked, 27 conflicts, 6,485 unresolved and 32 excluded D/ST records. Only 40/121 owned athletes have direct matching directory hints; 81 lack a raw matching ESPN/GSIS hint. No names, alias creation or ownership inference fill that gap. NFLverse still resolves 121/121 owned athletes.
- Two explicit undocumented week 7 statistics candidates each returned 2,095 rows with the same ID set. The newer representation supplies 2026/week 7/regular metadata. They remain research inputs with unverified FFA scoring and no supported live-play-feed claim.
- ESPN's scoped regular-season week 8 scoreboard has 14 events: one final and 13 scheduled. Four completed games yielded 842 game-specific plays, including three with period 5 and one tie.706 plays carry athlete references; all 293 game-scoped unique IDs resolve through existing canonical ESPN aliases. A pregame summary has null scores and explicitly no play-source request.
- Twenty actual provider types are pinned in a minimal factual fixture with original-body hash/completed receipt and source IDs. Synthetic tests separately cover missing/error/delayed/correction/sneak cases. No actual active-game latency, observed source correction pair or explicit sneak label was obtained; these remain M6 empirical gates.
- Replay preserves each play's page observation time, original provider modification metadata, explicit no-play cancellations and omitted-play history. It performs no fantasy arithmetic or persistent effective-play/SSE publication. A fresh summary or another page cannot renew older play provenance. Unknown field/participant data remains unknown; no tracking route or stadium orientation is invented.
- Gridiron uniform/field pages and 2026 navigation were verified by bounded HTML reads. Both constructed graphics require permission. Empty `config/gridiron-assets.json` and tested exact-context/permission gate yield fallback; `eligible_metadata` always says `local_asset_ready=false`. Zero image bytes downloaded, zero messages sent, no owner previous patterns or grants confirmed.

[Source audit](../../research/m1e-source-audit-2026-10-31.md), [safe receipt](../../research/m1e-live-2026-10-31.json), [observation inventory](../../research/m1e-source-inventory-2026-10-31.json), [Gridiron prerequisites](../../research/gridiron-prerequisites-2026-10-31.md), [operator guide](../../engineering/supplemental-live-sources.md). Raw public bodies/HTML and private league state remain ignored; committed evidence contains counts/public URLs/hashes and minimal NFL facts, no league-member payloads or credentials.

## Commits and environment

Plan `8f58571`; capture/reservations `8f0601a`; Sleeper `e470c86`; ESPN normalization/replay `2e059a0`; asset gate `3689d05`; operator commands `4223d5b`; independent-review fixes **`a529b72`**. Final documentation/evidence commit follows. No push, merge, provider mutation, external publication or deployment occurred. Branch/workspace are retained locally.

Python 3.12.13, uv 0.11.33, Node 24.22.2, pnpm 12.16.1 and local PostgreSQL on loopback 55439. No dependencies were added in M1e. Existing host `bwrap`/native-worktree/Corepack limitations use the prior scoped-command/dedicated-branch/pinned npm-exec workarounds. Schema revision is `0005_public_sources`; real populated-v 1 upgrade and actual populated-local upgrade preserve prior data.

## Exact verification

```sh
npm exec --yes --package=node@24.22.2 --package=pnpm@12.16.1 -- make runtime-check
```

Final **409 tests passed** (18.97 seconds), Ruff lint/format 125 files, strict mypy 71 source files, AJV contracts and foundation validation. PostgreSQL tests use isolated random schemas in `arbit_test`; no public tables/database were reset. Network calls are opt-in and never required in CI. No remote CI execution is claimed. After documentation-only edits, foundation validation passed (25 JSON artifacts, 69 Markdown documents, 57 requirements, 24 contrast pairs), the contract-reference test passed, and inventory consistency plus `git diff --check` passed.

```sh
uv run --env-file .env.local arbit-worker sleeper-sync
uv run --env-file .env.local arbit-worker sleeper-probe --season 2026 --week 7
uv run --env-file .env.local arbit-worker live-inspect --season 2026 --week 8 --events 401873023 401873026
uv run --env-file .env.local arbit-worker sources-verify
uv run --env-file .env.local arbit-worker live-replay --observation 83d65fb278c96dd8f29cadeafc88dd7236ea864f9d68a00318fa227b14e488b4 --previous 2ce55d4f02ea0aa8c73bd69aefc8401a79dd4287e3abdd45cbbfb8c97059c082
uv run arbit-worker assets-check
```

The corrected final CLI reported final 197-play/pregame success, all supplied canonical participant IDs resolved, no stale flag at acquisition, and null pregame scores. Offline verification covered **25 observations/66 unique manifest/body/normalized objects**, with 1,236 play rows across repeated captures and **zero provider requests**. Replaying the two actual 197-play captures produced zero changes. All 17 captured ESPN raw inputs passed the corrected scope parser. Source aging continues after commands exit; no automatic supplemental/live scheduler is installed. `sources-status` returns original observation/next-allowed times and safe errors without renewing them.

Unchanged actual FFA counts: one snapshot, 132 roster rows, 19,008 canonical entities, 35,505 aliases. Zero active supplemental refresh reservations. No new API listener or continuous worker was installed or left running; local PostgreSQL remains available. Recommendations remain false.

## Independent review and one fix pass

One fresh reviewer (`m1e_final_review`, gpt-6-astra/high) reviewed `2a8f35a..4223d5b`, independently ran 30 focused tests and deterministic reproductions without provider/private-state/DB mutation. Verdict: with fixes; zero Critical, four Important, one Minor. All Important findings were accepted. No second reviewer was dispatched.

| Important finding | Observed failing regression → verified fix |
| --- | --- |
| New summary/page time could restamp cached plays and undo a later correction | `test_recent_summary_does_not_renew_cached_play_provenance` and `test_mixed_page_offline_replay_cannot_revert_newer_correction` RED→GREEN. Per-play/page evidence survives live and offline construction; replay checks each play's time independently |
| Season type was neither checked nor preserved | `test_scoreboard_rejects_missing_or_wrong_season_type`, `test_scoreboard_preserves_verified_season_type` and `test_summary_cannot_contradict_requested_regular_season` RED→GREEN. Missing/wrong source type fails; scoreboard type remains in normalized scope |
| An individual play's own reference could contradict the requested event | `test_play_own_reference_cannot_relabel_foreign_or_malformed_data` RED→GREEN for foreign event/competition, different play ID, hostile/private origin and malformed type; strict public source paths are checked without fetching |
| Numeric collection reference escaped safe errors and left its reservation active | `test_malformed_collection_reference_uses_validation_boundary` and `test_malformed_reference_records_failure_and_continues_other_game` RED→GREEN. Failure records `VALIDATION_FAILED`, clears the reservation and preserves multi-game partial results |

The completed fix pass passes 25 focused and 409 full tests plus all static/contract checks. Normal task regressions also covered: nested malformed play containers and ESPN's observed `down = -1` unknown sentinel; deeply nested JSON now fails at depth 64 before recursive normalization. Numeric/unknown/source-field fidelity and non-authoritative scoring labels remain explicit.

## Rulings and review boundaries

1. Approved architecture/roadmap plus explicit M1e instruction authorize implementation without another design/stack approval. Native inline execution continues with one final reviewer. Cost if wrong: local scope/design needs revision; no external publication or irreversible action occurred.
2. Existing host native-worktree limitations remain; a clean dedicated branch reuses current private data rather than repeatedly invoking a failed helper. Manual ledger bookkeeping substitutes for CRLF helper scripts. Cost if wrong: isolation/helper provenance is weaker; actual commands/results/commits and clean branch are retained.
3. Scoped ESPN route extensions were implemented with Task 1's request builder, then consumed by Task 3, avoiding duplicate URL construction. Cost if wrong: a future adapter must maintain one registry rather than assume a separate transport.
4. Summary absence of per-play athletes does not justify narrative name matching; the separately verified public core collection supplies explicit scoped references. Cost if wrong: participant coverage remains partial and missing actors cannot drive roster attribution.
5. M1e uses a strict stale threshold at one refresh interval, while older architecture tables propose longer serving thresholds. Current operator behavior is documented; final tuning is deferred to measured serving work. Cost if wrong: conservative staleness may limit later presentation longer than necessary; no stale facts become advice.
6. Actual availability, latency and empirical counts were verified by the implementer rather than the reviewer, who excluded provider calls/private captures. Cost if wrong: live evidence lacks independent corroboration; receipts/objects/commands support later reproduction, and no reliability guarantee is claimed.
7. Full-suite/database/upgrade proof relies on actual implementer runs; the reviewer ran 30 focused tests and in-memory reproductions. Cost if wrong: database evidence has no independent duplicate run.
8. M6 fantasy scoring, rendering, SSE and persistent effective-play serving remain outside this milestone. Cost if wrong: later product work is still required; pure replay is not represented as a shipped Live experience.
9. Actual Gridiron permission authenticity and image validity were outside review: no assets/grants are present, and only prerequisite metadata is eligible. Cost if wrong: curator evidence could be inaccurate; no image can become locally ready or served through this code.
10. Final audit/status/handoff prose receives author review and artifact validation after the one code review. Cost if wrong: prose has weaker independent review than code.
11. The reviewer's earlier-route and `eligible_metadata` naming exceptions fit the recorded plan adjustments. Cost if wrong: later clients must preserve the distinction between metadata and verified media bytes, and use the shared scoped request registry.
12. Work stays on the local development branch as authorized; no optional skill integration menu or extra publication approval is necessary to finish this local milestone. Cost if wrong: the owner must separately request future push/merge/deployment; all commits remain available.

## Deferred minor

The review noted different proposed architecture versus implemented freshness windows. M1e's actual one-interval/failed-refresh policy is stated explicitly in the operator guide; choosing final longer serving thresholds remains measured M6 policy tuning. No functional policy change was added to the review fix pass. The earlier NFLverse uppercase-suffix minor remains independently recorded in known issues, with no current affected source files.

## Next stage and open gates

**M2** builds authenticated member access/team binding and the application shell/Front Office facts. Before auth implementation, choose the OIDC provider and invite/account-binding policy; preparatory UX/contracts can proceed within existing architecture. No fake projections or generic dashboard filler should substitute for the required workflows.

M3 must verify semantic stats/FFA scoring, any additional trusted Sleeper-ID bridge (direct hints cover 40/121), source availability and historical vintages/retrospective policy, features, temporal evaluation/calibration and model quality. M6 must observe active/delayed/corrected states and remaining event classes, validate fantasy attribution/corrections, persist effective events/outbox/SSE, measure full-slate timing/load, and obtain exact asset links/variants/grants plus media validation. Gridiron gaps block exact imagery, not independent text-based Live or M2. No unverified Sleeper feed or name-only mapping becomes a hidden dependency.
