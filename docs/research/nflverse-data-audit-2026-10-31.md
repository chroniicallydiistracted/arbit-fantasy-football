# NFLverse full catalog and local import audit

Observed **2026-10-31**. M1d is implemented and locally verified. Every selected logical file in the discovered source surface succeeded: **1,140 files across 28 families**, comprising **1,087 Parquet tables with 11,973,952 stored rows**, plus **53 archive-only originals/metadata/reference files**. These row totals include distinct source variants and overlapping aggregations; they are not a count of unique combined NFL events. Recommendations remain disabled.

## Scope and reproducibility

The [official nflreadr loader catalog](https://nflreadr.nflverse.com/reference/index.html) and full loader source were inspected at [commit 23f915a5be30415aeaa0c5c80cd23b2c69cda122](https://github.com/nflverse/nflreadr/tree/23f915a5be30415aeaa0c5c80cd23b2c69cda122/R). Discovery exhausts paginated releases from [nflverse-data](https://github.com/nflverse/nflverse-data/releases), [ffopportunity](https://github.com/ffverse/ffopportunity/releases) and the commit-pinned DynastyProcess files exposed by those loaders. All 25 core release groups and the three exposed ffverse families are represented. Scope means the complete discovered published catalog, not every possible unpublished or externally hosted football dataset.

The catalog contains 4,764 physical representations. One preferred representation per logical stem was imported: Parquet, compressed CSV, CSV, RDS, QS, JSON, then text. Statistical subtypes, historical seasons, summaries, legacy variants and diagnostic/reference files remain separate. Alternate serialization mirrors remain cataloged rather than redundantly downloaded. The 1,140 selected originals total **1,380,778,711 bytes**. Two ffopportunity model ZIPs (`latest-model` and `v1.0.0-model`) are explicitly excluded as model artifacts, not omitted observations; neither is executed. Data ZIPs are preserved intact as archive-only objects, alongside their queryable annual tables; ZIP payloads are not separately extracted.

Catalog hash: `29dcfc0fb8d0ad00827870878a9e26fdccc1fcf01271a6c875757e097c0593a5`. [Safe aggregate receipt](nflverse-live-2026-10-31.json) and [per-file inventory](nflverse-inventory-2026-10-31.json) pin public source/version, usage/terms, original/normalized/manifest hashes, counts, coverage and observation time. Raw source bytes and member records remain private and ignored by Git.

## Measured family coverage

Ranges below come from actual table season fields; they describe observed values, not uniform field completeness or equal row coverage in every season. Participation years are filename evidence, explicitly distinguished from table fields. Timestamped depth files do not gain fabricated season/week columns.

| Family | Logical files | Tables | Archive-only | Observed season fields | Notes |
| --- | ---: | ---: | ---: | --- | --- |
| `dynastyprocess` | 9 | 8 | 1 | No explicit season field | Commit-pinned values/rankings/projections and reference files; benchmark only. |
| `ff_playerids` | 1 | 1 | 0 | No explicit season field | Supplemental ID directory; no name matching. |
| `ff_opportunity` | 130 | 126 | 4 | 2006–2026 | Weekly/seasonal expected-opportunity variants; benchmark, not FFA scoring. |
| `combine` | 2 | 1 | 1 | 2000–2026 | All published combine fields. |
| `contracts` | 3 | 2 | 1 | No explicit season field | Includes nested OTC history RDS as 13,184 rows × 12 columns. |
| `depth_charts` | 27 | 26 | 1 | 2001–2024 | 2001–2024 season fields; 2025/2026 timestamped files also included. |
| `draft_picks` | 2 | 1 | 1 | 1980–2026 | Published draft history. |
| `espn_data` | 3 | 2 | 1 | 2006–2026 | Weekly and seasonal QBR. |
| `ftn_charting` | 6 | 5 | 1 | 2022–2026 | Separate charting source; 2026 weeks 1–7. |
| `injuries` | 19 | 18 | 1 | 2009–2026 | 2026 weeks 1–8; presence does not prove future status. |
| `misc` | 8 | 6 | 2 | 2002–2022 | Auxiliary/reference/patch data; not automatically model features. |
| `nextgen_stats` | 31 | 30 | 1 | 2016–2026 | All passing/rushing/receiving variants and global summaries. |
| `officials` | 2 | 1 | 1 | 2015–2026 | Published officials data. |
| `pbp` | 52 | 28 | 24 | 1999–2026 | 28 annual tables; original ZIP variants retained archive-only. |
| `pbp_participation` | 12 | 11 | 1 | No explicit season field | 2016–2025 filenames plus old_2023; no 2026 file or explicit season column. |
| `pfr_advstats` | 76 | 75 | 1 | 2018–2026 | All published weekly/seasonal passing/rushing/receiving/defense variants. |
| `player_stats` | 367 | 366 | 1 | 1999–2024 | Legacy variants and summaries retained separately from modern stats. |
| `players` | 2 | 1 | 1 | No explicit season field | Primary exact GSIS/ESPN directory. |
| `players_components` | 3 | 2 | 1 | No explicit season field | All components retained; no guessed joins. |
| `rosters` | 108 | 107 | 1 | 1920–2026 | Historical annual roster files, including early seasons. |
| `schedules` | 2 | 1 | 1 | 1999–2026 | Scheduled and completed games; a schedule is not proof a game occurred. |
| `snap_counts` | 17 | 16 | 1 | 2012–2026 | Annual partitions and exposed variants. |
| `stats_player` | 112 | 111 | 1 | 1999–2026 | Weekly and all published summary scopes. |
| `stats_team` | 112 | 111 | 1 | 1999–2026 | Weekly and all published summary scopes. |
| `teams` | 2 | 1 | 1 | No explicit season field | 36 source rows; logo URLs retained, image assets not acquired. |
| `test` | 4 | 4 | 0 | 2000–2022 | Diagnostic inputs retained, excluded from football feature authority. |
| `trades` | 2 | 1 | 1 | 2002–2026 | Published NFL trades; separate from FFA transactions. |
| `weekly_rosters` | 26 | 25 | 1 | 2002–2026 | All annual weekly-roster partitions. |

## Current 2026 availability

The imported PBP table has 18,926 rows and weeks 1–8, source update `2026-10-31T09:03:35Z`. Modern weekly player stats have 7,521 rows and weeks 1–8, updated `2026-10-31T09:05:15Z`; team stats have 216 rows and weeks 1–8, updated `2026-10-31T09:05:18Z`. These scopes include the available part of week 8 and do not assert that the full week is final. The player-stat key profile records eight rows with missing key components; those rows remain preserved, and affected joins must respect the missingness.

Injuries (2,459 rows), weekly rosters (19,865) and snap counts (10,073) contain weeks 1–8. FTN charting has 18,191 rows and weeks 1–7, updated `2026-10-29T12:15:54Z`; its lag remains explicit. The 2026 depth source has `dt` observations from `2026-03-22T06:38:42Z` through `2026-10-31T06:01:42Z`, without a source season/week field. The 2025 depth file extends into March 2026; a filename must not replace actual timestamps.

Participation has 2016–2025 annual files and a retained legacy `old_2023` variant, with no published 2026 file. The [official availability schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html) describes FTN participation from 2023 as postseason-published, so its game dates cannot establish in-season availability. Pre-2023 NGS and newer FTN sources retain separate attribution. The legacy 2023 variant is preserved separately; verify its exact source-specific provenance before promoting it into model features. Charting is a separate dataset from participation.

## Integrity, revisions and as-of limits

All originals and normalized objects have local SHA256 integrity. Provider SHA256 or commit-pinned Git blob SHA1 additionally bind source content where supplied. **786 selected assets lack those upstream checksums.** For these, acquisition stages the candidate and a fresh complete catalog must confirm the same source identity, size and creation/update revision before publication. All 786 passed, with zero changed identities. The post-acquisition catalog is `56b5fde417102d2813587165a4fbb4781140825b6498ca93d0c968fdf6e6d68c`; immutable proof `1ef9c59b84757b560dd61abf0a692f41981a88b817715af9d48e0f8468687bb0` was recorded at `2026-10-31T09:57:48.582627Z`.

This metadata bracket cannot detect an upstream change-and-revert or incorrect upstream metadata; it is not a provider cryptographic signature. Proofs append without mutating source manifests. Source/catalog ordering prevents delayed old work from replacing current data. As-of reads require both local acquisition and hashless-source confirmation by the cutoff; identity validity begins at its verified observation. Current downloads of historical seasons do not establish historical publication vintages. Strict historical model validation remains an M3 gate requiring vintage evidence or an explicitly labeled retrospective policy.

The offline verifier rechecked **1,140 manifests and 1,157 unique source/normalized data objects**, including byte hashes, table columns and row counts, with **zero network calls**. Repeating the same import retained 1,140 published files, zero errors and no active work. Each manifest additionally profiles source schema/types/nullability, scopes, missingness and available key diagnostics. A successful import does not certify every football metric's meaning or establish every required feature join.

## Identity and protected read proof

The primary directory contains 24,863 rows: 18,784 linked and 6,079 unresolved without verified GSIS. Supplemental identity observations retain their separate reports and ambiguity queue. Exact trusted IDs reuse the original FFA athlete UUIDs; no name matching or automatic conflicting-entity merge is used. The review found five later conflicting supplemental ESPN aliases in this local import. A backed-up, locked, plan-hash-checked correction closed those aliases at correction time and appended five review records, preserving original alias rows, reports, source data, UUIDs and the FFA snapshot. [Recovery record](../engineering/nflverse-review-corrections.md).

After correction, all **121/121 rostered athletes** resolve to one GSIS ID. **119** have observed 2026 weekly source rows; **two** have none and remain missing. The 11 owned D/ST entries are distinct from human athletes. There are zero multiple active IDs per provider/entity, 19,008 canonical entities, 35,505 preserved alias rows, one unchanged FFA snapshot and 132 unchanged roster rows. This proves the owned-athlete path; unresolved historical/source records remain explicit.

The local API returned readiness 200, coverage 200, an exact canonical-UUID season/week read 200 with one row and a pinned manifest, and unauthorized access 401. All responses were `no-store`; stored reads made no provider calls. The API smoke process was stopped. Default health-only behavior and the production startup block remain. Source `fantasy_points` columns are labeled as upstream scoring, never substituted for FFA totals.

## Terms and next gate

General nflverse data retains its [upstream license statement](https://nflreadpy.nflverse.com/#license); [FTN charting](https://nflreadr.nflverse.com/reference/load_ftn_charting.html) and FTN participation carry FTN attribution and CC-BY-SA-4.0. DynastyProcess/FantasyPros inputs retain source-specific terms, not a blanket nflverse grant. Software licensing is separate from data licensing; team-logo URLs do not grant image reuse rights. Imported benchmark/ranking/opportunity inputs do not become approved model features automatically.

M1d closes acquisition/storage/manifests/crosswalk and local-read evidence. **M1e is next:** verify Sleeper's documented supplemental inputs and candidate scoring/play capabilities, expand ESPN live coverage/play fixtures, and record Gridiron link/variant/permission prerequisites. M2 member access/UI and M3 feature definitions, FFA cross-source scoring semantics, temporal validation and model quality remain open. No recommendations are enabled by this milestone.
