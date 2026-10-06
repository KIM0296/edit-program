# TASK-012 — Pause Edit Planning Foundation

Status: **Implemented; validation and Chat Gate tracked in docs/reports/TASK_012_COMPLETION.md**

Basis:
- ADR-013 Relationship Execution Semantics v1
- ADR-015 Candidate Authority
- ADR-016 Human Priority
- ADR-018 Pause / Dialogue Editing v1
- ADR-021 Native Time & Snapshot Mapping v1
- ADR-022 Read-only Resolve Snapshot v1
- ADR-023 Pause Edit Planning & Safety Lowering v1
- TASK-007 PauseCandidate
- TASK-010 mapping foundation (must be approved/merged first)
- TASK-011 snapshot/readiness foundation (must be approved/merged first)

## Purpose

Implement a pure immutable planner that consumes an existing PauseCandidate plus explicitly supplied
cut geometry and already-computed readiness/dependency facts, and decides whether the edit is:

- NO_OP
- REVIEW_ONLY
- not ready for planning
- or READY_FOR_PREFLIGHT

The planner does not infer cut geometry, execute edits or manufacture Safety PASS.

## Required semantics

1. PauseCandidate is editorial intent, not geometry.
2. KEEP -> NO_OP, no destructive artifact.
3. REVIEW -> REVIEW_ONLY, no destructive artifact.
4. TIGHTEN requires explicit caller-supplied PauseCutGeometry.
5. TIGHTEN v1 supports exactly one contiguous removed range.
6. TIGHTEN geometry must satisfy:
   - same timeline/base/object/pause binding as candidate
   - removal contained in pause
   - 0 < retained < original duration
   - removed duration == original - candidate retained frames
7. No range clamp/round/shift/repair.
8. REMOVE also requires a separate explicit geometry artifact.
9. REMOVE geometry must remove exactly the original pause and retain 0 frames.
10. REMOVE geometry may not expand into adjacent speech.
11. Geometry generation/inference is out of scope.
12. PlanningDisposition and future SafetyDisposition remain separate.
13. READY_FOR_PREFLIGHT != Safety PASS.
14. Target/mapping readiness is caller-supplied/previously computed; planner does not call TASK-010
    mapper.
15. Snapshot readiness is caller-supplied/previously computed; planner does not call a Resolve
    adapter or TASK-011 evaluator as a side effect.
16. Dependency/relationship readiness is supplied from the relationship layer; planner does not
    infer propagation.
17. Unresolved dependency blocks READY_FOR_PREFLIGHT.
18. Human version/snapshot mismatch -> STALE; no geometry/dependency rebase.
19. Planner does not infer ripple=True from REMOVE/TIGHTEN.
20. Planner does not invoke Safety, Authority or executor.

## Suggested domain

Names may be refined without changing semantics:

- GeometryContractVersion
- PauseCutGeometry
- GeometrySource / GeometryProvenance (v1 supports explicit caller supply only)
- TemporalEditIntent
- PlanningDisposition
- PlanningReason
- TargetReadinessInput
- DependencyReadinessInput
- PausePlanningInput
- PauseEditProposal
- PausePlanningResult

Do not add AI/audio geometry producers in TASK-012.

## Geometry source v1

TASK-012 may represent a minimal provenance value indicating explicit caller supply.

Do not claim HUMAN/AI/PROSODY verification semantics that the task cannot prove.

Future geometry-producing sources belong to OPEN-013 / ADR-024.

## Target readiness

Planner must consume existing mapping/snapshot facts conservatively.

If target is not current/exact/supported according to supplied readiness:

- STALE when stale
- TARGET_RESOLUTION_REQUIRED or UNSUPPORTED otherwise

Do not synthesize a new mapping.

## Dependency readiness

Consume a typed conservative result sufficient to distinguish at least:

- resolved/no blocker
- unresolved/review
- conflict/unsupported

Do not reinterpret relationship membership.

Relation-bearing actions may remain non-ready under existing TASK-005 limitations.

## TIGHTEN cases to test

At minimum:

- missing geometry -> GEOMETRY_REQUIRED
- valid one-range geometry -> potentially READY_FOR_PREFLIGHT
- two removal ranges -> MULTI_RANGE_GEOMETRY_UNSUPPORTED
- removed range outside pause -> invalid/non-ready
- wrong retained arithmetic -> GEOMETRY_CONFLICT
- equal/zero/invalid retained semantics rejected by domain
- geometry wrong timeline/version/object/pause -> non-ready/stale as appropriate
- valid geometry but target non-exact -> non-ready
- valid geometry but dependency unresolved -> non-ready

