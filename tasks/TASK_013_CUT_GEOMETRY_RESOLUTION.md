# TASK-013 — Cut Geometry Resolution Foundation

Status: **Authorized after TASK-012 approval/merge; implementation in progress**

Basis:
- ADR-018 Pause / Dialogue Editing v1
- ADR-020 Observation Evidence & Producer Provenance v1
- ADR-021 Native Time & Snapshot Mapping v1
- ADR-023 Pause Edit Planning & Safety Lowering v1
- ADR-024 Cut Geometry Resolution Contract v1
- TASK-012 Planner consumes explicit PauseCutGeometry; TASK-013 is the separate pure producer-side
  geometry-resolution foundation

## Purpose

Implement a pure immutable resolver that consumes an existing TIGHTEN PauseCandidate plus explicit
typed geometry constraints and returns:

- UNRESOLVED when no exact geometry can be proven
- RESOLVED when exactly one distinct valid geometry remains
- REVIEW_REQUIRED when two or more distinct valid geometries remain
- STALE / UNSUPPORTED for corresponding contract failures

The resolver does not analyze raw media, rank alternatives, invoke Planner/Safety/Authority or edit
the timeline.

## Required v1 constraint vocabulary

Implement exactly:

- CUT_START_ANCHOR
- CUT_END_ANCHOR
- MUST_PRESERVE_RANGE
- ALLOWED_REMOVAL_RANGE

Do not introduce additional semantic/audio constraint kinds in TASK-013.

## Required confidence semantics

GeometryConfidence:

- STRONG
- MODERATE
- WEAK
- UNKNOWN

Rules:

1. confidence is producer-supplied typed metadata
2. resolver preserves it
3. resolver does not derive it
4. resolver does not convert EvidenceStrength/PauseCandidate Confidence into it
5. resolver does not use confidence to rank competing valid candidates

## Suggested domain

Names may be refined without changing semantics:

- GeometryConstraintKind
- GeometryConfidence
- GeometryProducerKind
- GeometryProducerRef
- GeometryConstraint
- ExplicitGeometryInput or equivalent
- CutGeometryCandidate
- GeometryResolutionStatus
- GeometryResolutionReason
- GeometryResolutionResult
- pure resolve_geometry(...)

## Binding requirements

Every constraint/input must be bound to the same:

- timeline ID
- base version
- object/placement identity
- original pause range
- target PauseCandidate identity/reference
- geometry contract version

Mixed bindings must not be silently merged.

Current snapshot/version mismatch -> STALE.

Do not call TASK-010 mapper or TASK-011 adapter/readiness evaluator. Consume already-aligned/current
internal frame-domain inputs only.

## TIGHTEN duration rule

For pause duration P and suggested retained K:

```text
required_removal = P - K
```

A valid candidate removed range must:

- be one contiguous FrameRange
- be contained inside original pause
- have exactly required_removal duration
- not overlap any MUST_PRESERVE_RANGE
- satisfy ALLOWED_REMOVAL constraints

No clamp, shift, nearest anchor or duration repair.

## Explicit geometry path

Allow one or more explicitly supplied exact removed ranges.

Each is validated independently.

Invalid explicit geometry does not get repaired.

## Anchor-pair path

Generate candidates only from explicit:

- CUT_START_ANCHOR
- CUT_END_ANCHOR

pairs.

A pair is valid only when:

```text
start < end
end - start == required_removal
```

and all preserve/allowed constraints pass.

Do not synthesize missing anchors.

## ALLOWED_REMOVAL_RANGE semantics

For TASK-013 v1, when one or more applicable ALLOWED_REMOVAL_RANGE constraints are present, candidate
removed range must be fully contained in **every** applicable allowed range.

This is conservative intersection semantics.

Do not treat multiple allowed ranges as alternatives/unions in v1.

## MUST_PRESERVE_RANGE semantics

Any overlap between a candidate removal range and any preserve range invalidates that candidate.

Do not trim/move candidate geometry to avoid preserve ranges.

## Distinct geometry / provenance

Distinct geometry is based on exact removed range for the same bound candidate.

If multiple producers/constraints support the same exact range, do not count that as multiple
competing geometries merely because provenance differs.

However, retain all supporting producer/constraint provenance for the canonical candidate.

## Resolution rule

Mandatory:

```text
0 distinct valid geometries -> UNRESOLVED
1 distinct valid geometry  -> RESOLVED
2+ distinct valid geometries -> REVIEW_REQUIRED
```

Confidence must not change this rule.

## Deterministic ordering

Outputs/candidates/provenance may be canonically sorted for deterministic equality.

Sorting order must not imply preference.

## Suggested statuses

- RESOLVED
- REVIEW_REQUIRED
- UNRESOLVED
- STALE
- UNSUPPORTED

## Suggested reasons

At minimum cover:

- UNIQUE_GEOMETRY
- MULTIPLE_GEOMETRIES
- INSUFFICIENT_CONSTRAINTS
- NO_VALID_ANCHOR_PAIR
- REQUIRED_DURATION_MISMATCH
- PRESERVE_RANGE_CONFLICT
- OUTSIDE_ALLOWED_REMOVAL
- STALE_BINDING
- MIXED_BINDING
- MULTI_RANGE_UNSUPPORTED
- CROSS_PLACEMENT_UNSUPPORTED
- UNSUPPORTED_CONTRACT

