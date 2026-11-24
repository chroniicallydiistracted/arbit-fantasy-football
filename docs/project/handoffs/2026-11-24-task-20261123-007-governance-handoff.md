# Task handoff — TASK-20261123-007 — R-072 repair: one code per franchise across nflverse tables, rebuilt FFA targets, repaired reruns; R-074 regular-season gamebooks

Status at authoring: implementation pending governance finish gate. Not a deployment claim.

**Objective:** Owner instruction 2026-11-23: fundamental data defects are necessary repairs, not decisions. Map every nflverse team code to one franchise code (OAK/SD/STL relocations and the 2012-2015 roster codes ARZ/BLT/CLV/HST/SL) at the targets, gamebook and team-feature boundaries, with a fail-closed check that every row's team is one of its game's two teams. Rebuild the canonical FFA targets from the same pinned nflverse inputs as index 4afbd836 so the difference is the repair alone, classify every changed row, keep the old index readable so v0 reproduces, rerun the signal study's team rates with the repair (its file stays byte-identical), update the team shrinkage constants it supplies, restrict gamebooks to regular seasons (R-074), and rerun the DvP phase 1 audit on the repaired index. Offline research store only: no service, deployment or live advisor change.

**Requirements:** MD-002, MD-004, DATA-002, GOVAI-013

**Change class:** model

**Scoped files:** libs/arbit-model/src/arbit_model/teams.py, libs/arbit-model/src/arbit_model/targets.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/src/arbit_model/feature_specs.py, libs/arbit-model/src/arbit_model/dvp/observations.py, libs/arbit-model/tests/test_teams.py, libs/arbit-model/tests/test_model_targets.py, libs/arbit-model/tests/test_gamebook.py, libs/arbit-model/tests/test_team_features.py, libs/arbit-model/tests/test_dvp_continuity.py, libs/arbit-model/tests/test_dvp_observations.py, libs/arbit-model/README.md, scripts/model/build_targets.py, scripts/model/targets_diff.py, scripts/model/ffa_signal_study_r072.py, scripts/model/dvp.py, config/dvp/base.json, docs/research/ffa-signal-study-2026-11-23-r072.json, docs/research/targets-repair-r072.md, docs/research/targets-repair-r072.json, docs/research/team-features-2026-11-23.md, docs/research/dvp/README.md, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md, docs/research/dvp/v0-reproduction.json, docs/research/dvp/audit-receipt.json, docs/research/dvp/SCORE_FINALITY_AUDIT.json, docs/research/dvp/PROJECTION_EXCLUSION_AUDIT.json, docs/research/dvp/continuity-manifest.json, docs/research/dvp/experiment-registry.json, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/project/known-issues.md, docs/project/decision-register.md, docs/project/status.md, docs/project/changelog.md, docs/superpowers/plans/2026-11-09-m3-model.md, docs/governance/state.json

## Review

Read targets.py, gamebook.py, team_features.py, timing.py, build_targets.py, ffa_signal_study.py, dvp.py and the DvP config. Surveyed team codes in every nflverse table 2012-2026: the schedule uses OAK 2012-2019, SD 2012-2016, STL 2012-2015; play-by-play and player/team statistics use LV, LAC, LA throughout; snap counts follow the schedule; 2012-2015 weekly rosters use ARZ, BLT, CLV, HST and SL. targets.py compares schedule codes with statistics codes (opponent, D/ST team rows) and roster codes (participation); gamebook._team_games and team_features join schedule codes with statistics codes. The signal study and v0 are byte-locked (T29), so their repair is a rerun that leaves the files unchanged. R-072 is wider than recorded (STL 2012-2015, roster-based participation labels for five teams).

Files: libs/arbit-model/src/arbit_model/targets.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, scripts/model/build_targets.py, scripts/model/dvp.py, config/dvp/base.json

## Plan

