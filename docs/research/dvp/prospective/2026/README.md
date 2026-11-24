# M3-3 DvP prospective forecasts, 2026 weeks 12–18

Exported from the write-once archive `artifacts/dvp/prospective/2026/` by `scripts/model/dvp_prospective.py`. The procedure is in [PROSPECTIVE_2026.md](../../PROSPECTIVE_2026.md); the rules were declared first in [`config/dvp/prospective.json`](../../../../../config/dvp/prospective.json).

**Never edit these files.** Each one's SHA-256 is in [ledger.jsonl](ledger.jsonl), and each ledger line carries the hash of the line before it. Editing a file, or the ledger, breaks the chain.

| File | Contents |
| --- | --- |
| `ledger.jsonl` | One line per week: PROSPECTIVE (archived before the cutoff), MISSED, or RETROSPECTIVE (a later reconstruction, never counted) |
| `week-WW/forecasts.csv` | Forecast-only rows: game, offense, position, defense, cutoff, the opposing unit's game count, and every frozen forecast (B00–B09). No score or label |
| `week-WW/manifest.json` | Generated and cutoff times, the frozen-hash verification, readiness, the fitted parameters, the data lineage (targets index, verified objects, nflverse manifests and when Arbit observed them, source ancestry hash) and the forecasts' hashes |
| `week-WW/league.json` | The FFA league's D/ST rosters at forecast time (snapshot id and time), for the exploratory league-constrained evaluation |

**Checking it:** run `uv run python scripts/model/dvp_prospective.py verify --main <main checkout>`. It checks the chain, every archived file against its ledger hash, that every PROSPECTIVE forecast was generated before its cutoff, and that these exported copies equal the archive. GitHub's record of each push is an outside timestamp: `gh api "repos/{owner}/{repo}/activity?ref=refs/heads/<branch>"`.
