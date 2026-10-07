# TASK-014 — Expected Diff & Temporal Displacement Foundation

Status: **Implemented; validation and Chat Gate tracked in docs/reports/TASK_014_COMPLETION.md**

Basis:
- ADR-010 ProtectedRange HARD_LOCK
- ADR-011 Unrequested Content Preservation
- ADR-013 Relationship Execution Semantics
- ADR-015 Candidate Authority
- ADR-016 Human Priority
- ADR-023 Pause Edit Planning
- ADR-025 Expected Diff & Temporal Displacement v1
- INV-016 Expected Diff = Actual Diff
- TASK-012 PauseEditProposal

## Purpose

Implement a pure immutable foundation that consumes an existing PauseEditProposal plus an already
resolved displacement-participation assessment and produces an explicit ExpectedDiff suitable for
future Safety Preflight.

Also implement pure synthetic Expected-vs-Actual diff comparison semantics. Do not capture real
Resolve post-state.

## Mandatory decisions

1. Compiler does not select displacement participants.
2. Participant assessment is precomputed input.
3. No ripple boolean / all-downstream symbolic instruction.
4. Concrete participant object IDs are explicitly enumerated.
5. Primary range removal and collateral displacement are separate values.
6. v1 participant displacement is pure translation with exact integer delta.
7. Every participant delta equals negative removed duration.
8. Nonuniform displacement is non-ready/unsupported.
9. Crossing objects are unsupported/review, not auto trim+move.
10. Gap interaction is not guessed.
11. Pure displacement preserves media/source/duration/track membership.
12. PreservationScope explicitly enumerates validation objects.
13. Scope objects absent from ExpectedDiff are expected unchanged.
14. Scope must cover the whole expected impact.
15. ExpectedDiff completeness != Safety acceptability.
16. Compiler may return READY_FOR_PREFLIGHT even if a later Safety rule will reject a fully described consequence.
17. READY_FOR_PREFLIGHT != Safety PASS.
18. Human edit/base mismatch -> STALE.
19. No silent rebase.
20. Verification uses exact integer-frame equality; no ±1 tolerance.
21. UNVERIFIED != MATCH.

## Suggested domain

Names may be refined without changing semantics:

- ParticipationStatus
- DisplacementParticipant
- DisplacementParticipationAssessment
- RangeRemovalEffect
- TemporalDisplacement
- TemporalDisplacementManifest
- PreservationScope
- CompilerProvenance
- ExpectedDiff
- ExpectedDiffStatus
- ExpectedDiffReason
- ActualChange / ActualDiff
- DiffVerificationStatus
- DiffVerificationReason
- DiffVerificationResult

## Input binding

All inputs must share the same base:

- timeline ID
- timeline version/state reference
- PauseEditProposal reference
- primary geometry/range
- participant assessment

Mismatch -> STALE/non-ready.

Do not call TASK-010 mapper, TASK-011 readiness evaluator, TASK-012 planner or TASK-013 geometry resolver.

## Primary effect

Compile the proposal's exact affected_primary_range into RangeRemovalEffect without changing
boundaries.

No clamp, shift, expansion or normalization.

## Participation input

At minimum distinguish:

- RESOLVED
- REVIEW_REQUIRED
- CONFLICT
- UNSUPPORTED
- STALE

Only RESOLVED may compile READY_FOR_PREFLIGHT ExpectedDiff.

The compiler does not infer participant membership.

## Participant requirements

For the v1 supported case, each participant must:

- be explicitly identified
- be fully downstream of the primary removed range
- have a typed before range
- remain on the same track
- preserve duration
- preserve media/source identity metadata supplied to the compiler
- move by exactly -removed_duration

A crossing participant is non-ready/unsupported.

## Displacement arithmetic

For each participant:

```text
delta = -primary_removed_range.duration
after.start = before.start + delta
after.end   = before.end + delta
before.duration == after.duration
```

No rounding or repair.

## PreservationScope

Represent an immutable explicit object set.

Changed objects must be a subset of the scope.

Any known impacted object omitted from the scope -> SCOPE_INCOMPLETE.

An object in scope with no expected change is invariant.

## Topology

Pause v1 expected topology change must be empty.

Cross-track movement or membership changes are not TemporalDisplacement.

## ExpectedDiff status

At minimum:

- READY_FOR_PREFLIGHT
- INCOMPLETE
- REVIEW_REQUIRED
- STALE
- UNSUPPORTED

Only READY_FOR_PREFLIGHT carries a complete ExpectedDiff.

Do not add Safety PASS/approval/apply fields.

## Pure verification

Synthetic ActualDiff values may be caller-supplied for pure verification tests.

At minimum detect:

- exact MATCH
- missing expected primary change
- missing expected displacement
- unexpected changed object in scope
- wrong primary range
- wrong delta
- media identity change
- source range change
- duration change
- track membership change
- unverifiable identity
- stale post/base relation

