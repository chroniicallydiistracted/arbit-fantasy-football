# Handoff — 2026-10-30 — Public ESPN Capability Audit

## Owner instruction and scope

Owner supplied pseudo-r/Public-ESPN-Fantasy-API and made FFA publicly viewable to test data access before selecting the final access policy. IDs remain league 1729878439 / season 2026. This session performs read-only research; it does not set an access policy, collect cookies, change league settings, run the reference service or implement production sync.

## Completed

Cloned the source to `/tmp/arbit-public-espn-api-reference` at commit `097c42f0da0b692ceb3168a2c6af1e7479be5906`. Read all 68 tracked files, including all 34 Python files and all documentation/config/build/CI files (7,104 total lines). Per-file checksums are recorded in the source-review manifest.

Ran 81 cookie-free GET probes, covering every one of the 21 documented view names, all nine upstream client request families and football-compatible companion endpoints. Explicitly tested period scoping, player status/position/rank/card filters, legacy routes, alternate scopes/domains and complete available-player pagination. No Cookie/Authorization header, stored credential or cookie jar was used.

Results: public settings 200/isPublic true; eight teams/members; 132 owned players exactly matching roster IDs; 923 available players (884 free agents, 39 waivers), four disjoint pages and zero owned overlap; 128 picks; 389 unique transactions across weeks 1–8; 46 configured scoring items. NFL completed-game sample: 25 drives, 196 play events, eight scoring plays. Core reads work anonymously; communication remains 401. Seven 404s and one unsupported IR-filter 400 are preserved. Several HTTP 200 examples omit promised data, and three legacy-domain calls return HTML; successful CDN calls return actual PNG.

## Authoritative results

- [Full audit](../../research/espn-public-api-audit-2026-10-30.md): all view/domain results, schema differences, exclusions and complete probe index.
- [Request evidence](../../research/espn-public-2026-10-30.json): exact requests, timestamps/statuses, expected-field checks, safe shape/count summaries and body hashes.
- [Complete source review](../../research/espn-reference-source-review-2026-10-30.json): audited commit and every tracked file hash.

Raw bodies and one-off probe scripts are retained locally under ignored `data/research/espn-public/2026-10-30/`; they are not committed or exposed through an application. Tracked artifacts do not copy member names/owner GUIDs, messages, contact information, article text or betting payloads. A checksum is evidence of the observed body, not a substitute for preserving credentials safely or proof of future provider availability.

## Verification

Evidence construction asserted every logged request is GET with no auth/cookie headers; body SHA-256 matches each local raw file; case IDs are unique; all 21 catalog views and nine client request families are covered; available-player pagination terminates on a short page without duplicate/owned overlap; all 389 transaction IDs are unique and periods match requests. CDN responses have PNG signatures. Foundation/document checks are run at handoff; application code and dependencies were unchanged, so no unrelated application-suite rerun is claimed.

## Continue from here

Owner can choose public/private source visibility using the audit. Public mode suffices for the core endpoints tested, while the message board remains denied. The included Django service is a self-hosted reference; approved Arbit architecture stays intact. Next implementation work is observed-payload contracts/sanitized fixtures, a bounded read adapter, actual FFA rule mapping/reconciliation, robust sync and canonical mappings. No production integration, model validity or full M1b completion is implied by this manual audit. If visibility returns private, configure and test local server-side credentials then; never request them in chat.
