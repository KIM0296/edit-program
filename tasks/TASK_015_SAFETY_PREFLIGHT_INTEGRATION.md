# TASK-015 — Safety Preflight Integration Foundation

Status: **Authorized after TASK-014 approval/merge; implementation in progress**

Basis:
- ADR-010 ProtectedRange HARD_LOCK
- ADR-011 Unrequested Content Preservation
- ADR-013 Relationship Execution Semantics
- ADR-015 Candidate Authority
- ADR-017 Preserve Editability
- ADR-022 Read-only Snapshot
- ADR-025 Expected Diff & Temporal Displacement
- ADR-026 Safety Preflight Integration v1
- INV-002/003/004/006/007/009/010/011/012/016/017/018/019

## Purpose

Implement a pure immutable Safety Preflight foundation that consumes a READY_FOR_PREFLIGHT
ExpectedDiff plus explicit current safety evidence and returns either:

- STALE / UNSUPPORTED / INCOMPLETE, with no SafetyVerdict
- or EVALUATED with PASS / REVIEW_REQUIRED / REJECT

No Resolve mutation, approval or execution is performed.

## Mandatory profile

Implement PAUSE_DESTRUCTIVE_PREFLIGHT_V1 with exactly these 17 required checks:

1. BASE_FRESHNESS
2. EXPECTED_DIFF_INTEGRITY
3. PROTECTION_CONTEXT
4. PROTECTED_RANGE
5. TRACK_LOCK
6. RELATIONSHIP_INTEGRITY
7. TEMPORAL_DEPENDENCY_COVERAGE
8. RETIME_SUPPORT
9. MEDIA_IDENTITY_PRESERVATION
10. SOURCE_RANGE_PRESERVATION
11. DURATION_PRESERVATION
12. TRACK_MEMBERSHIP_PRESERVATION
13. TOPOLOGY_PRESERVATION
14. TRANSITION_INTEGRITY
15. EFFECT_EDITABILITY
16. KEYFRAME_EDITABILITY
17. PRESERVATION_SCOPE

Do not silently add/remove mandatory checks.

## Required statuses

PreflightStatus:

- EVALUATED
- STALE
- UNSUPPORTED
- INCOMPLETE

Precedence:

```text
STALE > UNSUPPORTED > INCOMPLETE > EVALUATED
```

SafetyVerdict only for EVALUATED:

- PASS
- REVIEW_REQUIRED
- REJECT

Precedence:

```text
REJECT > REVIEW_REQUIRED > PASS
```

## Result invariant

```text
status != EVALUATED -> verdict is None
status == EVALUATED -> verdict is not None
```

PASS requires all 17 mandatory checks to have completed evaluable results.

## Unknown policy

Unknown/missing mandatory safety state must not become PASS.

Use INCOMPLETE for unknown/unavailable mandatory evidence unless the contract explicitly classifies
the case as UNSUPPORTED/STALE.

## Finding retention

Do not short-circuit diagnostics after the first reject/review.

Preserve every check result that can be evaluated from supplied evidence.

## ProtectionContext

Implement immutable snapshot-bound protection context with explicit completeness.

Requirements:

- complete empty protected tuple = known no protection
- incomplete/unknown protection context -> INCOMPLETE
- primary destructive overlap -> REJECT
- explicitly displaced protected object/range -> REJECT

No protection override.

## Track lock

Affected track lock:

- FALSE -> PASS check
- TRUE -> REJECT
- UNKNOWN/unavailable -> INCOMPLETE

Do not infer lock state from track name/index or other metadata.

## Relationship / dependency

Consume precomputed relationship/dependency completeness evidence only.

Do not call/reimplement relationship resolution.

Unknown/unresolved temporal dependency coverage -> INCOMPLETE.

## Retime

- supported exact forward state -> may pass
- UNKNOWN -> INCOMPLETE
- REVERSE/FREEZE/VARIABLE_RETIME -> UNSUPPORTED

