# ESPN contract fixtures

These JSON files are **synthetic**, derived from the required structures observed in the [public FFA audit](../../../docs/research/espn-public-api-audit-2026-10-30.md). Teams, managers, player identities, roster sizes, draft picks, schedule and statistical values are synthetic. No fixture is an actual FFA snapshot or scoring-reconciliation case.

Settings retain observed rule/slot shapes and OFFLINE draft configuration, with a synthetic unsupported stat ID `9999` to prove preservation without invented rule support. Negative D/ST identifiers are intentional. `isViewable: false` is compatible with `settings.isPublic: true`. Available-player ownership includes a null metric; a stat block with scope identifiers but no stat map remains unknown. Player-card/current-player pages have no league metadata envelope.

The audited raw combined league and four available pages were also validated locally against these contracts. Those raw files remain ignored under `data/research`; deterministic tests need no credentials or network. The [request evidence](../../../docs/research/espn-public-2026-10-30.json) records body checksums and exact source requests. Future drift should be reproduced here with anonymized structure, not copied member data.
