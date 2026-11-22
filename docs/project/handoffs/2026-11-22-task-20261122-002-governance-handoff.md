# Task handoff — TASK-20261122-002 — Restore and harden local runtime: database restart policy, availability lane activation, branch protection, global guidance

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** The database comes back by itself after Docker or Windows restarts, the running worker runs the merged availability lane, week 11 NFL games are linked, main requires CI, and both agents load the shared global guidance

**Requirements:** GOVAI-011, GOVAI-018, GOVAI-020, DATA-008

**Change class:** ops

**Scoped files:** infra/compose.yaml, docs/engineering/member-application.md, docs/project/known-issues.md, docs/governance/state.json, docs/project/status.md, docs/project/changelog.md

## Review

Observed 2026-11-22: arbit-dev-postgres-1 exited (code 0) 2026-11-10T18:06:08Z with restart policy 'no' and stayed down until docker start at 22:44:49Z; the worker logged DATABASE_UNAVAILABLE throughout (first at 2026-11-10 18:06:09Z). The running worker (started 15:25:34 MST) predates local main's fast-forward to the M3 merge (15:26:36 MST), so it lacks the availability lane; daemon.LANES now includes it by default and the unit passes no --lanes. NFL discovery ran 22:44:52Z, 6 s before ESPN created week 11 nfl_game rows (22:44:58Z), so all 13 week 11 nfl_api_game rows have event_id NULL and NFL details are not read until the next discovery 6 h later. GitHub main has no branch protection or rulesets. ~/.claude/CLAUDE.md is absent; ~/.codex/AGENTS.md is 0 bytes.

Files: infra/compose.yaml, services/worker/src/arbit_worker/daemon.py, libs/arbit-data/src/arbit_data/live/nfl_feed.py, docs/engineering/member-application.md, docs/project/known-issues.md, scripts/install_global_instructions.py

## Plan

Owner authorized fixing all identified current-state issues (2026-11-22 chat). Steps: (1) docker update --restart unless-stopped on arbit-dev-postgres-1 (no downtime) and set restart: unless-stopped in infra/compose.yaml so a recreated container keeps it; (2) install the generic global templates with scripts/install_global_instructions.py --apply --replace (backs up the empty Codex file); (3) restart arbit-worker only between the late games' end and Sunday night's kickoff, never mid-game, so it loads main (ec5682a: availability lane) and rediscovers week 11; verify journal 'started' lanes, links and availability capture; (4) protect main on GitHub requiring Foundation validation, Runtime validation and Context governance, enforce_admins off so the owner can still push. Rollback: docker update --restart no; delete installed files / restore .backup; systemctl --user restart arbit-worker after git checkout of the previous commit is not needed (no code change); DELETE branch protection via gh api.

Files: infra/compose.yaml, docs/engineering/member-application.md, docs/project/known-issues.md

## Implement

Applied: docker update --restart unless-stopped and infra/compose.yaml restart: unless-stopped; global templates installed (Codex empty file backed up); main branch protection (validate, runtime, governance; enforce_admins false; no force push or deletion). Worker restarted 23:43:25 UTC on main ec5682a: lanes league, live, nfl, nfl_probe, statistics, availability started; NFL discovered 13 games, all linked, 11 details read; availability captured 23:43:37 UTC with 0 failures. Catch-up verified on restored copy arbit_catchup_test (14 recovered, 0 failed, 14 NFL finals, 2550 play revisions, receipt mode 600), then run on arbit_local with the worker stopped 23:45:55-23:46:20 UTC (14 recovered, 0 failed, nothing remaining); copy dropped. Docs: R-029, R-068, R-069 outcomes, status, changelog.

Files: infra/compose.yaml, docs/project/known-issues.md, docs/engineering/member-application.md

## Validate

Observed exit 0: foundation and governance doctor. Runtime evidence: journal lines show all six lanes started and no errors after both restarts; database queries show week 10 with 14 games, 14 summaries, 14 NFL finals and final_checks 3, and week 11 with 13 of 13 linked; the live schedule stays on week 11; data/catchup/receipts.jsonl is mode 600 in a 700 directory.

Files: not separately listed

## Document

Status 'Running app repaired' block, changelog entry, R-029 restart-policy done, R-068 recovery results, R-069 runtime relink, governance state next action and source.

Files: docs/project/status.md, docs/project/changelog.md, docs/project/known-issues.md, docs/governance/state.json

## Recorded commands

- `foundation`: exit=0, 2026-11-22T23:47:04Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=a8055fd5157531ee9e92a6d1dfd56e48c40994280c6d1ea411be89acafee17f6
- `governance`: exit=0, 2026-11-22T23:47:04Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a
- `foundation`: exit=0, 2026-11-22T23:47:16Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=a8055fd5157531ee9e92a6d1dfd56e48c40994280c6d1ea411be89acafee17f6
- `governance`: exit=0, 2026-11-22T23:47:16Z; argv=["python", "scripts/governance.py", "doctor"]; output SHA-256=828a81d5d73f64c19b1857df41ebf03677d9c68bf0b30966137359239adc446a

## Findings / decisions / contradictions

- 2026-11-22T23:11:59Z [observation] Database outage 2026-11-10T18:06:08Z to 2026-11-22T22:44:49Z (about 12.2 days). No ESPN league reads, live game captures, NFL API reads or nflverse imports were stored then; week 10's 14 games have no stored record. — docker inspect FinishedAt/StartedAt; journalctl --user -u arbit-worker; read-only query of nfl_schedule_game vs nfl_game
- 2026-11-22T23:12:39Z [observation] Applied while waiting: arbit-dev-postgres-1 restart policy unless-stopped (docker update, no downtime); global templates installed (~/.claude/CLAUDE.md new, ~/.codex/AGENTS.md replaced; empty original kept as AGENTS.md.backup-20261122T231209Z); main protected requiring checks validate, runtime, governance with enforce_admins false, force pushes and deletion off. — docker inspect RestartPolicy=unless-stopped; install_global_instructions.py output; gh api PUT branches/main/protection response
- 2026-11-22T23:12:39Z [risk] Worker restart must wait for the gap between Sunday's late games ending (~17:20 MST) and Sunday night kickoff (18:20 MST); no mid-game restarts — blocking condition
- 2026-11-22T23:43:27Z [observation] Owner, 2026-11-22: no one else uses the app yet; free to stop, restart, rebuild and start the stack as needed, without waiting for live games. The mid-game wait in this task's plan is dropped. — Owner message in the 2026-11-22 Claude session

## Remaining unresolved / blocked

No alert when the database or a source stays down for hours (R-068). Q-016 weather forecast awaits the owner. Weeks 1-7 were never captured; recoverable with arbit-worker catchup --from-period 1 if wanted.

## Next executable action

Push branch claude/catch-up-and-decisions and open the PR; when validate, runtime and governance pass, merge, fast-forward the main checkout and restart arbit-worker so the catchup lane and fixes run (confirm a catchup 'started' line).

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