MATCH requires no unexpected changes within PreservationScope.

## Required tests

At minimum prove:

1. immutable/frozen nested values
2. deterministic ordering/defensive copies
3. proposal primary range copied exactly
4. compiler does not repair primary range
5. participant RESOLVED required
6. unresolved/conflict/unsupported/stale participation blocks readiness
7. participant set is supplied, not discovered
8. same track/name/order does not add participants
9. one participant -> exact -D displacement
10. multiple participants -> each exact -D
11. nonuniform supplied result cannot become ready
12. crossing participant non-ready
13. existing gap metadata cannot cause guessed shorter delta
14. before/after duration preserved
15. media/source metadata preserved
16. track membership preserved
17. cross-track move rejected
18. changed objects all in PreservationScope
19. omitted known impacted object -> scope incomplete
20. unlisted scope object expected unchanged
21. expected topology changes empty in v1
22. known protected/risk metadata does not itself turn completeness into Safety verdict
23. READY_FOR_PREFLIGHT contains no Safety PASS/Approval/Apply meaning
24. base mismatch -> STALE
25. no silent rebase
26. exact synthetic expected==actual -> MATCH
27. extra actual changed object in scope -> MISMATCH
28. missing expected change -> MISMATCH
29. wrong delta by one frame -> MISMATCH
30. wrong primary range -> MISMATCH
31. media/source/duration/track preservation failure -> MISMATCH
32. identity insufficient -> UNVERIFIED
33. stale post relation -> STALE
34. UNVERIFIED never MATCH
35. no mapper call
36. no native snapshot evaluator
37. no planner call
38. no geometry resolver call
39. no relationship compiler/propagation
40. no safety.preflight
41. no authority transition
42. no FakeTimeline.apply
43. TASK-001..013 regression remains green

## Explicitly out of scope

- participant selection policy
- actual Ripple command
- gap absorption/preservation semantics
- relationship propagation
- subtitle/marker movement policy
- protected-range Safety verdict
- Resolve API/mutation
- actual postflight snapshot capture
- transaction/rollback
- Authority/approval/promotion
- production persistent identity
- nonuniform displacement support
- crossing-object trim+move support
- topology mutation

## Workflow

1. Do not start until TASK-013 is Chat APPROVED and merged, unless Chat explicitly reorders tasks.
2. Start from then-current main.
3. Treat ADR-025 and this spec as authoritative.
4. Record architecture ambiguity as OPEN; do not invent participant/gap/Safety policy.
5. Red-first tests.
6. Implement pure immutable foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_014_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.

## Success definition

Given one explicit PauseEditProposal and a resolved explicit participant set, produce an immutable
ExpectedDiff that fully enumerates the exact primary removal, exact uniform temporal displacements and
unchanged validation scope, and verify synthetic ActualDiff against it without inferring ripple
participants, making Safety decisions or executing Resolve mutations.


## TASK-014 implementation notes (before source)

- Add expected_diff.py, importing existing immutable FrameRange/identity, NativeSnapshotRef,
  MappingKind and PauseEditProposal values only. No layer execution calls.
- DiffBinding explicitly binds proposal, PlanningBinding, geometry ID and primary range.
  PreservationScope enumerates complete supplied PlacementState values; each participant
  carries its before state, proposed integer delta and destination track. The compiler
  validates these against scope rather than discovering participants. A supplied uniform
  consequence fact is required; gap/participant policy is never inferred.
- Compiler input includes current base and provenance/version. Known impacted IDs and
  protected-risk IDs remain descriptive assessment metadata; known impact must be scoped.
  Failures accumulate with stale > unsupported > review > incomplete precedence.
- RangeRemovalEffect records the exact primary removal and before placement. No fragment
  rebinding/source-removal mapping is invented. TemporalDisplacement describes surviving
  placements with exact before/after metadata and delta. Expected topology changes are empty.
- Synthetic ActualDiff carries typed primary effects plus explicit before/after observations
  for all other scoped placements (including unchanged ones). Missing expected changed
  objects are mismatches; missing unchanged observations cannot establish MATCH.
- Caller supplies identity-correspondence and base/post relation evidence references; no
  native proof is generated or authenticated. Verification also requires the caller's
  current post snapshot to equal the observed post. No numeric version increment is inferred.
- Verification precedence: stale relation > insufficient identity/relation evidence > known
  mismatch > incomplete observation coverage > match. All reasons remain machine-readable.
  Extra changed objects (including reported out-of-scope changes), primary changes, or any
  reported topology change mismatch. Unobserved space outside scope remains unverified.
- Primary verification is semantic range-removal equality, not a synthetic native fragment
  reconstruction. Additional primary modifications must be represented as unexpected changes.
  Native post capture/correspondence remains deferred under OPEN-001/006/008/012.
