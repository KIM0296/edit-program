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

## OPEN-019 documented capability tiers

TASK-020 must start from a conservative three-tier map and then replace documentation claims with
runtime evidence from the exact installed Resolve/adapter profile.

### Tier A — mandatory first runtime validation

Candidate read surfaces:

- Resolve product/version/build fields
- current Project identity including documented Project.GetUniqueId() where callable
- current Timeline.GetUniqueId(), start/end/start-timecode/settings required by fixture verification
- track count/name/subtype/enabled/locked state
- TimelineItem.GetUniqueId(), track type/index, start/end/duration
- TimelineItem source start/end frame
- TimelineItem MediaPoolItem binding
- MediaPoolItem unique/media IDs and required clip properties
- linked items
- clip-enabled state
- Timeline and TimelineItem markers
- subtitle track/item enumeration and timing/text where the runtime returns typed values

Tier A documentation is not runtime verification. Each field remains UNKNOWN/UNSUPPORTED until the
installed profile proves a callable, typed, stable read path.

### Tier B — observe when available, never treat as generic Safety proof

- simple/fixed speed
- fades
- generic TimelineItem properties
- transition item presence/type/span surface
- Fusion composition presence
- color node-graph presence

Tier B observations must remain explicitly PARTIAL/UNVERIFIED unless a later producer contract proves
the exact Safety semantic needed.

### Tier C — explicitly unresolved for generic v1 proof

- persistent identity lifetime across app/project reopen, split/delete and session changes
- stable native Track identity independent of type/index
- complete transition alignment/parameter state
- generic Edit/Fairlight effect graph and editability state
- generic keyframe/interpolation state
- complete variable-retime curve
- generic transition/effect/keyframe PRESERVATION_PROVEN production

Do not infer Tier C values from names, positions, static properties or object-ID shape.

## Installed API discovery procedure

For every concrete adapter field, use this order:

1. inspect the exact installed Developer Scripting reference / `DaVinciResolveScript.pyi`
2. confirm the method on the actual native object surface
3. execute only the bounded read call
4. type/shape validate the returned value
5. repeat against an unchanged fixture to validate read stability

Do not mark capability supported from `hasattr()`, a method-name string, documentation presence, or
a non-throwing call alone.

## Runtime gate for TASK-020

TASK-020 may report the documented Tier A surface as candidate support, but completion evidence must
record for each mandatory field one of:

- SUPPORTED_STABLE
- SUPPORTED_UNSTABLE
- UNSUPPORTED
- UNKNOWN

Only SUPPORTED_STABLE fields may contribute to a qualifying fixture snapshot.

Project/Timeline/TimelineItem `GetUniqueId()` values are observation data only. TASK-020 does not
upgrade their lifetime to PERSISTENT_VERIFIED without explicit cross-boundary identity tests.


## Runtime validation matrix

The concrete runtime test plan is defined in:

`docs/TASK_020_RUNTIME_VALIDATION_MATRIX.md`

ADR-033 fixes the matrix as authoritative v1 policy. TASK-020 must implement:

- 10 consecutive double-capture semantic stability pairs per qualifying Tier A fixture
- 3 timeline switch round-trips for identity candidates
- 3 project reopen cycles only when project-reopen lifetime is claimed
- Resolve restart testing only before cross-session persistence claims
- no PERSISTENT_VERIFIED identity grant from same-session stability alone

Implementation must preserve every failed/unstable observation rather than retrying until green.


## Canonical fixture inputs

TASK-020 must use ADR-034 / `docs/PROBE_FIXTURE_CATALOG.md` for F0–F4 semantics.

Do not create or mutate these fixtures in TASK-020. They are externally prepared/registered inputs.

Important requirements:

- interpret catalog timeline ranges as offsets from observed T0 = Timeline.GetStartFrame()
- preserve source ranges as a distinct coordinate domain
- use F1 to prove repeated-media placements are not collapsed
- use F4 for the three ADR-033 timeline-switch round trips
- do not substitute real editorial footage for canonical fixture assets


## Canonical package dependency

TASK-020 code/adapter structure may be developed after TASK-019 using mocks or externally prepared
test state.

However, **full F0–F4 runtime qualification under ADR-033/034 requires the approved first canonical
asset package from TASK-022**.

Do not claim TASK-020's real canonical-fixture runtime matrix complete using ad-hoc substitute media.

Recommended dependency:

```text
TASK-019 approved
→ TASK-022 first canonical package approved
→ TASK-020 full runtime validation
```

If TASK-020 implementation starts before TASK-022 finishes, its Chat completion report must clearly
separate adapter implementation from deferred real canonical-package runtime qualification.
