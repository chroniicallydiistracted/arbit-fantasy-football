# Comprehensive nflverse ingestion

M1d imports published statistical inputs into local immutable storage. It does not enable models or recommendations. ESPN remains authoritative for FFA rules, ownership and official fantasy totals.

## Catalog and import

After frozen installs, `make db-up` and `make local-db-migrate`:

```sh
make local-nflverse-catalog
# Copy the returned catalog_hash; all selected files are imported by default.
uv run --env-file .env.local arbit-worker nflverse-import --catalog <hash> --workers 2
uv run --env-file .env.local arbit-worker nflverse-status --catalog <hash>
make local-nflverse-verify
```

The catalog exhausts paginated official `nflverse/nflverse-data` releases, ffopportunity data releases and a commit-pinned DynastyProcess files directory. No seasons are inferred from the computer date or silently restricted to a sample. Every published core release group and logical file is accounted for, including historical/deprecated statistics, component/reference/patch data and diagnostic assets. nflreadr's full loader source was inspected at commit `23f915a5be30415aeaa0c5c80cd23b2c69cda122`; see the [primary catalog](https://nflreadr.nflverse.com/reference/index.html).

For each logical file, choose Parquet, then compressed CSV, CSV, RDS, QS, JSON or text. Other formats for the same stem remain cataloged as mirrors; distinct statistical subtypes, year partitions and summaries are retained. Model ZIP releases are explicitly listed as model artifacts rather than observations and are never executed. ffverse rankings, values and expected-points tables are benchmark/reference inputs; they cannot substitute for shared FFA scoring or become recommendation features by importing them.

The first full inventory selected 1,140 logical files (about 1.38 GB) from 4,764 physical representations across 28 families. Current/historical completeness is measured against that catalog, not an assumed number of seasons. Sources include PBP, current and legacy player/team statistics and all summaries, participation, annual/weekly rosters, player IDs/components, NFL-team metadata, schedules/game results, snaps, NGS variants, PFR weekly/seasonal passing/rushing/receiving/defense, FTN charting, depth, injuries, ESPN QBR, draft/combine, contracts, trades, officials and the exposed ffverse references.

`--retry-failed` explicitly creates new attempts for failed files while preserving failed job history. Successful files in the same catalog are skipped. Ctrl+C/SIGTERM lets in-flight work finish, leaving queued work durable; repeat the command to resume. A catalog with auth denial pauses rather than hammering the remaining files; check source visibility/rate state before explicitly retrying. Transient requests retry at most five times with persisted exponential delay/jitter/Retry-After. Exhausted or invalid files remain explicit failures and make completion nonzero. `nflverse-status` exposes safe codes without source bodies.

To discover newer revisions, run `nflverse-catalog --live` again and import that new hash. Matching provider checksums or a verified unchanged source revision reuse local original bytes; changed source versions publish new immutable manifests. A metadata/file checksum race fails safely rather than publishing the wrong body; rediscover before retrying a changed release. The current CLI is an explicit foreground batch importer, not an installed scheduled service.

## Storage, fidelity and source limits

`ARBIT_NFLVERSE_PATH` defaults to ignored `data/nflverse`; objects live in `objects/<sha256>`. Original bytes, normalized Parquet and serialized manifests use mode-600 files in a private directory. Bounded streamed writes verify declared size, GitHub SHA256 when supplied and pinned raw Git blob SHA1; they fsync before atomic publication and verify existing objects instead of overwriting them. Normalized Parquet can reuse validated upstream Parquet unchanged. Every column and null is preserved; source numeric scope values such as `1.0` are interpreted only in the coverage profile, without rewriting the source type. CSV columns remain strings to protect IDs/leading zeros; empty/unquoted missing markers become null, while quoted literal values remain values. Raw CSV is retained for exact source reproduction.

RDS tables use pyreadr with Polars in a separate process, constrained to 4 GiB address space/60 CPU seconds/90 elapsed seconds, with no R runtime or code evaluation. Opaque and metadata objects remain archive-only. File limits are 512 MiB per original/derived object, 2 GiB decompressed CSV, five million rows per table and 1,024 columns; limits fail explicitly. Arrow profiles include original columns/types/nullability, row count, missing counts, actual season/type/week coverage, relevant date/timestamp ranges and missing/duplicate key diagnostics. Profiling does not erase anomalous rows or certify every football metric's semantics. Missing values never become zero.

Original/normalized checksums, source asset/version/URLs, source timestamps, usage, terms/attribution, schema hash, adapter version, observation time and limitations are pinned in PostgreSQL manifests. Publication/current-pointer updates and successful job completion share a lease-fenced transaction. Partial/bad/older files preserve the last good pointer; exact historical replay never promotes an old version. Files precede database publication, so failed parsing or a crash can leave unreferenced private objects; no automatic destructive cleanup is installed.

`nflverse-verify --all` independently verifies stored manifest hashes, all referenced source/normalized bytes, Parquet row counts and columns without network calls. `--manifest <hash>` narrows verification. Back up PostgreSQL and the object directory together. New schema migrations extend the foundation without changing applied DDL; do not reset production/shared tables for an import test.

## Availability and point-in-time use

Event date, source-file creation/update and first local observation are different facts. As-of reads only select manifests first observed by that cutoff. A freshly downloaded historical season file does not establish that those corrected values were known years earlier. Strict historical backtests remain blocked unless historical release evidence or an explicitly labeled retrospective evaluation policy resolves that distinction.

From 2025 onward depth charts use timestamped observations, not invented week assignments. From 2023 FTN participation is published after the postseason, so file/game dates cannot make it an in-season feature. FTN charting is a separate product with its own update lag. Current-year absence, stale files and unsupported source forms remain visible rather than being filled with guesses. [Official availability schedule](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html).

General nflverse data is attributed under its upstream CC-BY-4.0 statement; FTN charting and FTN participation carry CC-BY-SA-4.0 and FTN attribution. Earlier NGS participation retains its distinct source attribution. ffverse/DynastyProcess/FantasyPros provenance and source-specific terms remain explicit. Importing team-logo URLs does not download or grant separate rights to image assets. See the [official license/source statement](https://nflreadpy.nflverse.com/#license) and [FTN terms](https://nflreadr.nflverse.com/reference/load_ftn_charting.html).

## Canonical identity and local reads

The authoritative player directory's explicit GSIS/ESPN pairs reuse existing FFA athlete UUIDs. New verified GSIS records get native identities; valid crosswalk aliases begin at the observation that established them. Neither missing GSIS nor ambiguous/reused IDs are resolved by name. Conflicting existing UUIDs are never merged automatically; they remain in `mapping_review`, with evidence and reason. DynastyProcess crosswalks are supplemental. Provider directory records without verified GSIS remain stored and unresolved. NFL-team metadata and source game IDs are retained; no guessed ESPN team/franchise or historical transfer joins are asserted.

With `make local-api`, the existing optional operator token plus actual loopback peer protects:

| GET route | Result |
| --- | --- |
| `/internal/league/nflverse/coverage` | Stored family coverage, import outcomes and identity-review counts |
| `/internal/league/nflverse/players/{canonical_uuid}/stats?season=2026&week=1` | Bounded current source weekly rows joined by exact GSIS alias, with pinned manifest and missingness/authority labels |

No route contacts providers. Responses/errors are no-store. Default health-only and production/member-authentication guards remain; see [local operator access](ffa-synchronization.md). Decimal-like source values are sent as strings, unknowns stay null, and upstream `fantasy_points` are explicitly labeled as using upstream rules. Recommendations remain disabled.
