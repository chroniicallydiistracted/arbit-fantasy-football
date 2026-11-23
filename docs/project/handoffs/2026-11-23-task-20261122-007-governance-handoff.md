# Task handoff — TASK-20261122-007 — Record OWN-069 to OWN-071: weather intelligence (ADR-008), remote-server alerting, weeks 1-7 capture

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** The owner's weather decision is an accepted ADR with a verified multi-source plan that keeps forecasts point-in-time, the alerting decision and weeks 1-7 capture are recorded, and all policy surfaces name weather as the second exception to nflverse-only inputs

**Requirements:** MD-002, MD-004, LN-002, LN-003, GOVAI-003, GOVAI-013, GOVAI-014

**Change class:** docs

**Scoped files:** AGENTS.md, docs/project/decision-register.md, docs/architecture/decisions/008-weather-intelligence.md, docs/architecture/decisions/README.md, docs/research/weather-sources-2026-11-22.md, docs/research/source-register.md, docs/superpowers/plans/2026-11-22-weather-intelligence.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, .claude/rules/model-integrity.md, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Owner reply 2026-11-22: Q-016 yes for non-closed stadiums, via a multi-source weather intelligence system (Open-Meteo, NOAA RRFS, NWS/NBM, ECMWF/AIFS, NOAA historical/Meteostat), refreshed as kickoff nears, little weight indoors; owner findings: RRFS operational 2026-11-03 and observed vs forecast weather must not be mixed. Alerting deferred to a remote 24/7 server; weeks 1-7 captured by the worker; housekeeping last. Verified (web, 2026-11-22/23): SCN 26-48 updated and SCN 26-89 set RRFS/REFS live 2026-11-03 12 UTC replacing NAM, HREF, SREF, HiresW; HRRR stays (correction to the owner's note); NOMADS prod paths observed 2026-11-23: nam 404, rrfs 200, hrrr 200. Open-Meteo free tier non-commercial, <10k/day, 5k/h, 600/min, CC BY 4.0; Previous Runs API from Jan 2024; Single Runs ECMWF IFS from Mar 2024, others from 2026-04-02. ECMWF open data CC-BY-4.0, AIFS free, AWS replica. NWS API no key, User-Agent with contact required. NBM on AWS noaa-nbm-grib2-pds, text bulletins. GHCNh replaces ISD. Meteostat licence statements conflict (CC BY vs CC BY-NC). nflverse play_by_play: roof and surface pre-game, stadium_id identity, temp and wind after the game; no venue coordinates in the repo.

Files: docs/project/decision-register.md, docs/architecture/decisions/006-model-architecture.md, docs/architecture/decisions/007-model-availability.md, libs/arbit-model/src/arbit_model/nflverse_fields.json, AGENTS.md, docs/research/source-register.md

## Plan

Decision rows OWN-069 (weather intelligence, quoted), OWN-070 (alerting waits for a remote 24/7 server; owner keeps the PC awake), OWN-071 (weeks 1-7 captured by the worker); Q-016 resolved; ADR-008 accepted by OWN-069 with point-in-time forecast rules, roof handling and source roles; research note with verified facts and sources; SRC-34 to SRC-38; implementation plan W1-W6; AGENTS.md invariant names OWN-063 and OWN-069 as exceptions; plan, roadmap, R-063, R-068, charter and model rule updated. No code in this task.

Files: AGENTS.md, docs/project/decision-register.md, docs/architecture/decisions/008-weather-intelligence.md, docs/architecture/decisions/README.md, docs/research/weather-sources-2026-11-22.md, docs/research/source-register.md, docs/superpowers/plans/2026-11-22-weather-intelligence.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, .claude/rules/model-integrity.md

## Implement

New: ADR-008 (accepted by OWN-069) with source roles, point-in-time record, lead-time captures, roof weighting, effects-then-apply, venue provenance, supervision; research note with verified facts, evidence grades and sources (RRFS live, NAM gone, HRRR stays; Open-Meteo terms and archives; NWS UA; NBM, ECMWF, GHCNh, Meteostat); weather plan W1-W6. Register: OWN-069, OWN-070, OWN-071, Q-016 resolved; SRC-34 to SRC-38. AGENTS.md invariant names OWN-063/064 and OWN-069 exceptions; ADR index, charter, model rule, R-063, R-068, M3 plan, roadmap, status and changelog updated.

Files: AGENTS.md, docs/project/decision-register.md, docs/architecture/decisions/008-weather-intelligence.md, docs/architecture/decisions/README.md, docs/research/weather-sources-2026-11-22.md, docs/research/source-register.md, docs/superpowers/plans/2026-11-22-weather-intelligence.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/project/roadmap.md, docs/project/known-issues.md, docs/governance/FANTASY_ADVISOR_CHARTER.md, .claude/rules/model-integrity.md

## Validate

Observed exit 0: foundation validator (links resolve, including the new ADR, research note and plan) and governance doctor. External facts carry their evidence grade in the research note; the NOMADS status codes were observed 2026-11-23 about 00:00 UTC with empty bodies, so directory contents were not read.

Files: not separately listed

## Document

Status block and changelog entry for the decisions and the weather plan. Written before validation; unchanged since.

Files: docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-23T00:23:01Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=5bd8626be0d21e3fa4293ec39f8509c57aa6150d5601d07b4115448673d744b2
- `governance`: exit=0, 2026-11-23T00:23:01Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a

## Findings / decisions / contradictions

- 2026-11-23T00:23:09Z [correction] The owner's note said older pipelines built on HRRR or NAM need to account for their retirement. NAM retired with RRFS on 2026-11-03, but HRRR stays in operations until a later RRFS upgrade. — NOAA GSL RRFS page; NWS RRFS webinar Q&A 2026-06-25; NOMADS hrrr/prod 200 on 2026-11-23
- 2026-11-23T00:23:09Z [question] NWS API requires a User-Agent with contact information; the owner chooses the contact, kept in .env.local (weather plan W3). — NWS API documentation (SRC-36)

## Remaining unresolved / blocked

NWS User-Agent contact awaits the owner. Weather sources are documented, not yet read by Arbit except NOMADS status codes.

## Next executable action

Capture weeks 1-7 (TASK-20261122-008), then weather W1 (venue table and forecast record) beside M3 slice 3.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
