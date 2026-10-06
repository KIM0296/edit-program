# Cut Geometry Resolution Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define how a TIGHTEN PauseCandidate may obtain one or more exact cut-geometry candidates without
allowing retained duration alone, hidden ranking, or raw media inference to choose a cut location.

ADR-023 remains authoritative:

> A Pause decision specifies editorial intent, not cut geometry.

> TIGHTEN may not be lowered to an EditPlan until exact retained/removed temporal geometry is
> explicitly resolved.

ADR-024 adds:

> Duration tells us how much time should remain. Geometry evidence tells us where the edit may occur.
> If more than one exact geometry remains plausible, preserve the alternatives instead of pretending
> certainty.

This contract does not execute edits and does not grant Safety or Authority permission.

## Architecture position

```text
PauseCandidate
      +
Exact/current target context
      +
Typed geometry constraints
      ↓
Cut Geometry Resolver
      ↓
0 / 1 / many CutGeometryCandidate values
      ↓
GeometryResolutionResult
      ↓
resolved PauseCutGeometry only when exactly one valid candidate remains
      ↓
ADR-023 / TASK-012 Planner
```

The resolver is not an EditPlan builder.

## Three confidence/evidence axes remain separate

The following are different concepts and may not be implicitly converted:

- ADR-020 EvidenceStrength
- PauseCandidate editorial Confidence
- GeometryConfidence

GeometryConfidence is producer-supplied descriptive metadata only.

It is not:

- a calibrated probability
- a Safety score
- an approval score
- a ranking weight
- an apply permission

## GeometryConfidence v1

Minimum values:

- STRONG
- MODERATE
- WEAK
- UNKNOWN

The resolver validates and preserves this typed value. It does not derive GeometryConfidence from
EvidenceStrength, candidate confidence, producer kind, number of constraints or agreement counts.

Forbidden examples:

- average input EvidenceStrength values
- strongest producer wins
- human => STRONG
- two anchors agree => STRONG
- semantic model => MODERATE

Any future confidence-derivation policy requires a separate approved contract.

## Confidence never ranks competing valid geometry

Given:

```text
Geometry A = STRONG
Geometry B = MODERATE
```

if both are structurally valid, v1 still returns multiple-candidate review.

The resolver may not choose A merely because its GeometryConfidence is stronger.

## Producer provenance

Every geometry-producing input/candidate must retain explicit provenance sufficient for audit.

Recommended producer metadata:

- producer_kind
- producer_name
- producer_version
- geometry_contract_version
- optional producer_config_ref
- source_constraint_ids

Initial producer kinds may represent:

- EXPLICIT_CALLER
- DETERMINISTIC_RULE
- FUTURE_MODEL

The foundation does not implement FUTURE_MODEL inference.

## v1 raw-media boundary

TASK-013 does not perform:

- audio decode
- waveform analysis
- VAD
- STT
- diarization
- prosody analysis
- breath detection
- room-tone analysis
- semantic/LLM geometry inference

Future producers may create typed constraints from such analysis, but that producer layer is separate
from the pure geometry resolver.

## Geometry constraint vocabulary v1

The v1 constraint vocabulary is deliberately limited to exactly four kinds:

1. CUT_START_ANCHOR
2. CUT_END_ANCHOR
3. MUST_PRESERVE_RANGE
4. ALLOWED_REMOVAL_RANGE

Do not add implicit semantic aliases or raw audio-specific constraint kinds in TASK-013.

### CUT_START_ANCHOR

An exact internal-frame boundary that may be used as the start of the one contiguous removal range.

### CUT_END_ANCHOR

An exact internal-frame boundary that may be used as the end of the one contiguous removal range.

### MUST_PRESERVE_RANGE

An internal range within the pause that a valid removal geometry may not overlap.

This may later represent speech, breath, room tone or other semantics, but the resolver treats it
only as an explicit preserve constraint.

### ALLOWED_REMOVAL_RANGE

An internal range inside which a valid removal geometry must be fully contained when such a
constraint is supplied.

The resolver does not infer why the range is allowed.

## Constraint binding

Each GeometryConstraint is immutable and bound to at least:

- constraint_id
- timeline_id
- base_version
- object/placement identity
- original_pause_range
- constraint_kind
- exact boundary or FrameRange payload
- producer provenance
- GeometryConfidence or explicit provenance reference to it

All constraints participating in one resolution must belong to the same candidate/base target.

Do not merge constraints across timeline/version/placement/pause identities.

## Exact mapping first

Geometry constraints operate only in the already-resolved internal timeline frame domain.

If native/source evidence requires mapping, ADR-021 must resolve it first.

The geometry resolver must not call map_range or derive native/source correspondence itself.

The following mapping outcomes cannot be treated as geometry-ready:

- STALE
- AMBIGUOUS
- NON_INTEGRAL
- OUT_OF_RANGE
- UNSUPPORTED

