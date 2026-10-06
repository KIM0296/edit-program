# Pause Edit Planning & Safety Lowering Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the planning boundary between an editorial PauseCandidate and a future safety-checkable edit
plan.

The contract preserves five separations:

1. editorial decision != cut geometry
2. cut geometry != dependency resolution
3. planning readiness != safety pass
4. safety pass != approval
5. approval != successful verified apply

Core principles:

> A Pause decision specifies editorial intent, not cut geometry.

> TIGHTEN may not be lowered to an EditPlan until the exact retained/removed temporal geometry is
> explicitly resolved.

## Architecture position

```text
PauseCandidate
      ↓
Planning eligibility
      ↓
current snapshot / exact target readiness
      ↓
explicit cut geometry
      ↓
PauseEditProposal
      ↓
precomputed dependency assessment
      ↓
READY_FOR_PREFLIGHT
      ↓
Safety Preflight
      ↓
Validated Plan Candidate
      ↓
Authority / Approval / Apply / Verification
```

This contract does not execute edits.

## PlanningDisposition and SafetyDisposition are separate

Planning and Safety are independent axes.

Suggested PlanningDisposition:

- NO_OP
- REVIEW_ONLY
- TARGET_RESOLUTION_REQUIRED
- GEOMETRY_REQUIRED
- DEPENDENCY_RESOLUTION_REQUIRED
- READY_FOR_PREFLIGHT
- STALE
- UNSUPPORTED

A planner may return READY_FOR_PREFLIGHT only when the proposed primary temporal edit is explicit
enough to be evaluated by Safety.

READY_FOR_PREFLIGHT is **not** a safety verdict.

SafetyDisposition remains a separate later axis such as:

- NOT_EVALUATED
- PASS
- REVIEW
- REJECT

TASK-012 does not manufacture Safety PASS.

## KEEP

PauseAction.KEEP lowers only to:

```text
NO_OP
```

KEEP must not create a destructive command, geometry, ripple displacement or rewrite of unchanged
timeline state.

## REVIEW

PauseAction.REVIEW lowers only to:

```text
REVIEW_ONLY
```

REVIEW must not generate destructive commands.

Future review UI/payloads may carry Original / Proposal / Reason / Impact / Choices, but this contract
does not implement UI.

## TIGHTEN means editorial duration intent, not location

A TIGHTEN candidate says that the pause should remain but become shorter.

For example:

```text
pause_range = [100,160)
suggested_retained_frames = 20
```

does not tell the planner whether to preserve the leading, trailing or middle portion.

The planner must never synthesize that choice from retained_frames alone.

## PauseCutGeometry

TIGHTEN/REMOVE destructive planning requires a separate immutable PauseCutGeometry.

Recommended fields:

- geometry_id
- candidate_ref
- timeline_id
- base_version
- object_id
- original_pause_range
- removed_ranges
- retained_duration_frames
- geometry_contract_version
- explicit provenance/source reference

Geometry is a descriptive planning artifact, not apply authority.

## TASK-012 is a geometry consumer only

TASK-012 accepts explicitly caller-supplied geometry and validates it.

It does **not** infer geometry from:

- audio
- waveform
- VAD
- STT
- prosody
- breath cues
- semantic context
- local pacing
- candidate confidence
- preferred retained duration alone

Geometry generation is a separate responsibility tracked by OPEN-013 and a future Cut Geometry
Resolution Contract.

## Caller-supplied does not mean blindly trusted

Caller-supplied geometry must still pass structural and binding validation.

The planner checks:

- candidate binding
- base timeline/version
- object/placement identity
- original pause range
- range containment
- retained duration arithmetic
- supported geometry cardinality
- target/mapping readiness
- supplied dependency readiness

The planner validates geometry consistency; it does not certify that the geometry was editorially
optimal.

## TIGHTEN v1: exactly one contiguous removal range

For v1 planning:

```text
len(removed_ranges) == 1
```

is required for TIGHTEN lowering.

Multiple removal ranges are unsupported/review-required in v1.

This deliberately avoids turning one PauseCandidate into multiple delete/ripple operations before
dependency, transaction and rollback behavior are mature.

## TIGHTEN geometry invariant

Let:

- P = original pause range
- R = the single removed range
- retained = candidate.suggested_retained_frames

Then all must hold:

```text
P contains R

0 < retained < P.duration

R.duration == P.duration - retained
```

The geometry must remain bound to the same timeline/version/object/pause range as the candidate.

If the candidate says retained=20 but the geometry implies retained=22, return a geometry conflict.
Do not repair or clamp it.

## No geometry clamp

A removal range extending outside the pause by even one frame is invalid.

The planner must not:

