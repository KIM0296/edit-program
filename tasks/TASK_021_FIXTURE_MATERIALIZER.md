# TASK-021 — Fixture Materializer Prototype

Status: **PREPARED, NOT AUTHORIZED UNTIL TASK-020 IS APPROVED/MERGED**

Basis: ADR-029, ADR-030, ADR-031, ADR-032.

## Purpose

Materialize canonical disposable Resolve probe fixtures using a template-first package, then prove the result through the approved TASK-020 read-only observation path. No destructive capability probe is authorized.

## Mandatory approach

- versioned project template with content hash
- versioned canonical test assets with content hashes
- minimal typed materialization recipe
- independent read-only canonical verification
- no arbitrary scripts

Filename/path alone is never package or asset identity. Missing or hash-mismatched assets fail; do not substitute similar files.

Initial step vocabulary remains bounded, such as IMPORT_PROJECT_TEMPLATE, BIND_CANONICAL_ASSET and ACTIVATE_FIXTURE_TIMELINE.

Materializer return success is insufficient. Only independent MATCH may produce CLEAN_VERIFIED. MISMATCH/INCOMPLETE/STALE/UNSUPPORTED are non-ready.

A mismatched instance becomes DIRTY/discarded. Do not patch the same instance and count it as the clean qualifying fixture.

## Required tests

Cover immutable package/template/assets, hash mismatches, missing asset, filename substitution prohibition, bounded recipe vocabulary, no arbitrary script, return-code insufficiency, independent verification, MATCH -> CLEAN_VERIFIED, mismatch -> discard, non-ready statuses, semantic expected snapshot without native IDs, ambiguous role binding, unexpected object mismatch, no rounding/range/track normalization, new instance after mismatch, project generation binding, no user working project, and no destructive probe primitive.

## Workflow

Start only after TASK-020 approval. Use actual installed Resolve API only through approved materialization boundaries. End every materialization with independent TASK-020 verification. Full regression, Python 3.11 CI, Ruff and strict mypy. Write completion report and request Chat Gate. Do not start mutation probes automatically.

## Canonical fixture catalog

TASK-021 materializes ADR-034 / `docs/PROBE_FIXTURE_CATALOG.md`.

Required packaging behavior:

- F0–F3 each become an independent disposable project instance
- F4 becomes one disposable project with exactly the two required timelines
- canonical synthetic assets are content-hashed by the package
- filename is not asset identity
- project template/package may share immutable asset bytes, but fixture project lifecycles remain
  independent
- materialized semantic state must be verified independently through TASK-020 before CLEAN_VERIFIED


## Canonical asset package validation

TASK-021 must consume ADR-036 / `docs/CANONICAL_FIXTURE_ASSET_PACKAGE.md`.

Before any materialization step:

1. load manifest.v1.json
2. validate package/contract version
3. validate checksums.sha256 format
4. hash manifest, generator.lock and all six assets
5. compute package_digest = SHA256(exact checksums.sha256 bytes)
6. compare against the approved package index
7. inspect required stream properties
8. reject missing/extra/hash-mismatched authoritative package files
9. only then import/bind canonical assets

Do not regenerate canonical media inside TASK-021 or during an ordinary editing request.

The first binary package/digest remains OPEN-021 until separately generated and approved.


## Generator prerequisite

TASK-021 consumes a previously sealed package produced under ADR-037 /
`docs/CANONICAL_ASSET_GENERATOR_CONTRACT.md`.

TASK-021 must not implement or invoke canonical-media generation.

Before TASK-021 can perform full real package validation, OPEN-021 must have a separately approved
first package index containing the actual package_digest and six asset hashes.

Unit tests may continue to use tiny fake package bytes without the full canonical bundle.