Do not promote UNKNOWN to IDENTITY_1X.

## Pure displacement preservation

For TemporalDisplacement expected changes verify supplied metadata preserves:

- media identity
- source range
- duration
- track membership

Known mutation -> REJECT.

## Topology

Pause v1 expected topology changes must be empty.

Planned topology mutation -> UNSUPPORTED.

## Transition / Effect / Keyframe safety

Each category must distinguish:

- trusted absent
- unknown
- known present without proof
- known present with valid PRESERVATION_PROVEN proof
- explicit violation

Semantics:

- trusted absent -> PASS check
- unknown -> INCOMPLETE
- known present without valid proof -> REVIEW_REQUIRED
- valid bound preservation proof -> PASS check
- explicit violation -> REJECT

## PreservationProof

Implement typed immutable proof records at least for:

- TRANSITION
- EFFECT
- KEYFRAME

Safety validates:

- proof type
- ExpectedDiff binding
- snapshot/base binding
- subject binding
- proof contract version
- PRESERVATION_PROVEN outcome

Safety does not generate proofs.

No proof confidence/ranking arithmetic.

## PreservationScope

Ensure:

- every changed object is in scope
- all known impacted/dependent objects required by input evidence are in scope
- unlisted scope objects are expected unchanged

Known scope omission -> INCOMPLETE.

## ExpectedDiff integrity

Verify supplied ExpectedDiff corresponds exactly to the supplied PauseEditProposal/primary geometry.

No primary range repair.

Tampering/mismatch -> REJECT or typed invalid input, but never PASS.

## Suggested domain

Names may be refined without changing semantics:

- SafetyRequirementProfile
- ProtectionContext / ProtectedRangeRecord
- PreservationProofKind
- PreservationProof
- SafetyCheckKind
- SafetyCheckOutcome
- SafetyCheckResult
- PreflightStatus
- SafetyVerdict
- SafetyPreflightInput
- SafetyPreflightResult
- SafetyReason
- pure preflight(...)

## Required tests

At minimum prove:

1. immutable/frozen domain values
2. defensive copy / deterministic ordering
3. profile contains exactly the 17 required checks
4. non-EVALUATED result cannot carry verdict
5. EVALUATED must carry verdict
6. PASS impossible with missing mandatory check
7. status precedence STALE > UNSUPPORTED > INCOMPLETE > EVALUATED
8. verdict precedence REJECT > REVIEW_REQUIRED > PASS
9. all evaluable findings retained despite reject
10. stale base -> STALE
11. ExpectedDiff not READY_FOR_PREFLIGHT -> non-evaluated
12. ExpectedDiff/proposal primary mismatch -> reject/non-pass
13. complete empty protection context may pass protection checks
14. incomplete protection context -> INCOMPLETE
15. direct protected overlap -> REJECT
16. protected displacement -> REJECT
17. track lock FALSE -> pass check
18. track lock TRUE -> REJECT
19. track lock UNKNOWN -> INCOMPLETE
20. unresolved relationship/dependency -> INCOMPLETE
21. supported exact retime -> pass check
22. retime UNKNOWN -> INCOMPLETE
23. reverse/freeze/variable retime -> UNSUPPORTED
24. media identity mutation in displacement -> REJECT
25. source range mutation -> REJECT
26. duration mutation -> REJECT
27. track membership mutation -> REJECT
28. topology mutation -> UNSUPPORTED
29. transition absent -> pass check
30. transition unknown -> INCOMPLETE
31. transition present without proof -> REVIEW_REQUIRED
32. transition present + valid proof -> pass check
33. transition explicit violation -> REJECT
34. effect absent/unknown/present-no-proof/proven/violation same matrix
35. keyframe absent/unknown/present-no-proof/proven/violation same matrix
36. proof wrong ExpectedDiff -> non-pass
37. proof wrong snapshot/base -> non-pass
38. proof wrong subject/kind/version -> non-pass
39. changed object outside PreservationScope -> INCOMPLETE
40. known impacted object omitted from scope -> INCOMPLETE
41. all 17 checks evaluated, no review/reject -> PASS
42. one review finding, no reject -> REVIEW_REQUIRED
43. reject + review findings -> REJECT with both retained
44. confidence values do not bypass Safety
45. no automatic plan repair/replanning
46. no mapper call
47. no native snapshot capture/evaluator side effect
48. no pause planner call
49. no geometry resolver call
50. no ExpectedDiff compiler call
51. no relationship compiler/propagation
52. no authority transition
53. no FakeTimeline.apply
54. no Resolve API/mutation
55. TASK-001..014 regression remains green