## REMOVE cases to test

At minimum:

- missing geometry -> GEOMETRY_REQUIRED
- exact full-pause geometry -> potentially READY_FOR_PREFLIGHT
- partial removal geometry -> GEOMETRY_CONFLICT
- geometry extending into adjacent speech -> invalid
- retained duration != 0 -> invalid/conflict
- valid geometry + unresolved dependency -> non-ready

## KEEP / REVIEW tests

- KEEP returns NO_OP even if geometry is supplied; geometry must not cause mutation planning
- REVIEW returns REVIEW_ONLY and never READY_FOR_PREFLIGHT
- neither path calls mapper/relationship/safety/authority/executor

## Stale / binding tests

- candidate/base version mismatch -> STALE
- geometry base mismatch -> STALE or typed binding failure
- target readiness stale -> STALE
- no silent rebase
- repeated media placement identity remains placement-specific
- cross-placement geometry not ready

## Purity tests

Patch/fail if planner tries to invoke:

- temporal mapping functions
- Resolve snapshot adapter
- pause classifier
- relationship execution/propagation
- safety.preflight
- authority transition
- FakeTimeline.apply

The planner consumes already-computed inputs only.

## Acceptance criteria

- immutable planning domain
- defensive copies/canonical tuples
- deterministic same-input result
- PlanningDisposition separate from safety
- exact TIGHTEN geometry validation
- explicit REMOVE geometry validation
- no geometry inference
- no ripple execution
- no Safety/Authority side effects
- existing TASK-001..011 regression PASS
- Python 3.11 CI PASS
- Ruff PASS
- strict mypy PASS

## Explicitly out of scope

- Cut Geometry Resolver
- audio/waveform/VAD/STT/prosody analysis
- arbitrary automatic cut-position selection
- multiple removal ranges
- relationship propagation implementation
- subtitle/marker movement implementation
- protected range override
- transition inference
- Resolve API/mutation
- EditPlan execution
- Safety pass generation
- approval/apply/postflight/promotion
- rollback
- DB/network/UI

## Workflow

1. Do not start until TASK-011 is Chat APPROVED and merged, unless Chat explicitly reorders tasks.
2. Start from then-current main.
3. Treat ADR-023 and this spec as authoritative.
4. Record architecture ambiguity as OPEN; do not invent geometry generation or dependency semantics.
5. Red-first tests.
6. Implement pure immutable planner foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_012_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.


## Implementation notes (before source)

`pause_planning.py` consumes immutable caller-supplied facts only. PlanningBinding holds
candidate_ref, NativeSnapshotRef, fake TimelineObjectId and original pause range. Existing
PauseCandidate lacks an ID/state token, so the caller supplies this binding; planner checks
its timeline/version/object/range against the candidate observation and supplied current ref.
No candidate authority identity or production native correspondence is invented.

Geometry carries explicit caller provenance, contract version, binding, removed ranges and
retained integer duration. Invalid semantic geometry remains inspectable and yields reasons;
noninteger/negative frame counts and malformed typed values reject at construction. No repair.

TargetReadinessInput reuses MappingStatus and carries assessment_ref, binding, media identity,
explicit placement range and resolved primary range. SnapshotReadinessInput reuses ReadinessStatus
and carries assessment/profile refs and binding. These are precomputed facts, not adapters or
new evaluations. Missing inputs fail closed. EXACT target range must match the actual removal,
not merely the original pause; placement must contain that pause. DependencyReadinessInput
binds assessment to geometry ID, primary range and temporal intent, and distinguishes RESOLVED,
UNRESOLVED, CONFLICT and UNSUPPORTED. Planner never constructs those assessments itself.

KEEP/REVIEW return without interpreting supplied geometry/readiness for destructive planning.
Other results collect reasons: stale dominates, then unsupported, target, geometry, dependency
requirements. Only READY_FOR_PREFLIGHT contains PauseEditProposal. Proposal ID is caller-supplied
for determinism, and intent is SHORTEN_GAP/CLOSE_GAP without ripple/displacement or Safety fields.

OPEN-001/006/008/012 retain actual identity/currentness/correspondence verification. ADR-024
resolves OPEN-013 v1 semantics, but TASK-013 resolver/constraints/producers are not implemented.
