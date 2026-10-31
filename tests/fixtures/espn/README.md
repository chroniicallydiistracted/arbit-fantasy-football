# ESPN contract and scoring fixtures

`league.synthetic.json` and `available.synthetic.json` are **synthetic** observed-shape fixtures from the [public audit](../../../docs/research/espn-public-api-audit-2026-10-30.md). Team/manager/player identities, roster sizes, picks, matchups and stat values are synthetic. They are not FFA score-reconciliation cases. The synthetic unsupported category 9999, negative D/ST IDs, null ownership and absent stat maps deliberately test preservation and unknown-data behavior.

`ffa-scoring.observed.json` is **observed, anonymized numeric data**: the 46 actual FFA definitions plus QB/K/DST raw stat and applied-contribution examples. Identity is replaced; source receipts/body hashes remain. Hand-checked totals are 35.66, 8 and 19. These values are not synthetic projections or a complete roster snapshot. [Scoring support and verification](../../../docs/research/ffa-scoring-verification-2026-10-30.md) explains semantics and empirical coverage.

Additional rare/boundary scenarios in tests are explicitly synthetic; they do not increase live empirical coverage. No fixture contains real manager names/GUIDs, contact details, cookies or article text. Private source archives remain ignored. Tests require no provider access; loopback HTTP tests forbid external DNS/connections.