## Explicitly out of scope

- actual Resolve API/mutation
- participant selection
- geometry generation
- ExpectedDiff compilation
- preservation-proof generation
- transition/effect/keyframe runtime proof producer
- track unlock/protection modification
- Safety override
- automatic replanning
- approval/authority
- transaction/rollback
- actual postflight capture
- promotion

## Workflow

1. Do not start until TASK-014 is Chat APPROVED and merged, unless Chat explicitly reorders tasks.
2. Start from then-current main.
3. Treat ADR-026 and this spec as authoritative.
4. Record ambiguity as OPEN; do not invent proof generation/runtime policies.
5. Red-first tests.
6. Implement pure immutable preflight foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_015_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.

## Success definition

Given one complete ExpectedDiff plus explicit current safety evidence, produce a complete immutable
preflight evaluation that never defaults unknown state to safe, preserves all findings, and returns
PASS only when all 17 mandatory Pause-v1 safety checks are actually evaluated and none require review
or rejection.


## TASK-015 implementation notes (before source)

- Add safety_preflight.py; retain the earlier safety.py fake executor checks unchanged.
  Import domain values only from existing layers; never invoke any upstream compiler,
  mapper, evaluator, planner, proof producer or executor.
- SafetyPreflightInput consumes DiffCompilationResult (including non-ready states for
  diagnostics), a separately supplied PauseEditProposal, current snapshot, optional
  snapshot-bound ProtectionContext and CurrentSafetyEvidence, typed proofs and fixed profile.
- CurrentSafetyEvidence enumerates affected-track locks and exact object/range subjects,
  retime kind/exact-forward fact, three structure observations, precomputed relationship/
  dependency status and assessment refs, and known impacted/dependent IDs. Missing is not
  absent. No confidence fields or native identity bridge are added.
- Primary subject is the exact removal range; displacement subject is its whole before
  range. Proofs must match this subject, ExpectedDiff ref, snapshot, kind, v1 contract and
  PRESERVATION_PROVEN outcome. Invalid/missing proof for known presence yields REVIEW;
  stale proof snapshot also contributes STALE. All supplied proof bindings remain visible.
- ProtectedRangeRecord can bind a whole object or a track range (or a range on an object).
  HARD_LOCK only. Direct removal overlap and displacement affecting protected occupancy
  are rejected; empty protection is known none only when explicitly complete.
- Each of exactly 17 SafetyCheckResults contains every individual finding. Findings retain
  subjects, reasons and evidence refs, plus status and optional evaluated outcome. A check
  may contain known REJECT findings alongside incomplete evidence without losing either.
- Result constructors validate exact mandatory coverage and status/verdict aggregation.
  Global precedence is STALE > UNSUPPORTED > INCOMPLETE > EVALUATED; only evaluated results
  receive REJECT > REVIEW_REQUIRED > PASS. Profile cannot be edited into fewer checks.
- Independently recheck supplied consequence integrity/arithmetic without calling the
  ExpectedDiff compiler. Deliberately corrupted frozen fixtures exercise preservation and
  scope guards which normal TASK-014 constructors already reject; no alternate plan schema.
- No proof production/native trust policy is established. OPEN-015 and OPEN-001/006/008/012
  remain unresolved. PASS is bound to all raw immutable inputs and is not execution authority.
