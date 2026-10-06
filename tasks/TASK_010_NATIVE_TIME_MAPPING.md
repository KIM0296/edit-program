# TASK-010 — Native Time & Snapshot Mapping Foundation

Status: **PREPARED, NOT AUTHORIZED UNTIL TASK-009 IS APPROVED/MERGED**

Basis:
- ADR-008 Integer Half-open Internal FrameRange
- ADR-012 Fake Placement Lineage Identity
- ADR-015 Candidate Authority
- ADR-016 Human Priority / No Silent Rebase
- ADR-020 Observation Evidence & Producer Provenance
- ADR-021 Native Time & Snapshot Mapping v1
- OPEN-001 / OPEN-006 / OPEN-008 remain unresolved where noted

## Purpose

Implement a pure immutable temporal-mapping foundation that can prove exact source↔timeline frame
correspondence for an explicit placement binding, without Resolve API calls and without guessing from
FPS, filenames or similar metadata.

## Mandatory decisions

- Internal project ranges remain integer half-open FrameRange.
- FrameRate metadata uses exact rational numerator/denominator.
- Mixed FPS is supported only through explicit mapping correspondence.
- Result is EXACT only when both requested boundaries map to integer frames.
- Non-integral boundaries return NON_INTEGRAL; never round/floor/ceil.
- FPS values alone never synthesize placement mapping.
- Snapshot mismatch is STALE in v1; no silent rebase.
- EXACT mapping is not execution/approval/safety authority.
- IDENTITY_1X and explicit AFFINE_FORWARD are the only mapping kinds lowered in v1.
- REVERSE/FREEZE/VARIABLE_RETIME/UNKNOWN are UNSUPPORTED.

## Suggested domain

Names may be refined without changing semantics:

- FrameRate(numerator, denominator)
- TimeDomain: TIMELINE_FRAME / SOURCE_FRAME
- typed frame address/range wrapper or another type-safe domain distinction
- NativeSnapshotRef(timeline_id, timeline_version, state_token)
- PlacementTemporalBinding
- MappingKind
- MappingStatus
- MappingReason
- TemporalMappingResult

Placement binding must carry explicit snapshot, placement/object identity, media identity, timeline
range, source range, exact source/timeline rates and mapping kind.

## Pure operations

Support:

1. source range -> timeline range
2. timeline range -> source range
3. current snapshot check using caller-supplied NativeSnapshotRef
4. exact integer boundary validation
5. range containment / out-of-range validation

For explicit affine mapping use exact integer/rational arithmetic only. Do not use float seconds.

## Important safety rule

Do not derive affine correspondence from frame-rate ratio.

Example:

```text
source_rate = 30/1
timeline_rate = 24/1
```

does not prove a 30:24 mapping.

Only an explicit PlacementTemporalBinding provides mapping authority.

## Required statuses

- EXACT
- STALE
- AMBIGUOUS
- NON_INTEGRAL
- OUT_OF_RANGE
- UNSUPPORTED

Do not clamp or normalize a failed mapping into EXACT.

## Split / repeated media

Same media may appear in multiple placements. media_id alone is insufficient.

A mapping must bind a specific placement and concrete source/timeline spans. If a request cannot
resolve uniquely to one explicit binding, return AMBIGUOUS rather than selecting by filename/range.

Production persistent identity remains OPEN-001.

## Required tests

At minimum prove:

1. FrameRate is positive exact rational and canonical/equivalent rates compare deterministically.
2. 30000/1001 is not treated as 30/1.
3. timeline/source coordinates cannot be silently interchanged.
4. IDENTITY_1X source->timeline exact mapping.
5. IDENTITY_1X timeline->source exact mapping.
6. Explicit AFFINE_FORWARD source->timeline exact mapping.
7. Explicit AFFINE_FORWARD inverse mapping.
8. Mixed-FPS explicit mapping may be EXACT at integral boundaries.
9. Mixed-FPS non-integral boundary returns NON_INTEGRAL.
10. No rounding/floor/ceil path turns non-integral into EXACT.
11. Both range boundaries must be exact.
12. OUT_OF_RANGE does not clamp.
13. wrong placement identity rejects/non-EXACT.
14. wrong media identity rejects/non-EXACT.
15. timeline/version/state-token mismatch -> STALE.
16. no silent stale rebase.
17. multiple candidate bindings -> AMBIGUOUS.
18. repeated same media placements remain distinct.
19. split fragments require concrete range correspondence.
20. cross-placement single mapping is not EXACT.
21. REVERSE -> UNSUPPORTED.
22. FREEZE -> UNSUPPORTED.
23. VARIABLE_RETIME -> UNSUPPORTED.
24. UNKNOWN -> UNSUPPORTED.
25. frame-rate ratio alone cannot construct/authorize mapping.
26. same input -> same deterministic result.
27. inputs/outputs immutable.
28. no Resolve API, pause classifier, authority transition, safety preflight or FakeTimeline.apply.
29. TASK-001..009 regression remains green.

## Explicitly out of scope

No Resolve integration, native object discovery, SMPTE parser requirement, media decoding, STT/VAD,
Evidence production, persistent native identity, automatic fragment rebinding, scope-aware refresh,
reverse/freeze/variable-retime lowering, sub-frame global domain, StableTarget/EditPlan lowering,
timeline mutation, DB/telemetry/network/UI.

## Workflow

1. Do not start until TASK-009 is Chat APPROVED and merged.
2. Start from then-current main.
3. Treat this file and ADR-021 as authoritative.
4. Record architectural ambiguity as OPEN; do not invent production behavior.
5. Red-first tests.
6. Implement pure immutable mapping foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_010_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.
