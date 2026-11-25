# Task handoff — TASK-20261124-010 — M3-3 final directive: audit reconciliation and prospective operations (Phase A)

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Reconcile every external audit finding of the owner's final M3-3 directive in a durable register; correct the prospective completion gate, archive transactions and recovery, data readiness, observed availability capture and external evidence publication (AUD-01a-d, PB-AUD-07); declare the evaluation-integrity amendment before the week-12 kickoff; install and verify the owner-authorized timer (DEC-02).

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** docs/research/dvp/M3-3_AUDIT_REMEDIATION_AND_COMPLETION_DIRECTIVE_FINAL.md, docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/audit-findings.json, config/dvp/prospective-amendment-1.json, libs/arbit-model/src/arbit_model/dvp/window.py, libs/arbit-model/src/arbit_model/dvp/archive.py, libs/arbit-model/src/arbit_model/dvp/evidence.py, libs/arbit-model/tests/test_dvp_window.py, libs/arbit-model/tests/test_dvp_archive.py, libs/arbit-model/tests/test_dvp_evidence.py, libs/arbit-model/tests/test_dvp_shadow.py, scripts/model/dvp_prospective.py, scripts/model/dvp.py, infra/systemd/arbit-dvp-prospective.service.template, infra/systemd/arbit-dvp-prospective.timer.template, infra/systemd/install-dvp-prospective.sh, docs/research/dvp/PROSPECTIVE_2026.md, docs/research/dvp/prospective/2026/README.md, docs/research/dvp/README.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/governance/state.json, scripts/model/dvp_plan_audit.py, libs/arbit-model/src/arbit_model/dvp/league.py, docs/project/handoffs/2026-11-25-task-20261124-010-governance-handoff.md

## Review

Read the owner's final directive in full (1,689 lines). Reconciled Phase A findings against the code at 2e2520f, the live database and GitHub: the service template exported locally only (AUD-01a); readiness accepted a completed game with any line and named no cause (AUD-01b); evaluate counted a week complete on any completed game and accepted MISSED weeks, as the original declaration allowed (AUD-01c); write_once had staging and atomic rename but no fsync, lock, archivedAt or recovery, and a crash after the rename would block the week until its cutoff (AUD-01d); week 12's capture labelled 19 unowned D/STs free agents while ESPN reported all 19 on waivers in the same snapshot, freeAgents held every unowned unit, empty teams were absent and claimable-only evaluation was skipped without free agents (PB-AUD-07). Host: WSL2 with linger on; the Windows wake task wakes the PC at 00:10 and 16:55 UTC daily and starts WSL; powershell.exe interop works from systemd services. Only waiver claims carry processed_at (52/52 executed).

Files: docs/research/dvp/M3-3_AUDIT_REMEDIATION_AND_COMPLETION_DIRECTIVE_FINAL.md, scripts/model/dvp_prospective.py, infra/systemd/arbit-dvp-prospective.service.template

## Plan

1) Register every external finding (audit-findings.json, AUDIT_RECONCILIATION.md). 2) Before the week-12 kickoff: declare and push prospective amendment 1 with the completion gate (window.py) and tests. 3) archive.py (lock, fsync, atomic rename, archivedAt, recovery) with failure injection. 4) evidence.py (sanitized commitment, dedicated clone and branch, read-back, GitHub activity timestamp) and publications.jsonl; record week 12's prior push. 5) Per-game readiness states. 6) League capture v2 (one snapshot, every team, observed availability, contradictions, labelled fallback), decision-time captures, week-12 supplement, four evaluation kinds. 7) status.json, alerts (journal, alerts.jsonl, Windows notification), self-retiring timer bounded to the window. 8) Docs, OWN-077, ENG-067. 9) Merge, then install the timer from main and verify the chain.

Files: config/dvp/prospective-amendment-1.json, libs/arbit-model/src/arbit_model/dvp/window.py, libs/arbit-model/src/arbit_model/dvp/archive.py, libs/arbit-model/src/arbit_model/dvp/evidence.py

