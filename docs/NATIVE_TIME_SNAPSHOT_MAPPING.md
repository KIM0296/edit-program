# Native Time & Snapshot Mapping Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define how native/source/timeline time coordinates may be converted into the project's existing
integer half-open FrameRange domain without guessing, rounding, or silently rebasing across human
timeline edits.

Core rule:

> Time must be mapped, not guessed.

A coordinate that is almost correct is still the wrong edit target.

## Time domains

v1 distinguishes at least:

- TIMELINE_FRAME: zero-based frame address in a captured timeline snapshot.
- SOURCE_FRAME: zero-based addressable frame in a source-media domain.

Equal integers in different domains are not interchangeable.

SMPTE/native timecode strings are labels/addresses at adapter boundaries, not arithmetic primitives.
Float seconds are not authoritative mapping values.

## Internal primitive remains integer FrameRange

ADR-008 remains unchanged:

- internal ranges are integer half-open [start, end)
- v1 does not introduce sub-frame/rational time as the system-wide domain primitive
- if future audio/sample-accurate requirements prove this insufficient, that requires a separate ADR

Exact rational arithmetic may be used inside the mapping layer to decide whether an integer boundary
exists. A non-integer result is not rounded into the internal domain.

## Exact FrameRate metadata

Frame-rate metadata is represented exactly as a positive rational numerator/denominator, for example:

- 24/1
- 25/1
- 30000/1001
- 30/1
- 60000/1001

23.976 must not be normalized to 24, and 29.97 must not be normalized to 30.

Drop-frame/non-drop-frame is a timecode-label policy and is distinct from the actual frame cadence.

Important: frame-rate metadata alone does **not** prove source↔timeline correspondence.

## Native snapshot identity

Mapping belongs to one captured native timeline state.

Recommended immutable value:

- timeline_id
- timeline_version
- state_token

`timeline_version` is the product-side version contract already used by candidates/plans.
`state_token` is an opaque adapter-supplied identity for mapping-relevant captured native state.

The pure foundation may validate caller-supplied tokens, but it does not claim to prove Resolve truth.
How a future Resolve Adapter derives/verifies the token is outside TASK-010.

A snapshot mismatch is STALE in v1. No scope-aware reuse or silent rebase.

## Placement temporal binding

Mapping authority is placement-specific, not filename- or media-only.

A binding identifies at least:

- snapshot_ref
- object/placement identity
- media identity
- timeline_range
- source_range
- timeline_rate
- source_rate
- mapping_kind
- mapping_id/version or opaque mapping reference

Same media may appear multiple times. Media identity alone must not locate a placement.

Production persistent TimelineItem identity remains OPEN-001.

## Mapping kinds

v1 domain may express:

- IDENTITY_1X
- AFFINE_FORWARD
- REVERSE
- FREEZE
- VARIABLE_RETIME
- UNKNOWN

Only IDENTITY_1X and explicitly supplied AFFINE_FORWARD mappings are eligible for exact pure range
mapping in TASK-010.

REVERSE, FREEZE, VARIABLE_RETIME and UNKNOWN are represented but return UNSUPPORTED for lowering in
the v1 foundation.

This does not establish INV-007 retime safety.

## Explicit mapping, never FPS inference

Mixed FPS is supported structurally, but a mapping is **never derived solely from source FPS and
timeline FPS**.

For example, a 30/1 source on a 24/1 timeline does not by itself authorize a 30:24 affine mapping.
The adapter/caller must supply authoritative placement correspondence.

TASK-010 evaluates only that explicit correspondence.

## Exact affine boundary rule

For an explicit affine segment:

- source [S0, S1)
- timeline [T0, T1)

mapping a source boundary s uses exact rational arithmetic conceptually equivalent to:

```text
mapped = T0 + (s - S0) * (T1 - T0) / (S1 - S0)
```

The result is EXACT only when the mapped boundary is an integer timeline frame.

The inverse timeline→source mapping follows the same rule.

A range is EXACT only if both start and end boundaries map exactly.

No round/floor/ceil/clamp is permitted.

## Mixed-FPS policy

Mixed FPS is **not globally prohibited**.

Results distinguish:

- EXACT: explicit mapping exists and requested boundaries land exactly on integer internal frames.
- NON_INTEGRAL: explicit mapping exists, but one or more requested boundaries do not land exactly on
  integer frames.

NON_INTEGRAL never becomes EXACT through rounding.

This is the accepted v1 policy.

## Mapping status

Minimum statuses:

- EXACT
- STALE
- AMBIGUOUS
- NON_INTEGRAL
- OUT_OF_RANGE
- UNSUPPORTED

EXACT means temporal correspondence is exact for the supplied snapshot/binding. It is not edit,
approval, candidate or safety authority.

### STALE

Current snapshot identity does not match the mapping snapshot.

### AMBIGUOUS

The request corresponds to multiple placement/fragment mappings or cannot be uniquely resolved.

### NON_INTEGRAL

Exact correspondence exists mathematically but cannot be represented as integer frame boundaries.

### OUT_OF_RANGE

The requested range is outside the explicit mapped span. Do not clamp.

### UNSUPPORTED

The transform or correspondence is outside the v1 supported subset.

## Mapping results

A pure result carries:

