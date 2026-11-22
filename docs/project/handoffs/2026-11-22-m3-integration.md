# Handoff — 2026-11-22 — M3 integration

The owner requested that outstanding code be pushed to GitHub and merged into `main`. The existing `claude/m3-model` worktree held the unpublished source, tests and documentation for the NFLverse field catalog and FFA scoring targets, the NFL injury-report capture lane, ESPN point-in-time availability and the Windows wake planner.

- **Scope.** ENG-051 and owner decisions OWN-060 through OWN-065. See the [M3 model plan](../../superpowers/plans/2026-11-09-m3-model.md), [scoring handoff](2026-11-09-m3-ffa-points.md), [catalog and targets handoff](2026-11-09-m3-slice2-catalog-targets.md) and [availability handoff](2026-11-10-m3-nfl-availability.md).
- **Local verification.** Frozen Python and JS installs, `python3 scripts/validate_foundation.py`, `make lint typecheck`, `pnpm check:contracts` and `make web-check` passed. The web suite passed 32 tests and one service-worker test.
- **Integration verification.** The local database-backed test run could not connect to the dedicated PostgreSQL service. Use the pull request's Runtime validation job for the full database suite and fictional browser flow.
- **Runtime release.** GitHub integration is the requested scope. Activating the new worker lane on the member application is a separate operational step. Keep ADR-007 and the remaining M3 backtesting and feature work open.