## Implement

window.py (archive_state, label_state, window_state, game_readiness); archive.py (exclusive, commit, self_consistent, recover); evidence.py (commitment, publish, verify_remote, read_activity, external_timestamp); dvp_prospective.py: league_capture v2, statistics_revisions, run_forecast via archive.commit with archivedAt and cutoff check, recover_archive, sweep with lock, status.json, alerts, capture_pending, publish_pending, retire_if_done; commands publish, record-prior, supplement; evaluate through the gate with league_week (rosterOnly, unownedPool, claimablePool, claimableWithWaivers); export without league.json. league.py without_decision. Unit templates (UTC calendar bounded to 2027-01-15, EnvironmentFile for evidence settings) and installer (linger check, key creation, registration check). Live: record-prior week 12 verified (23:13:15Z); evidence branch commitment 959ff9e verified (03:46:49Z); week-12 supplement (13 OWNED, 19 WAIVERS); sweep OK (week 13 waiting on 16 games, week-12 decision-time capture).

Files: scripts/model/dvp_prospective.py, libs/arbit-model/src/arbit_model/dvp/league.py, infra/systemd/install-dvp-prospective.sh, infra/systemd/arbit-dvp-prospective.timer.template

## Validate

All seven checks pass (foundation, model-tests, point-in-time, ruff check, ruff format, mypy on arbit-model and six model scripts, pytest -q full suite). Model suite 255 passed, 2 skipped (real-artifact tests need the main machine's audit run). New tests: test_dvp_window.py 15 (completion gate cases the directive lists, readiness states, amendment hash), test_dvp_archive.py 12 (failure injection, killed processes, concurrency, quarantine, fsync), test_dvp_evidence.py 6 (local bare remote: publish, read back, idempotence, failed push retried, mismatch, activity timestamp, harness retry). Live, against main's archive: week-12 prior push verified (GitHub 23:13:15Z, bytes equal the ledger); evidence-branch commitment verified (03:46:49Z, before the 2026-11-26 01:00Z cutoff); supplement from week 12's snapshot; sweep OK in 6 s; alert shown on Windows from a systemd user service; database sessions refuse writes (ReadOnlySqlTransaction). Not yet verified: unattended publication with the deploy key (needs the owner's registration) and the timer's first scheduled run (after merge and install).

Files: libs/arbit-model/tests/test_dvp_window.py, libs/arbit-model/tests/test_dvp_archive.py, libs/arbit-model/tests/test_dvp_evidence.py

## Document

AUDIT_RECONCILIATION.md and audit-findings.json (every finding: assertion, requirement, implementation at 2e2520f, evidence, tests, disposition, reasoning, remediation, expected effect, criteria, status); config/dvp/prospective-amendment-1.json; PROSPECTIVE_2026.md (readiness states, capture v2, archive transaction, commitments, decision-time captures, export, completion gate, evaluation kinds, operations and manual procedures); prospective/2026/README.md; DvP README; decision register OWN-077 (DEC-01..10) and ENG-067; status; changelog; next action.

Files: docs/research/dvp/AUDIT_RECONCILIATION.md, docs/research/dvp/audit-findings.json, docs/research/dvp/PROSPECTIVE_2026.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md

## Recorded commands