## Human Edit Wins

Candidate and geometry constraints are base-snapshot/version bound.

If current timeline state changes, geometry resolution is stale.

Do not silently shift, rebase, clamp or regenerate old anchors onto a new timeline version.

## TIGHTEN removal duration

Let:

- P = original pause duration
- K = PauseCandidate suggested_retained_frames

Then:

```text
required_removal = P - K
```

The resolver may not change K merely to make a candidate fit.

The resolver may not choose a nearest duration.

## Duration is never location authority

Absent explicit geometry evidence, the following are forbidden:

- preserve the leading K frames
- preserve the trailing K frames
- remove the center
- symmetric 50/50 retention
- choose the nearest legal anchor
- slide the requested range until it fits

No valid exact candidate means UNRESOLVED.

## v1 geometry cardinality

ADR-023 remains authoritative: a TIGHTEN geometry contains exactly one contiguous removed range.

TASK-013 generates/validates only one-range candidates.

Multiple removed ranges are UNSUPPORTED in v1.

## Candidate production path A: explicit geometry

A caller may provide one or more exact candidate removed ranges.

The resolver validates them against:

- same binding/base
- pause containment
- required removal duration
- MUST_PRESERVE_RANGE
- ALLOWED_REMOVAL_RANGE
- v1 one-range cardinality

The resolver does not assume caller-provided means valid or approved.

## Candidate production path B: explicit anchor pairs

The resolver may construct candidate ranges from supplied start/end anchors.

For every candidate pair:

```text
start < end
end - start == required_removal
```

and the resulting range must satisfy all preserve/allowed constraints.

The resolver must not generate additional anchors.

## Example

```text
pause = [100,160)
retained = 20
required_removal = 40

start anchors = {110,120}
end anchors   = {150,160}
```

Valid exact pairs:

```text
[110,150)
[120,160)
```

Both remain valid candidates.

The resolver does not select one.

## MUST_PRESERVE_RANGE behavior

A candidate removed range overlapping any MUST_PRESERVE_RANGE is invalid.

The resolver does not move or shorten the candidate to avoid the preserve constraint.

## ALLOWED_REMOVAL_RANGE behavior

If one or more ALLOWED_REMOVAL_RANGE constraints are supplied, a candidate must satisfy the explicit
contract chosen for that bundle.

For v1 foundation, the conservative rule is:

> a candidate must be fully contained in every applicable ALLOWED_REMOVAL_RANGE constraint in the
> same resolution bundle.

This avoids silently choosing one competing allowed region.

If future use cases need union/alternative allowed regions, that requires an explicit contract
change.

## ALLOWED_REMOVAL_RANGE is optional

A valid explicit geometry or exact anchor pair may resolve without an ALLOWED_REMOVAL_RANGE.

But retained duration alone never creates geometry.

## Candidate identity and provenance

Each CutGeometryCandidate should retain:

- geometry_id
- candidate reference
- timeline/base/object binding
- original_pause_range
- removed_range
- retained_leading_frames
- retained_trailing_frames
- retained_total_frames
- GeometryConfidence
- producer/provenance
- source_constraint_ids

The candidate is descriptive geometry, not Planner/Safety/Authority permission.

## Derived retained metadata

For pause P and removed range R:

```text
leading_retained = R.start - P.start
trailing_retained = P.end - R.end
retained_total = leading_retained + trailing_retained
```

and retained_total must equal candidate suggested_retained_frames.

These are deterministic derived values, not new editorial decisions.

## Multiple producers / duplicate candidates

Two different producers may produce the same removed range.

The resolver must not silently discard provenance.

v1 may canonicalize equal geometric ranges into one geometric candidate only if it retains the full
set of supporting producer/constraint provenance.

Otherwise preserve distinct candidate artifacts.

What matters is that equal geometry is not mistaken for competing geometry, while provenance is not
lost.

## No hidden ranking

v1 explicitly forbids selecting candidates by:

- GeometryConfidence
- EvidenceStrength
- producer kind
- producer version recency
- insertion order
- lexical ID order
- center proximity
- leading/trailing preference
- number of supporting constraints

Deterministic ordering for output/audit is allowed, but output ordering carries no preference.

## Resolution rule

The v1 resolution rule is intentionally simple:

```text
0 distinct valid geometries
→ UNRESOLVED

1 distinct valid geometry
→ RESOLVED

2+ distinct valid geometries
→ REVIEW_REQUIRED
```

A distinct geometry is defined by its exact removed range for the same bound PauseCandidate.

Confidence does not alter this rule.

## GeometryResolutionStatus

Minimum statuses:

- RESOLVED
- REVIEW_REQUIRED
- UNRESOLVED
- STALE
- UNSUPPORTED

## Status meanings

### RESOLVED

Exactly one distinct valid geometry remains and all required binding/currentness checks pass.

### REVIEW_REQUIRED

