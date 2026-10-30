# Worker service

M1a provides `arbit-worker fixture PATH`, an explicitly synthetic end-to-end smoke path into a database ending in `_fixture` or `_test`. It prints only labeled snapshot references and does not poll ESPN or execute arbitrary jobs. Durable scheduling/provider ingestion/model dispatch will compose the shared queue/data/core libraries later, preserving leases/fencing/idempotency and per-host budgets. See [local development](../../docs/engineering/local-development.md).