- clamp
- round
- shift
- normalize

the range to make it valid.

## REMOVE also requires an explicit geometry record

PauseAction.REMOVE is editorial intent:

> this pause may be absent from the final edit.

It is not itself a delete command.

v1 REMOVE geometry is explicit and deterministic in shape:

```text
removed_ranges == (original_pause_range,)
retained_duration_frames == 0
```

Even though the geometry is simple, keep the decision and geometry as separate immutable artifacts
for provenance/auditability.

TASK-012 may validate a supplied full-pause REMOVE geometry. It does not collapse Candidate and
Geometry into one type.

## REMOVE never expands into adjacent speech

REMOVE geometry may not include:

- previous speech tail
- next speech head
- adjacent non-pause frames

Removing adjacent speech is a separate dialogue-cleanup decision and requires a different contract.

## TemporalEditIntent

The planner may normalize candidate intent into a descriptive intermediate enum:

- PRESERVE
- SHORTEN_GAP
- CLOSE_GAP
- REVIEW_ONLY

Suggested mapping:

- KEEP -> PRESERVE
- TIGHTEN -> SHORTEN_GAP
- REMOVE -> CLOSE_GAP
- REVIEW -> REVIEW_ONLY

TemporalEditIntent still does not specify ripple mechanics.

## Candidate confidence is not a planning bypass

HIGH confidence does not skip:

- target freshness
- exact mapping
- geometry
- dependency resolution
- Safety

MEDIUM TIGHTEN may produce a reviewable proposal when geometry is explicit, but does not gain Main
apply authority.

## Target readiness

Production lowering requires the target to be current and exact.

When ADR-021 mapping is involved, only an EXACT current mapping may satisfy temporal target
readiness.

STALE / AMBIGUOUS / NON_INTEGRAL / OUT_OF_RANGE / UNSUPPORTED mappings block lowering.

TASK-012 consumes already-computed target/mapping readiness. It does not call the mapper itself.

## Snapshot readiness

When ADR-022 snapshot readiness is supplied, the planner consumes it as input.

The planner does not call a Resolve adapter or infer missing snapshot facts.

A stale/unsupported/unverified required snapshot state blocks the corresponding planning path
according to the supplied readiness result.

## Human Edit Wins

Candidate, geometry, target resolution and dependency assessment are all bound to the same base
snapshot/version.

If the current base changes, planning artifacts are STALE.

Do not silently rebase geometry or dependency results.

## Ripple is not inferred directly from PauseAction

Do not encode:

```text
REMOVE -> ripple=True
TIGHTEN -> ripple=True
```

as direct action mapping.

Planner describes desired temporal effect:

- SHORTEN_GAP
- CLOSE_GAP

Future plan compilation/safety must explicitly calculate expected displacement.

This preserves ADR-011: timeline movement must be explicit and approved, not an accidental side
effect.

## PauseEditProposal

When the primary edit is geometrically explicit, produce an immutable PauseEditProposal.

Recommended fields:

- proposal_id
- candidate_ref
- base snapshot reference
- target object
- temporal_intent
- geometry
- affected_primary_range
- planning reasons
- dependency readiness/assessment reference
- planning contract version

A proposal means:

> this exact primary edit is being considered.

It does not mean:

- safe
- approved
- applied
- verified

## Dependency assessment is an input, not planner inference

TASK-012 does not reimplement relationship semantics.

It consumes a precomputed dependency/relationship assessment from the existing relationship layer or
a conservative explicit equivalent.

The planner must not infer:

- linked objects move together
- linked objects delete together
- subtitle automatically follows
- J/L boundaries normalize
- member order implies direction

ADR-013 remains authoritative.

## Unresolved relationship/dependency state blocks lowering

If dependency handling is unresolved, return:

```text
DEPENDENCY_RESOLUTION_REQUIRED
```

or another explicit non-ready result.

Current relationship-bearing actions may therefore remain review-required until their action-specific
semantics are implemented.

This is expected, not a failure of the planner.

## J/L Cut preservation

Existing J/L cuts are user-owned structure.

Do not normalize audio/video boundaries merely because objects are linked.

## No delete cascade

A primary Pause REMOVE/TIGHTEN does not automatically delete or trim relationship members.

Dependent actions must be explicitly represented by an approved dependency compiler before Safety
evaluation.

## Subtitle / marker / dependent temporal objects

The planner does not directly shift subtitles, markers or other temporal objects merely because a
pause closes.

Their expected response must be explicit through a dependency/safety contract.

Unknown behavior -> review/non-ready.

## Protected ranges remain Safety responsibility

The planner may preserve risk metadata, but it must not bypass ADR-010 HARD_LOCK.

