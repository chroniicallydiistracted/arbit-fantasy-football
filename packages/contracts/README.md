# Public contracts

JSON Schemas define single-FFA configuration and future recommendation records; `pnpm check:contracts` validates examples with Draft2020-12 AJV. [OpenAPI](openapi.json) now defines implemented private member/auth/administrator contracts and generates the [TypeScript wire types](../../apps/web/src/generated/api.ts). Examples and fixture auth are explicitly synthetic; no recommendation API exists.

Regenerate with `uv run python scripts/export_openapi.py` then `pnpm generate:client`. `pnpm check:client` compares both artifacts with current server models without rewriting them. Member operations, source distinctions and real Google setup gates are in the [guide](../../docs/engineering/member-application.md).