## Required tests

At minimum prove:

1. immutable/frozen producer, constraint, candidate and result values
2. defensive tuple copies / deterministic ordering
3. exactly four v1 constraint kinds
4. GeometryConfidence distinct from EvidenceStrength and PauseCandidate Confidence
5. GeometryConfidence accepts only typed values
6. confidence is retained but does not affect resolution count
7. retained duration alone -> UNRESOLVED
8. no default leading/trailing/center/symmetric geometry
9. valid explicit geometry -> RESOLVED when unique
10. explicit geometry wrong duration -> invalid/unresolved
11. explicit geometry outside pause -> invalid
12. exact anchor pair -> candidate generation
13. missing start anchor -> UNRESOLVED
14. missing end anchor -> UNRESOLVED
15. no exact-duration pair -> UNRESOLVED
16. two valid anchor-pair geometries -> REVIEW_REQUIRED
17. STRONG vs WEAK alternatives still REVIEW_REQUIRED
18. identical geometry from two producers counts as one distinct geometry
19. identical geometry retains both provenance/support sets
20. MUST_PRESERVE overlap invalidates candidate
21. preserve range does not cause automatic cut shifting
22. ALLOWED_REMOVAL contains candidate -> valid
23. candidate outside one applicable allowed range -> invalid
24. multiple allowed ranges use intersection semantics
25. no ALLOWED_REMOVAL constraint is permitted when explicit anchors/geometry suffice
26. mixed timeline/version/object/pause binding rejected/non-ready
27. current-version mismatch -> STALE
28. no silent rebase
29. one contiguous removal range only
30. cross-placement/multi-range unsupported
31. candidate derived retained-leading/trailing totals are exact
32. resolved candidate retained total equals PauseCandidate suggested retained frames
33. resolver never changes PauseAction
34. deterministic result independent of input order
35. no mapper call
36. no native snapshot adapter/readiness call
37. no pause classifier call
38. no TASK-012 planner call
39. no relationship compiler/propagation
40. no safety.preflight
41. no authority transition
42. no FakeTimeline.apply
43. no audio/VAD/STT/prosody/LLM imports/side effects
44. TASK-001..012 regression remains green

## Explicitly out of scope

- raw media/audio decode
- waveform analysis
- VAD/STT/diarization/prosody/breath detection
- semantic/LLM geometry inference
- GeometryConfidence calibration/derivation
- ranking of alternatives
- multiple removed ranges
- ALLOWED_REMOVAL union/alternative semantics
- cross-placement geometry
- planner execution
- dependency propagation
- Safety evaluation
- ripple execution
- seam/crossfade/room-tone treatment
- Resolve API/mutation
- telemetry/DB/network/UI
- numeric geometry-quality thresholds

## Workflow

1. Do not start until TASK-012 is Chat APPROVED and merged, unless Chat explicitly reorders tasks.
2. Start from then-current main.
3. Treat ADR-024 and this spec as authoritative.
4. Record architecture ambiguity as OPEN; do not invent ranking/confidence derivation/audio semantics.
5. Red-first tests.
6. Implement pure immutable geometry-resolution foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_013_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.

## Success definition

Given a TIGHTEN candidate and explicit current typed constraints, the foundation produces only exact
one-range geometry candidates, preserves ambiguity and provenance, and returns RESOLVED only when one
distinct valid geometry remains — without guessing cut location, deriving confidence, ranking
alternatives, analyzing media or crossing execution boundaries.


## Implementation notes (before source)

`cut_geometry.py` reuses PlanningBinding and existing integer FrameRange; no Planner call.
GeometryResolutionInput includes caller resolution ref, TIGHTEN candidate, binding/current
NativeSnapshotRef, explicit placement span and precomputed MappingStatus. Only current EXACT
already-aligned input is considered. No mapping/native identity discovery occurs.

Constraint payloads are typed integer anchors or FrameRange values according to exactly four
kinds. ExplicitGeometryInput keeps a tuple of supplied ranges so multi-range input can return
UNSUPPORTED without repair. Duplicate source IDs reject. Mixed binding/version/contract or
out-of-pause constraint scope blocks the bundle rather than silently dropping constraints.
Invalid individual one-range explicit geometries/anchor pairs are diagnosed independently.

Candidate ranges arise only from each explicit geometry or explicit start/end pair. Every
preserve/allowed constraint applies to each candidate; allowed constraints use intersection.
Canonical output sorts by exact range, never preference. Equal ranges merge support records
including every contributing producer, supplied GeometryConfidence and constraint/input ID.
Candidate confidence metadata is per-support (with a descriptive set of supplied labels),
not an invented aggregate/winning confidence. This avoids deciding deferred calibration policy.

Retained leading/trailing/total values are derived from the unmodified range. Candidate IDs
are deterministic within caller resolution_ref plus boundaries; not persistent native IDs.
Results retain immutable raw inputs and rejection diagnostics. 0/1/2+ valid distinct ranges
map to UNRESOLVED/RESOLVED/REVIEW_REQUIRED, barring stale/unsupported contract failures.
Non-TIGHTEN actions are UNSUPPORTED, unchanged; no REMOVE helper or Planner lowering is added.
