# Pinned ESPN reference

Owner requested a workspace clone after the successful public audit. The local checkout is `.references/Public-ESPN-Fantasy-API`, detached at **097c42f0da0b692ceb3168a2c6af1e7479be5906** from [pseudo-r/Public-ESPN-Fantasy-API](https://github.com/pseudo-r/Public-ESPN-Fantasy-API/tree/097c42f0da0b692ceb3168a2c6af1e7479be5906). All 68 tracked files were reviewed; the [source review manifest](espn-reference-source-review-2026-10-30.json) records their checksums.

The checkout is ignored third-party reference material. Its Django/Celery application is not installed or adopted by Arbit. Its own license remains in the checkout. Project artifact validation excludes `.references`; Arbit's own documentation and contracts remain checked. Deterministic CI never downloads this repository.

To reproduce from the project root:

```sh
git clone --no-checkout https://github.com/pseudo-r/Public-ESPN-Fantasy-API.git .references/Public-ESPN-Fantasy-API
git -C .references/Public-ESPN-Fantasy-API checkout --detach 097c42f0da0b692ceb3168a2c6af1e7479be5906
```

Update the pinned revision only after reviewing changes and rerunning affected public read proofs. The [81-request audit](espn-public-api-audit-2026-10-30.md) is authoritative about observed FFA behavior where reference documentation differs. Core FFA reads work publicly without cookies; message boards were excluded from Arbit's scope by the owner on 2026-10-30. Their historical denial remains in audit evidence and is not an integration blocker.
