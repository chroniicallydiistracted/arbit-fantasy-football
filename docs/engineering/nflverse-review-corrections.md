# M1d review corrections and recovery record

The final independent review found five Important correctness/recovery gaps. All five were fixed in one regression-backed pass: check all active IDs on an entity before extending crosswalks; order current data by source/catalog revision separately from local observation; bind hashless mutable sources through a stable metadata acquisition bracket; catch corrupt compressed CSV safely; and compare source season/week scopes numerically on reads. Uppercase suffix handling is a Minor with zero affected selected files in the live catalog; keep its opaque classification explicit until a separate compatibility slice.

## Existing local identity correction

A read-only audit found five entities with a later supplemental ESPN alias alongside an earlier trusted ESPN alias, and no multiple active GSIS aliases. The completed correction:

1. Backed up the local PostgreSQL database and retained all immutable source/manifest objects.
2. Produced a private list of the five exact later alias keys, evidence manifests and earlier keys; took the shared identity lock and revalidated that plan in the correction transaction.
3. Closed only each later supplemental alias at the correction observation time; preserved its original validity start and evidence. No entities were deleted or merged, source bytes or FFA snapshots changed, or mappings backdated.
4. Appended five mapping-review records recording the conflicting old/new IDs and correction reason, and preserved the original import report as historical evidence.
5. Verified zero multiple active IDs per provider/entity, unchanged FFA snapshot/current/roster counts, and all 121 rostered human athletes still resolve to exactly one GSIS ID. Unresolved source records remain explicit.

The change repairs a newly introduced local-development mapping error inside the authorized M1d work. It is backed by a rollback artifact and a test for the same class of import before its application. No external/provider records or published league results change.

## Hashless source revisions

786 selected release assets lack upstream SHA256/Git blob SHA1. A local SHA256 provides byte integrity but cannot bind a mutable download URL to catalog metadata alone. Newly acquired hashless files must remain staged until a second metadata inventory confirms the same asset identity, size and update revision. Changed or unverifiable revisions remain unavailable; source/catalog age also prevents an old import from replacing newer current data. Provider-checksummed and immutable Git-blob inputs retain their direct verified path. Record catalog-bracket evidence and local availability time separately from historical event/source times.

All 786 existing hashless imports passed the post-acquisition metadata check; no changed identities were found. Original bytes/manifests remain immutable. Confirmation is separately dated, and as-of selection requires both acquisition and confirmation by its cutoff. This bracket cannot detect an upstream change-and-revert or inaccurate upstream metadata; it is not an upstream cryptographic signature. The [safe receipt](../research/nflverse-live-2026-10-31.json) pins both catalogs and the immutable proof.

## Recovery artifacts and result

The private backup is `data/backups/2026-10-31/m1d-before-crosswalk-correction.dump` (2,611,766 bytes; SHA256 `d9b25d55d8182986e70247d6312b8d098a0a5e1ee66bbf019409a636e2e758ab`). The private exact-key plan is alongside it; its content hash is `8fcb4028a5fc15561eb96dac13e34eed4299dd4a9e0e63a8e3b37213c9268c77`. These private files are ignored by Git. The correction helper rechecks the locked plan hash and closes only the specifically reviewed later supplemental aliases.

After correction: 19,008 canonical entities, 35,505 preserved alias rows, one FFA snapshot and 132 roster rows are unchanged; five review records were appended. All 121 rostered athletes resolve to one GSIS identity. Original identity-import reports remain historical records, including their original counts. `test_review_repair_closes_only_later_supplemental_alias_and_keeps_history` verifies preservation and rejects a stale correction plan. New imports reject the underlying entity-wide conflict in both provider directions.

Schema `0004_source_provenance` adds staged candidates and immutable revision proofs without modifying applied migrations. Back up the database and object directory together before operator recovery. Do not replay the private alias-correction plan after it has been applied; repeat planning will find no eligible correction.
