# M3-3 DvP prospective forecasts, 2026 weeks 12–18

Exported from the write-once archive `artifacts/dvp/prospective/2026/` by `scripts/model/dvp_prospective.py`. The procedure is in [PROSPECTIVE_2026.md](../../PROSPECTIVE_2026.md); the rules were declared first in [`config/dvp/prospective.json`](../../../../../config/dvp/prospective.json).

**Never edit these files.** Each one's SHA-256 is in [ledger.jsonl](ledger.jsonl), and each ledger line carries the hash of the line before it. Editing a file, or the ledger, breaks the chain.

| File | Contents |
| --- | --- |
| `ledger.jsonl` | One line per week: PROSPECTIVE (archived before the cutoff), MISSED, or RETROSPECTIVE (a later reconstruction, never counted) |
| `week-WW/forecasts.csv` | Forecast-only rows: game, offense, position, defense, cutoff, the opposing unit's game count, and every frozen forecast (B00–B09). No score or label |
| `week-WW/manifest.json` | Generated and cutoff times, the frozen-hash verification, readiness, the fitted parameters, the data lineage (targets index, verified objects, nflverse manifests and when Arbit observed them, source ancestry hash) and the forecasts' hashes |
| `week-12/league.json` | Week 12 only: the FFA league's D/ST rosters at forecast time. From week 13 the league capture stays in the local archive (it holds per-team rosters); its hash is in the manifest and in the external commitment |

**Checking it:** run `uv run python scripts/model/dvp_prospective.py verify --main <main checkout>`. It checks the chain, every archived file against its ledger hash, that every PROSPECTIVE forecast was generated before its cutoff, and that these exported copies equal the archive. GitHub's record of each push is an outside timestamp: `gh api "repos/{owner}/{repo}/activity?ref=refs/heads/<branch>"`. From amendment 1 every archive also has a commitment on branch `research-evidence/dvp-prospective` ([PROSPECTIVE_2026.md](../../PROSPECTIVE_2026.md#operations-owner-authorized-timer-own-077-dec-02)).