1) arbit_model.teams: FRANCHISE map (OAK->LV, SD->LAC, STL->LA; roster codes ARZ->ARI, BLT->BAL, CLV->CLE, HST->HOU, SL->LA), franchise() and a polars expression. 2) targets.py normalizes every team field of SeasonRows (schedule, plays, statistics, snaps, rosters) and refuses (TeamCodeError) a statistics or team row whose franchise is not one of its game's two teams. 3) gamebook and team_features map schedule codes; gamebooks read regular-season games only (R-074). 4) build_targets.py --inputs-of INDEX pins every manifest an earlier index read and --set-current moves the pointer for a repair build; targets_diff.py classifies every changed row between two indexes. 5) Rebuild 2012-2026 pinned to 4afbd836, diff, require every change to touch a relocated or roster-coded team. 6) ffa_signal_study_r072.py reruns the locked study with pinned manifests and franchise-mapped schedules; update the eight TEAM shrinkage constants. 7) DvP: targets_index moves to the repaired index, v0_targets_index keeps 4afbd836, reproduce-v0 stages a pointer to the old index so v0 still reproduces; rerun phase 1 audit. 8) Tests, records, docs.

Files: libs/arbit-model/src/arbit_model/teams.py, libs/arbit-model/src/arbit_model/targets.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, scripts/model/build_targets.py, scripts/model/targets_diff.py, scripts/model/ffa_signal_study_r072.py, scripts/model/dvp.py, config/dvp/base.json

## Implement

arbit_model.teams (FRANCHISE incl. 2012-2015 roster codes, franchise_row/columns); targets.py maps every SeasonRows table and refuses rows whose team is not in its game (TeamCodeError), format v2; gamebook maps codes and reads REG only (R-074); team_features maps schedule context; dvp/observations imports the shared map. build_targets.py --inputs-of/--set-current/--reason; targets_diff.py classifies differences with per-season expectations; ffa_signal_study_r072.py reruns the locked study pinned and franchise-mapped. Rebuilt index 6ffb62fb (twice, identical; 0 unexplained differences; receipt docs/research/targets-repair-r072.json). Signal study rerun (320 team-seasons) feeds the 8 team shrinkage constants. DvP: config targets_index=6ffb62fb, v0_targets_index=4afbd836; reproduce-v0 stages a pointer for v0; audit phase1-audit-20261124T021910Z all checks pass, D/ST 5,278 valid; v0 rerun exact; registry regenerated. Tests: 6 new (targets relocation equivalence, roster codes, stray teams refused, team map, gamebook relocation, gamebook playoffs), each fails when its fix is removed.

Files: libs/arbit-model/src/arbit_model/teams.py, libs/arbit-model/src/arbit_model/targets.py, libs/arbit-model/src/arbit_model/gamebook.py, libs/arbit-model/src/arbit_model/team_features.py, libs/arbit-model/src/arbit_model/feature_specs.py, libs/arbit-model/src/arbit_model/dvp/observations.py, scripts/model/build_targets.py, scripts/model/targets_diff.py, scripts/model/ffa_signal_study_r072.py, scripts/model/dvp.py, config/dvp/base.json, libs/arbit-model/tests/test_teams.py, libs/arbit-model/tests/test_model_targets.py, libs/arbit-model/tests/test_gamebook.py

## Validate