Two or more distinct valid geometry alternatives remain, or explicit non-fatal constraint conflicts
require human choice.

### UNRESOLVED

No exact geometry can be produced from the supplied valid constraints.

Insufficient evidence is not an error and must not trigger a guessed default.

### STALE

Candidate/constraint/current snapshot binding is no longer current.

### UNSUPPORTED

The request requires behavior outside v1, such as multi-placement or multi-range geometry.

## GeometryResolutionReason

Recommended reasons include:

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

TASK-013 may refine names without weakening semantics.

## Conflict preservation

Conflicting/alternative constraints remain visible in the result.

Do not apply latest-wins.

Do not average boundaries.

Do not choose the strongest confidence.

## Geometry confidence and conflict

Two STRONG alternatives are still REVIEW_REQUIRED.

STRONG + WEAK alternatives are also REVIEW_REQUIRED when both are valid.

Confidence is descriptive metadata only.

## Geometry resolution cannot change editorial action

The resolver may not convert:

- TIGHTEN -> KEEP
- TIGHTEN -> REMOVE
- REMOVE -> TIGHTEN

If TIGHTEN cannot resolve geometry, it remains an unresolved TIGHTEN.

## REMOVE relationship

REMOVE geometry is already deterministic in ADR-023:

```text
removed_range = original_pause_range
retained = 0
```

ADR-024 primarily governs TIGHTEN geometry.

TASK-013 may expose a pure helper to create/validate the ADR-023 full-pause REMOVE geometry only if
that does not blur the TIGHTEN resolver boundary.

## Geometry vs seam treatment

Geometry specifies which timeline frames are removed.

It does not decide:

- audio crossfade
- fade curve
- room-tone fill
- click repair
- spectral repair
- transition duration
- effect treatment

Those belong to later execution/effect contracts.

## Crosstalk / multi-speaker

If future producers cannot express safe exact constraints for crosstalk/overlap, the resolver does
not infer them.

Ambiguous/unsupported inputs remain review/non-ready.

## Geometry quality is a separate evaluation problem

Decision quality and geometry quality are different:

```text
Decision:
Was TIGHTEN the right editorial action?

Geometry:
Was this exact cut location natural/acceptable?
```

Future benchmark/pilot data should distinguish:

- decision accepted + geometry accepted
- decision accepted + geometry modified
- decision rejected

Do not encode numeric geometry thresholds before real pilot evidence.

## Reference ambiguity

Future benchmark reference may allow:

- multiple acceptable exact geometries
- acceptable boundary windows
- preferred geometry plus acceptable alternatives

Do not assume one frame-perfect answer always exists.

## TASK-013 boundary

A future TASK-013 may implement pure immutable geometry-resolution foundation only:

- GeometryConstraintKind with exactly four v1 kinds
- GeometryConstraint
- GeometryProducerRef / provenance
- GeometryConfidence
- CutGeometryCandidate
- GeometryResolutionStatus / Reason / Result
- explicit-geometry validation
- explicit anchor-pair candidate generation
- MUST_PRESERVE filtering
- ALLOWED_REMOVAL filtering
- deterministic equal-geometry deduplication with provenance retention
- 0/1/2+ resolution rule
- immutable/deterministic tests

Do not implement:

- raw audio analysis
- VAD/STT/prosody/breath/semantic models
- confidence derivation
- candidate ranking
- Planner execution
- relationship propagation
- Safety PASS
- Resolve API/mutation
- seam treatment
- telemetry/DB/network/UI

## Accepted v1 decisions

1. Geometry constraint vocabulary is exactly CUT_START_ANCHOR, CUT_END_ANCHOR,
   MUST_PRESERVE_RANGE, ALLOWED_REMOVAL_RANGE.
2. GeometryConfidence is producer-supplied typed descriptive metadata only.
3. Resolver does not derive or calibrate GeometryConfidence.
4. GeometryConfidence never ranks valid alternatives.
5. Retained duration determines removal amount, never cut location.
6. Exact/current mapping precedes geometry resolution.
7. TIGHTEN v1 supports one contiguous removed range.
8. Explicit geometry and explicit anchor pairs are the only v1 candidate-production paths.
9. MUST_PRESERVE ranges invalidate overlapping candidates.
10. ALLOWED_REMOVAL ranges constrain candidate containment; v1 uses conservative intersection
    semantics across applicable allowed ranges.
11. 0 distinct valid geometries -> UNRESOLVED.
12. 1 distinct valid geometry -> RESOLVED.
13. 2+ distinct valid geometries -> REVIEW_REQUIRED.
14. No hidden ranking or latest-wins.
15. Geometry resolution never changes the editorial action.
16. Geometry does not decide ripple mechanics, Safety, Authority or seam treatment.

## Final principle

> Duration tells us how much time should remain. Geometry evidence tells us where the edit may occur.
> If more than one exact geometry remains plausible, preserve the alternatives instead of pretending
> certainty.