- status
- machine-readable reasons
- source snapshot/binding identity
- source and timeline ranges when exact
- object/placement and media identity when exact

Only EXACT may carry a complete mapped range usable by later evidence preparation.

## Source↔timeline direction

Both directions use the same explicit binding proof:

- source range → timeline range for source-oriented producers such as STT/VAD
- timeline range → source range for Resolve selections/context lookup

Neither direction may use implicit offset arithmetic unless the binding kind explicitly supports it.

## Split fragments

A split placement lineage may contain multiple concrete fragments.

Within one captured snapshot, a concrete mapping must identify the relevant fragment through explicit
timeline/source spans rather than lineage ID alone.

This does not solve production persistent identity.

## Cross-placement ranges

A range spanning multiple placements/fragments must not be collapsed into one SourceRange.

Future systems may return a sequence of mapped fragments, but ADR-020/TASK-009 v1 consumes
single-placement evidence.

Therefore a multi-placement result is AMBIGUOUS or UNSUPPORTED for current evidence preparation.

## Snapshot staleness / Human Edit Wins

Mappings are snapshot-bound.

If the human changes Resolve after capture and the current snapshot ref differs:

```text
mapping -> STALE
evidence derived from it -> cannot be current READY evidence
```

Do not:

- reuse because positions look similar
- reuse because source ranges match
- rebind by filename
- automatically rebase to the new version

Scope-aware partial reuse remains deferred under OPEN-008.

## Identity requirements

Mapping validates both placement identity and media identity.

Do not infer identity solely from:

- filename
- duration
- similar timecode
- overlapping source range
- track ordinal/name

OPEN-001 and OPEN-006 remain authoritative unresolved production identity/correspondence topics.

## Timecode and start offsets

Timeline/source native start timecodes may be non-zero.

They are adapter-edge metadata used to convert native labels into zero-based frame addresses.
Internal FrameRange values do not store SMPTE label offsets.

TASK-010 does not need to implement a full Resolve/SMPTE timecode parser.

## Retime boundary

v1 pure mapping support:

- IDENTITY_1X: supported
- explicit AFFINE_FORWARD: supported when exact integer boundaries result
- REVERSE: UNSUPPORTED
- FREEZE: UNSUPPORTED
- VARIABLE_RETIME: UNSUPPORTED
- UNKNOWN: UNSUPPORTED

Do not treat unsupported retimes as 1:1.

## Relationship to ADR-020 Evidence

ADR-020 evidence binding must receive an already-aligned internal range from an EXACT current mapping
when native/source coordinates are involved.

```text
native/source coordinates
        ↓
temporal mapping
        ↓
EXACT internal range
        ↓
EvidenceBinding
        ↓
PauseObservation preparation
```

STALE/NON_INTEGRAL/AMBIGUOUS/OUT_OF_RANGE/UNSUPPORTED mapping cannot silently produce READY evidence.

## Relationship to StableTarget

Existing StableTarget already records timeline/version/placement/media/timeline range/source range in
the fake domain.

TASK-010 does not create executable StableTargets or lower mappings into EditPlans. Future lowering
requires production identity plus ordinary Safety/Authority checks.

## Immutability / determinism

Frame-rate values, snapshot refs, placement bindings and mapping results are immutable.

The same snapshot + explicit binding + input range must produce the same pure mapping result.

Refreshing mapping creates new values; historical values are not mutated.

## TASK-010 implementation boundary

Implement only:

- exact rational FrameRate value
- typed coordinate-domain values/ranges or equivalent type-safe wrappers
- immutable NativeSnapshotRef
- immutable PlacementTemporalBinding
- MappingKind
- MappingStatus and machine-readable reasons
- pure IDENTITY_1X mapping
- pure explicit AFFINE_FORWARD source↔timeline mapping
- exact integer-boundary validation
- same-snapshot/staleness checks against supplied refs
- placement/media binding validation
- OUT_OF_RANGE / NON_INTEGRAL / AMBIGUOUS / UNSUPPORTED results
- immutable deterministic tests

Do not implement:

- Resolve API calls
- SMPTE/Resolve parser as a production adapter
- automatic source↔timeline correspondence discovery
- mapping inferred solely from FPS
- filename matching
- persistent Resolve identity
- scope-aware stale reuse
- reverse/freeze/variable-retime lowering
- sub-frame system-wide primitive
- media decode
- STT/VAD/prosody
- actual evidence generation
- StableTarget/EditPlan lowering
- Safety/Authority execution
- DB/network/UI

## Deferred / still open

- OPEN-001 production persistent TimelineItem identity
- OPEN-006 native track/object correspondence
- OPEN-008 scope-aware invalidation / partial refresh
- native Resolve state-token derivation
- full native timecode/drop-frame parsing at adapter edge
- reverse/freeze/variable retime production correspondence
- audio-sample/sub-frame precision if proven necessary by real use

## Accepted v1 decisions

1. Mixed FPS is not globally banned.
2. Mixed-FPS requests are EXACT only when explicit mapping yields exact integer boundaries.
3. Non-integral boundaries are NON_INTEGRAL and never rounded.
4. Frame-rate metadata alone never creates source↔timeline mapping.
5. The system-wide primitive remains integer half-open FrameRange.
6. Sub-frame/rational time is not introduced as the global domain primitive in v1.