- `foundation`: exit=0, 2026-11-25T03:53:49Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6684f5112f7353d009645ebfa430777caa05f53a0693b69d542eac8c73156fd8
- `model-tests`: exit=0, 2026-11-25T03:54:03Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=c8a715f05da16c313053355ad6e03c6cd632f188e2ac6e5c9a8383f785d5082b
- `point-in-time`: exit=0, 2026-11-25T03:54:05Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=cb4e11ed239734bbd9543410fe59dc0424c682806a553e1bfc957dd0096c789e
- `lint`: exit=0, 2026-11-25T03:54:05Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=98733c3446b52dc3e6b6943142b19a142025d9727521f6abc3783a20e4b6d3c6
- `format`: exit=0, 2026-11-25T03:54:05Z; argv=["uv", "run", "ruff", "format", "--check", "."]; output SHA-256=678b3ca6820a0d323f54a957cc1e4426487b2bdba16694b72c6fe03386fc1d1f
- `types`: exit=0, 2026-11-25T03:54:06Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/dvp_plan_audit.py", "scripts/model/dvp_prospective.py", "scripts/model/dvp_explore.py", "scripts/model/dvp_league_2026.py", "scripts/model/ffa_2026_inventory.py"]; output SHA-256=094d5faea38caab5b121438faceb9e3af7a84f183aa86fbfc6fadc65887e2ce6
- `python-suite`: exit=0, 2026-11-25T03:55:18Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=714ea9182817bfc2d40aaa1dcce12d947e0ef9b30dd9070bd8e677c61413b3dc
- `foundation`: exit=0, 2026-11-25T03:55:32Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6684f5112f7353d009645ebfa430777caa05f53a0693b69d542eac8c73156fd8
- `model-tests`: exit=0, 2026-11-25T03:55:47Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=12d57ca4cc22bb5145d9c25d350cf66f1ee6b933aad2c9d0cc409ae3e2b1f09a
- `point-in-time`: exit=0, 2026-11-25T03:55:48Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=82c4d9265a9642bb3d19c42a3087937bdfbd6ce79824c8c82baaabfa54efa913
- `foundation`: exit=0, 2026-11-25T03:55:55Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6684f5112f7353d009645ebfa430777caa05f53a0693b69d542eac8c73156fd8
- `model-tests`: exit=0, 2026-11-25T03:56:10Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=c13be1380cd730e181542e9792ca210b29d06fcb1608b722212b101b731aee2f
- `point-in-time`: exit=0, 2026-11-25T03:56:12Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=9bf0a272ba321253b6d3b3be9fbcec107ace1dcfc9d2bdffa7ab99ddb6ca1dec
- `foundation`: exit=0, 2026-11-25T03:56:19Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=6684f5112f7353d009645ebfa430777caa05f53a0693b69d542eac8c73156fd8
- `model-tests`: exit=0, 2026-11-25T03:56:33Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=63d1d974f659d140d3dd8044bacfdc85146d22f9ff786ed6536caf9f33210521
- `point-in-time`: exit=0, 2026-11-25T03:56:35Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=1a3d161ab6a2f5c2c1f7f8349dac764c6a649bb5bef7d2cbf143c08c2ad2287b

## Findings / decisions / contradictions

- 2026-11-25T03:53:31Z [correction] Scope extended by hand: dvp_plan_audit.py (its league-capture check named a removed source line), league.py (without_decision helper for the league evaluation) and the dated handoff path. — scripts/model/dvp_plan_audit.py
- 2026-11-25T03:55:31Z [decision_proposed] Owner: register ~/.config/arbit/research-evidence/id_ed25519.pub as a write deploy key for this repository (gh repo deploy-key add ... --allow-write). The session's permission classifier refused the registration. Until then the timer's commitments fail, alert and retry; week 13's must be verified before 2026-12-04 01:15 UTC to count. — infra/systemd/install-dvp-prospective.sh
- 2026-11-25T03:55:31Z [assumption] A week counts as prospective only with a verified external commitment before its cutoff (amendment 1). This is stricter than the original declaration; it follows the directive's AUD-01a requirement to publish a commitment before the cutoff, under DEC-03. — config/dvp/prospective-amendment-1.json

## Remaining unresolved / blocked

Deploy key registration (owner). PB-AUD-01..06, -08, PB-RESULTS, AUD-06, AUD-07 open in audit-findings.json.

## Next executable action

Merge the Phase A PR after CI, then install the timer from main (sh infra/systemd/install-dvp-prospective.sh) and verify a scheduled run. Owner registers the evidence deploy key. Then Phase B corrections (PB-AUD-01..06, -08), AUD-06, AUD-07, eligibility registry, remediation 7.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
