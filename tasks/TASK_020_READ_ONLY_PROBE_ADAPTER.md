# TASK-020 — Read-only Probe Adapter Foundation

Status: **PREPARED, NOT AUTHORIZED UNTIL TASK-019 IS APPROVED/MERGED**

Basis: ADR-022, ADR-029, ADR-030, ADR-031, ADR-032.

## Purpose

Implement the first actual Resolve-facing probe component as a strictly read-only adapter boundary. No timeline/project mutation is authorized.

## Mandatory boundaries

- no generic execute/eval/script API
- no project/timeline/fixture repair
- control-plane activation is supplied externally
- capability support and observed values remain separate
- UNKNOWN/UNSUPPORTED never become false/absent
- exact RuntimeProfile/environment/project-generation/timeline binding
- conservative capture-consistency fence
- unstable capture is non-qualifying
- FixtureRoleBinding explicit and unambiguous
- no filename/name/index/current-position identity authority

## Minimum read domains

Represent typed reads, where the installed RuntimeProfile supports them, for runtime profile, registered project/timeline identity, timeline settings/range, track topology/state, placements, media/source/timeline ranges, retime, declared marker/subtitle/transition/effect/keyframe state and identity evidence.

Unsupported fields remain explicitly UNKNOWN/UNSUPPORTED.

## Read stability

Provide semantic comparison for repeated captures of an unchanged fixture. Differences are evidence of observer/runtime instability and are not normalized away.

## Required tests

Cover read-only surface isolation, RuntimeProfile/project/timeline binding, capability/value separation, UNKNOWN preservation, consistency fence, snapshot immutability, completeness, unique/zero/ambiguous role binding, repeated-media ambiguity, no filename/position fallback, fixture-class requirements, challenge UNKNOWN blocking completeness, repeated unchanged capture equality, unstable capture rejection, and no mutation/planner/Safety/transaction/executor calls.

## Explicitly out of scope

Fixture materialization, project-template import, asset-binding mutation, destructive probe invocation, production edit execution, rollback and capability promotion by itself.

## Workflow

Start only after TASK-019 approval. Inspect the exact installed Resolve developer API before concrete calls. Record unavailable facts as limitations; do not synthesize them. Full regression, Python 3.11 CI, Ruff and strict mypy. Write completion report and request Chat Gate. Do not start TASK-021 automatically.