Primary geometry overlap or expected displacement involving protected content must ultimately be
rejected by Safety.

TASK-012 may not declare a protected conflict safe.

## Planning vs Safety

Planner output READY_FOR_PREFLIGHT means only:

- target sufficiently resolved
- geometry sufficiently explicit
- required dependency readiness supplied
- primary expected change can be stated

It does not evaluate every production invariant.

Safety Preflight remains responsible for safety verdicts.

## Expected change must be explicit before mutation

A future plan derived from PauseEditProposal must make the expected primary change explicit.

Example:

```text
remove [120,160)
expected close-gap displacement = 40 frames
```

The actual displacement still requires explicit calculation/approval by plan compilation/Safety.

Unexpected motion may not be accepted after the fact.

## Topology default

Pause editing v1 expects no topology change by default:

- no track creation
- no track deletion
- no track reorder
- no cross-track membership move

Any such change would require a separate explicit expected topology change.

## Preserve Editability

Pause shortening/removal must not be lowered by replacing editable timeline state with a baked or
rendered substitute.

Existing editable structure remains user-owned.

## Transition / editability / retime risk

TASK-012 does not infer unknown native safety facts.

If supplied readiness says required transition/editability/retime evidence is insufficient, the
planner does not upgrade it to ready.

For initial destructive Pause planning, unsupported retime state remains conservative.

## Cross-placement geometry

A geometry spanning multiple placements is not supported by TASK-012 v1.

Do not split or merge it automatically.

Return unsupported/review-required.

## Multi-track changes

Multi-track/dependent changes require explicit dependency assessment and future plan compilation.

Track name/index cannot select a dependent track.

## Proposed EditPlan remains later

ADR-023 defines the boundary toward a future ProposedEditPlan but TASK-012 does not need to create a
fully executable plan or invoke Safety.

The initial implementation should stop at an immutable planning result / PauseEditProposal suitable
for later preflight.

## Immutability and determinism

Candidate, geometry, readiness inputs and planner results are immutable.

Given identical:

- candidate
- base snapshot reference
- target readiness
- geometry
- dependency readiness

the pure planner returns the same result.

New geometry creates a new artifact; historical geometry is not mutated.

## Machine-readable PlanningReason

Recommended reasons include:

- KEEP_NO_OP
- REVIEW_DECISION
- STALE_CANDIDATE
- TARGET_NOT_EXACT
- TARGET_UNSUPPORTED
- GEOMETRY_MISSING
- GEOMETRY_INVALID
- GEOMETRY_CONFLICT
- MULTI_RANGE_GEOMETRY_UNSUPPORTED
- DEPENDENCY_UNRESOLVED
- DEPENDENCY_CONFLICT
- CROSS_PLACEMENT_UNSUPPORTED
- RETIME_UNSUPPORTED
- READY_FOR_PREFLIGHT

TASK-012 may refine names without weakening semantics.

## TASK-012 boundary

Implement pure immutable planning foundation only:

- PauseCutGeometry
- TemporalEditIntent
- PlanningDisposition
- PlanningReason
- PauseEditProposal / planning result
- KEEP -> NO_OP
- REVIEW -> REVIEW_ONLY
- TIGHTEN geometry structural validation
- REMOVE full-pause geometry validation
- candidate/snapshot/target/geometry binding validation
- consumption of already-computed target readiness
- consumption of already-computed dependency readiness
- pure READY_FOR_PREFLIGHT determination
- deterministic/immutable tests

Do not implement:

- geometry inference
- audio/VAD/STT/prosody/semantic geometry resolver
- Resolve API
- relationship propagation
- Safety PASS
- protected-range bypass
- ripple execution
- actual EditPlan execution
- authority transition
- approval
- postflight
- rollback
- UI/DB/network

## Accepted v1 decisions

1. Pause decision specifies editorial intent, not cut geometry.
2. TIGHTEN cannot lower without explicit exact geometry.
3. PlanningDisposition and SafetyDisposition are separate.
4. TIGHTEN v1 supports exactly one contiguous removed range.
5. REMOVE uses a separate explicit full-pause geometry artifact.
6. TASK-012 consumes caller-supplied geometry and does not infer it.
7. Geometry generation is a separate future contract (OPEN-013 / ADR-024).
8. Candidate confidence never bypasses target/geometry/dependency/Safety stages.
9. Planner consumes mapping/snapshot/dependency results rather than reimplementing those layers.
10. READY_FOR_PREFLIGHT is not Safety PASS or Apply authority.

## Final principle

> Editorial intent tells us what should change. Geometry tells us exactly where. Dependency
> planning tells us what else may be affected. Safety decides whether the plan is acceptable.
> Authority decides whether it may actually be applied.