Checks: foundation, model tests (98), the full Python suite, ruff, mypy, all exit 0. Data: two pinned rebuilds produced identical season manifests; targets_diff over 2012-2026 returned EXPLAINED with 0 unexplained differences (2020-2026 byte-identical; no player line's points changed). DvP audit phase1-audit-20261124T021910Z: every check PASSED, 5,278 team-games, D/ST 5,278 valid, 0 opponent mismatches, 0 missing D/ST lines. v0 rerun exact on 4afbd836 and the independent recompute matches 12 of 12. Signal study rerun read exactly the original manifests (asserted). Mutation: removing the REG filter fails test_r074; removing the gamebook franchise map fails test_r072.

Files: libs/arbit-model/tests/test_teams.py, libs/arbit-model/tests/test_model_targets.py, libs/arbit-model/tests/test_gamebook.py, docs/research/targets-repair-r072.json, docs/research/dvp/audit-receipt.json, docs/research/dvp/v0-reproduction.json, docs/research/ffa-signal-study-2026-11-23-r072.json

## Document

targets-repair-r072.md (defect, repair, rebuild and diff table, reruns, reproduction commands); DvP README, DATA_QUALITY, V0_REPRODUCTION, EXPERIMENT_REGISTRY updated to the repaired index; 3b note corrections (R-072, R-074, relabeled column); decision register OWN-075 and ENG-058; known issues R-072 and R-074 resolved; status, changelog, M3 plan and libs/arbit-model README.

Files: docs/research/targets-repair-r072.md, docs/research/dvp/README.md, docs/research/dvp/DATA_QUALITY.md, docs/research/dvp/V0_REPRODUCTION.md, docs/research/dvp/EXPERIMENT_REGISTRY.md, docs/research/team-features-2026-11-23.md, docs/project/decision-register.md, docs/project/known-issues.md, docs/project/status.md, docs/project/changelog.md, docs/superpowers/plans/2026-11-09-m3-model.md, libs/arbit-model/README.md

## Recorded commands

- `foundation`: exit=0, 2026-11-24T02:23:10Z; argv=["python", "scripts/validate_foundation.py"]; output SHA-256=204bfcd94fba63d59bd8290ac43429df5352c3ef8b4e26d0e00b26a43cb4c9e1
- `model-tests`: exit=0, 2026-11-24T02:23:20Z; argv=["uv", "run", "pytest", "libs/arbit-model/tests"]; output SHA-256=9a49ced83884b12225a2595e5a25ab44b97a7be5f3f654b8e99931ddcdf76285
- `lint`: exit=0, 2026-11-24T02:23:21Z; argv=["uv", "run", "ruff", "check", "."]; output SHA-256=e83204db783718300b1d1f1af1f60eb1a350f4140d5c653994fb67bc65273b1d
- `types`: exit=0, 2026-11-24T02:23:21Z; argv=["uv", "run", "mypy", "libs/arbit-model/src", "scripts/model/dvp.py", "scripts/model/build_targets.py", "scripts/model/targets_diff.py", "scripts/model/ffa_signal_study_r072.py"]; output SHA-256=bfe68eeda4b395a659102ac01a1d7cc8c48c5a2ea08ac09714f9ce1731a87089
- `python-suite`: exit=0, 2026-11-24T02:24:29Z; argv=["uv", "run", "pytest", "-q"]; output SHA-256=6a0cde3721a3783a66cbb3b1bd55ec2ecd2e388532d6a483a16691bd0cc98e37
- `point-in-time`: exit=0, 2026-11-24T02:24:44Z; argv=["uv", "run", "pytest", "libs/arbit-data/tests/test_nfl_availability.py", "tests/integration/test_nflverse_provenance.py"]; output SHA-256=a30913a54bdf384cc04084e5a47831bdb846d6940087bb8837fc9152fd585c7c

## Findings / decisions / contradictions

- None

## Remaining unresolved / blocked

feature_specs dvp_* constants stay v0's until the DvP Phase B decision (OWN-074). The 3b team-features audit receipt (2026-11-23) predates R-074; its current-season values are unaffected and its prev_* values included playoff games. NWS User-Agent contact still needed before weather W3.

## Next executable action

Merge the R-072 repair PR (branch claude/r072-franchise-codes). Then DvP Phase 2 per OWN-074 on targets index 6ffb62fb: A00, A02-A10, A12 with scatter plots and RELIABILITY_REPORT, then Phase 3 starting with the offense-only B00.

## Release truth

No production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.
