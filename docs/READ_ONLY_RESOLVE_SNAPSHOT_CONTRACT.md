# Read-only Resolve Snapshot & Adapter Observation Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define a read-only, immutable observation contract between DaVinci Resolve and the existing
timeline-mapping / evidence / safety architecture.

Resolve remains the Source of Truth. A snapshot is only a captured observation of Resolve state at a
specific point in time; it is never an independent authoritative timeline.

Core principle:

> The adapter reports what Resolve actually exposes, not what the AI wishes were true.

Unknown native state must reduce automation rather than be filled by inference.

## Read-only boundary

This contract authorizes observation only.

The adapter layer must not, as part of snapshot capture:

- move/trim/delete clips
- ripple edits
- add/delete/reorder/rename tracks
- change effects/keyframes
- change markers/subtitles
- change links
- alter project/timeline settings

Any future mutation path is separate and remains subject to Candidate Authority and Safety contracts.

## Immutable snapshot

A captured snapshot is immutable. Resolve changes create a new snapshot value; historical snapshots
are never mutated in place.

Recommended top-level value:

- timeline_ref
- timeline_version
- native_state_token or explicit absence
- timeline_rate
- tracks
- placements
- adapter_provenance
- capability_manifest
- capture_consistency
- snapshot_completeness

## Identity lifetime is explicit, never probabilistic

Native identity must carry a lifetime/scope classification.

Minimum v1 levels:

- PERSISTENT_VERIFIED
- SESSION_LOCAL_VERIFIED
- SNAPSHOT_LOCAL
- UNKNOWN

Definitions:

- PERSISTENT_VERIFIED: continuity across reopen/restart is actually verified by supported native
  evidence.
- SESSION_LOCAL_VERIFIED: continuity is verified within one Resolve/application session but not
  promised across reopen/restart.
- SNAPSHOT_LOCAL: object is distinguishable inside the captured snapshot only.
- UNKNOWN: no safe correspondence claim is available.

Identity scope is not a confidence score and must not be converted into fuzzy probability.

OPEN-001 remains unresolved until production runtime/API evidence supports persistent identity.

## Capability and observed value are separate axes

Adapter capability states describe whether the adapter knows how to read a class of information:

- SUPPORTED
- UNSUPPORTED
- UNKNOWN

This does not describe the value observed in a particular snapshot.

Example:

- retime capability = SUPPORTED
- this placement retime observation = UNKNOWN

is valid.

Likewise:

- effect capability = UNSUPPORTED

must never be converted into:

- has_effects = FALSE

Capability absence/unknown is not negative evidence.

## Observed-value semantics

When a field is supported but not reliably observed in a capture, the snapshot must retain UNKNOWN
or an equivalent explicit absence. The adapter must not synthesize a false/default value.

This applies to, for example:

- retime state
- effect presence
- transition presence
- track lock/mute/enable state
- native relationship evidence

## Capture consistency

Snapshot capture must distinguish:

- CONSISTENT
- UNSTABLE
- UNVERIFIED

### CONSISTENT

The adapter has evidence that mapping-relevant state did not change during capture.

### UNSTABLE

The adapter detected that mapping-relevant state changed during capture.

### UNVERIFIED

The adapter cannot prove whether state remained stable during capture.

UNVERIFIED must never be silently upgraded to CONSISTENT.

For destructive downstream features, UNVERIFIED normally reduces readiness until a separate approved
policy says otherwise.

## Native state token

ADR-021 state_token is an opaque identity for mapping-relevant captured state.

The contract does not require Resolve itself to expose a built-in change token. A future adapter may
derive a fingerprint from authoritative mapping-relevant observations.

Rules:

1. state_token is not a security/auth token.
2. it must not be fabricated as a meaningless random string merely to satisfy a field.
3. if the adapter cannot produce a trustworthy mapping-state identity, freshness capability is
   insufficient/unknown.
4. exact token derivation and runtime validation remain a production adapter concern.

## Snapshot completeness != feature readiness

SnapshotCompleteness answers only:

> Were the fields required by the declared snapshot/capability contract structurally captured?

Minimum states:

- COMPLETE_FOR_DECLARED_CAPABILITIES
- PARTIAL

Completeness is not permission to analyze or edit.

A deliberately narrow capability manifest must not allow the system to claim that every product
feature is ready.

## FeatureRequirementProfile

Feature readiness is evaluated separately against an explicit requirement profile.

Examples:

### PAUSE_ANALYSIS

May require:

- usable timeline identity/version/state evidence
- placement identity at sufficient scope
- timeline/source ranges
- exact/current mapping readiness
- supported spoken-content evidence path

### PAUSE_DESTRUCTIVE_APPLY

May additionally require:

- track state needed by safety
- relationship/link evidence
- transition risk evidence
- editability/protected-state evidence
- current snapshot/freshness verification

The actual requirement profiles are versioned product contracts and can evolve independently from
snapshot completeness.

## Readiness result

A pure readiness assessment may return:

- READY
- REVIEW_REQUIRED
- STALE
- UNSUPPORTED
- UNVERIFIED

READY means the snapshot evidence is sufficient for the named downstream feature profile.

READY is not Apply/Approval/Safety authorization.

## Adapter provenance

Every snapshot records enough provenance to reproduce which adapter interpretation produced it.

Recommended fields:

- adapter_name
- adapter_version
- snapshot_contract_version
- resolve_version when available
- platform when useful

This is diagnostic provenance, not user identity.

## Timeline identity

Timeline display name is not identity.

If a persistent native timeline identity is unavailable, the adapter must classify the identity
scope honestly rather than fabricating persistence.

## Track observation

A NativeTrackSnapshot may contain:

- track_ref
- identity_scope
- track_type
- native_index as descriptive metadata
- optional display_name
- observed native state values
- placement membership

Track name and native ordinal/index are not persistent identity or semantic role.

ADR-014 remains authoritative: track names do not automatically imply DIALOGUE/BROLL/etc.

## Placement observation

A NativePlacementSnapshot is the core item-level observation.

Recommended fields:

- object_ref
- identity_scope
- track_ref
- media_ref
- media_identity_scope
- timeline_range
- source_range
- timeline_rate
- source_rate
- retime_kind / retime observation
- optional editability/risk observations
- native metadata that is explicitly non-authoritative

Placement identity and media identity are separate.

The same media may appear in multiple placements; media identity alone never selects a target.

## Media identity

Filename-only identity remains forbidden by ADR-003.

Prefer native media-pool identity or adapter-verified identity where available. Otherwise expose a
weaker identity scope; do not silently promote a composite heuristic to persistent identity.

## Temporal mapping boundary

Source/timeline coordinates must be normalized through ADR-021.

The snapshot layer may supply the explicit placement correspondence needed to construct
PlacementTemporalBinding, but it must not infer mapping solely from FPS, duration or filename.

UNKNOWN retime is not IDENTITY_1X.

## Retime observation

Use the ADR-021 vocabulary where possible:

- IDENTITY_1X
- AFFINE_FORWARD
- REVERSE
- FREEZE
- VARIABLE_RETIME
- UNKNOWN

The adapter reports what it actually knows. Mapping/execution support remains a separate concern.

## Optional editability/risk observations

Capability-based observations may later include:

- transition presence/ranges
- effect presence
- keyframe presence
- compound/multicam/nested/generator status
- native links/sync relationships
- track lock/mute/enable/solo/autoselect state

These are descriptive observations only.

For any unsupported/unobserved field, use UNKNOWN/absence rather than FALSE.

## Native relationship evidence

Linked A/V, multicam membership, sync membership or similar native relationships may be captured as
descriptive facts when supported.

They do not imply action semantics such as move/delete/trim together.

ADR-013 remains authoritative.

## Atomic observation objective

A production capture should represent one coherent native state.

If Resolve does not support one atomic read, a future adapter may use start/end state evidence or
equivalent checks.

Rules:

- do not combine new Track A data with stale Track B data and call it one current snapshot
- if drift is detected, mark UNSTABLE
- if drift cannot be checked, mark UNVERIFIED
- avoid long blocking locks; Human Priority / ADR-016 remains in force

## Partial snapshot

If required supported fields are missing, mark PARTIAL.

Do not reconstruct missing source ranges, identity, track state, retime state or native relationships
from nearby metadata unless a separate approved mapping contract explicitly permits it.

## Normalization vs semantic inference

Allowed normalization:

- native rational frame-rate representation -> FrameRate
- native typed range -> validated internal range through ADR-021
- native enum/value -> corresponding typed domain value when semantics are exact

Not allowed:

- track name "Dialogue" -> semantic DIALOGUE role
- missing speed info -> assume 100%
- filename match -> same placement
- unsupported effect query -> has_effects = false

## Relationship to ADR-021 and ADR-020

Expected path:

```text
Resolve native state
    ↓
Read-only Resolve Snapshot
    ↓
ADR-021 Native Time / Snapshot Mapping
    ↓
ADR-020 Observation Evidence
    ↓
PauseObservation
    ↓
TASK-007 decision
    ↓
Safety / Authority
```

TASK-009 does not read Resolve.
TASK-010 does not read Resolve.
This snapshot contract defines the future adapter observation boundary that can supply trusted inputs
to both.

## Relationship to Safety Core

Snapshot data may later support production checks for:

- stale targets
- track state
- transitions
- relationships
- editability risk
- protected state

The snapshot adapter itself does not decide whether an edit is safe.

## v1 minimum useful snapshot for Pause vertical

Minimum target shape:

Timeline:
- timeline_ref + identity scope
- timeline_version
- freshness/state evidence when available
- timeline rate

Track:
- track_ref + identity scope
- track type
- placement membership

Placement:
- object_ref + identity scope
- media_ref + media identity scope
- timeline range
- source range
- retime observation

Advanced safety metadata remains capability-based extension.

## TASK-011 boundary

A future TASK-011 may implement pure immutable snapshot-domain values and readiness logic only.

It may implement:

- IdentityScope
- AdapterCapability / CapabilityManifest
- CaptureConsistency
- SnapshotCompleteness
- AdapterProvenance
- NativeTrackSnapshot
- NativePlacementSnapshot
- NativeTimelineSnapshot
- FeatureRequirementProfile
- pure structural validation
- pure feature-readiness assessment

It must not implement:

- actual Resolve API calls
- mutation
- filename-based identity inference
- semantic track-role inference
- persistent identity claims not proven by runtime evidence
- ChangeSet/partial refresh engine
- media intelligence
- EditPlan lowering
- Safety execution
- UI/network/DB

## Deferred/open production questions

Remain open until runtime/API validation:

- exact persistent identity support (OPEN-001)
- native track/object correspondence (OPEN-006)
- scope-aware invalidation/partial refresh (OPEN-008)
- trustworthy state-token derivation
- which Resolve versions/platforms expose each capability reliably
- capture consistency proof strategy
- exact native relationship/effect/transition availability

## Accepted v1 principles

1. Resolve remains Source of Truth.
2. Snapshot is immutable read-only observation.
3. Identity lifetime is explicit and never probabilistic.
4. SESSION_LOCAL_VERIFIED is distinct from SNAPSHOT_LOCAL and PERSISTENT_VERIFIED.
5. Capability support and per-capture observed value are separate axes.
6. Unsupported/unknown capability never becomes a false negative observation.
7. Capture consistency is CONSISTENT / UNSTABLE / UNVERIFIED.
8. UNVERIFIED is never assumed stable.
9. Snapshot completeness and feature readiness are separate concepts.
10. Feature readiness is evaluated against an explicit requirement profile.
11. state_token is mapping-state identity only and may be unavailable if not trustworthy.
12. Unknown native state reduces automation.
13. Track names/indices are not persistent identity or semantic roles.
14. Media and placement identity remain separate.
15. Unknown retime is not assumed 1x.
16. Read-only READY is not Apply/Safety/Authority permission.
