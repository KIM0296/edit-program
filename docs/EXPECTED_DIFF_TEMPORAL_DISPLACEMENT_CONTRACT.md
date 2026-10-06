# Expected Diff & Temporal Displacement Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define a pure, immutable representation of the exact timeline consequences expected from a
PauseEditProposal before Safety Preflight, and the pure comparison semantics required later for
INV-016 Expected Diff = Actual Diff.

Core principles:

> Gap closure is not an implicit ripple side effect. Every expected temporal displacement must be
> explicit before mutation.

> Primary change and collateral displacement are different classes of change.

> A safe edit plan must state exactly what is expected to change, exactly what is expected to move,
> and therefore exactly what must remain unchanged.

## Architecture position

```text
PauseEditProposal
      +
Precomputed DisplacementParticipationAssessment
      +
PreservationScope
      ↓
Expected Diff Compiler
      ↓
ExpectedDiff
      ↓
Safety Preflight
      ↓
future Apply
      ↓
future Post Snapshot
      ↓
ActualDiff
      ↓
pure Expected-vs-Actual verification
```

The compiler is not an executor and does not decide Safety.

## Primary change vs displacement

The primary Pause edit is the explicit range removal already established by ADR-023.

A temporal displacement is a surviving object's timeline-position change caused by closing the
removed interval.

They must be represented separately.

## No implicit ripple

The following are insufficient for Safety-ready planning:

- ripple=true
- all downstream
- move everything after frame X
- track-local ripple without enumerated objects

A concrete displacement manifest is required.

## Participant policy is external to the compiler

The Expected Diff Compiler does **not** select displacement participants.

It consumes a precomputed immutable DisplacementParticipationAssessment.

This assessment identifies:

- resolved participant objects
- explicitly excluded objects when useful
- unresolved/conflicting objects
- status/reasons
- base snapshot/proposal binding

The compiler must not infer participation from:

- track name/index
- object order
- merely being after the cut
- media identity
- linked flag alone
- sync-group membership alone
- NLE convention

ADR-013 remains authoritative.

## Participation status

Minimum v1 statuses:

- RESOLVED
- REVIEW_REQUIRED
- CONFLICT
- UNSUPPORTED
- STALE

Only RESOLVED participation can produce a READY_FOR_PREFLIGHT ExpectedDiff.

## Primary range removal

Recommended immutable value:

- change_id
- proposal_ref
- object_id
- before_timeline_range
- removed_timeline_range
- geometry_ref
- optional exact source-removal metadata when already supplied

The compiler must preserve the exact geometry. No clamp, shift, rounding or repair.

## Closure amount

For one contiguous removed range R:

```text
closure_amount_frames = R.duration
```

This determines the v1 displacement delta for already-resolved participants.

It does not determine who participates.

## TemporalDisplacement

Recommended immutable value:

- object_id
- before_range
- after_range
- delta_frames
- source_change_id
- preserved media/source/duration/track metadata or references as available

For pure translation:

```text
after.start - before.start
==
after.end - before.end
==
delta_frames
```

and duration is unchanged.

## Uniform displacement v1

Initial supported close-gap behavior requires every resolved participant to use:

```text
delta_frames = -closure_amount_frames
```

Nonuniform displacement is REVIEW_REQUIRED or UNSUPPORTED in v1.

Uniformity constrains already-resolved participants; it never selects participants.

## Crossing objects

An object whose timeline range crosses the removed interval is not a simple displacement case.

v1 does not silently decompose it into trim + displacement.

Return non-ready/unsupported.

## Gap interaction

Existing gaps may make actual ripple semantics more complex.

The compiler must not guess gap absorption/preservation rules.

If the supplied participation assessment cannot prove the exact uniform displacement consequence,
return GAP_INTERACTION_UNRESOLVED or equivalent non-ready status.

Gap-aware participant policy remains deferred.

## Pure displacement preservation

A v1 displacement preserves:

- placement identity
- media identity
- source range
- duration
- track membership

Any change to these is a different change class and must be explicit.

## No cross-track move

A track-membership change is not TemporalDisplacement.

Pause close-gap v1 expects no track creation, deletion, reorder or cross-track membership move.

## PreservationScope

ExpectedDiff must define the validation universe.

v1 prefers explicit object enumeration:

- snapshot/base reference
- object_refs
- optional track/range metadata for diagnostics

Within this scope, every object is either:

1. explicitly changed by ExpectedDiff, or
2. expected unchanged.

No third implicit state exists.

## Unlisted Object Invariance

Within the validated PreservationScope:

> An object absent from ExpectedDiff is expected to remain unchanged.

This is a fixed v1 invariant.

The scope must include the complete expected impact. If known dependencies/participants fall outside
it, the diff is incomplete.

Scope outside the manifest is not automatically safe; it is simply unverified.

## ExpectedDiff completeness != Safety acceptability

ExpectedDiff answers:

> Are the intended consequences explicit enough to inspect?

Safety answers:

> Are those consequences acceptable?

Therefore a complete ExpectedDiff may be READY_FOR_PREFLIGHT even when a later Safety rule will
reject it, for example because an explicitly displaced participant lies in a protected region.

Known Safety risk does not make the consequence description incomplete.

The compiler must not fabricate Safety PASS/REJECT.

## ExpectedDiff status

Recommended values:

- READY_FOR_PREFLIGHT
- INCOMPLETE
- REVIEW_REQUIRED
- STALE
- UNSUPPORTED

READY_FOR_PREFLIGHT means the consequence set is sufficiently explicit for Safety evaluation only.

It does not mean:

- safe
- approved
- executable
- applied
- verified

## ExpectedDiff reasons

Recommended reasons:

- READY_FOR_PREFLIGHT
- STALE_BASE
- PARTICIPATION_UNRESOLVED
- PARTICIPATION_CONFLICT
- CROSSING_OBJECT_UNSUPPORTED
- NONUNIFORM_DISPLACEMENT_UNSUPPORTED
- GAP_INTERACTION_UNRESOLVED
- SCOPE_INCOMPLETE
- DEPENDENCY_UNRESOLVED
- UNSUPPORTED_RETIME
- UNSUPPORTED_TOPOLOGY_CHANGE

Names may be refined without weakening semantics.

## Human Edit Wins

ExpectedDiff, participation assessment and proposal are all bound to the same base snapshot/version.

Any relevant human edit makes the artifact stale.

Do not rebase before/after ranges or participant sets silently.

## Relationship boundary

The compiler consumes resolved relationship/dependency outcomes only.

It does not infer:

- linked objects move together
- AV_LINK means same delta
- SYNC_GROUP means same delta
- subtitles/markers automatically move

Unresolved temporal dependencies block readiness.

## Protected ranges

ADR-010 remains a Safety rule.

The ExpectedDiff compiler may describe a displacement that later violates a protected range, but it
must not declare that displacement safe.

## J/L Cut preservation

Pure displacement must preserve existing independent A/V boundaries and source ranges.

Do not normalize J/L structures because related items participate.

## ExpectedDiff structure

Recommended top-level fields:

- expected_diff_ref
- base_snapshot_ref
- planning_proposal_ref
- primary_changes
- temporal_displacement_manifest
- preservation_scope
- expected_topology_changes
- compiler_provenance
- contract_version

For Pause v1, expected_topology_changes defaults to empty.

## Determinism and immutability

Given identical:

- PauseEditProposal
- base snapshot facts
- resolved participation assessment
- preservation scope

the compiler returns the same immutable ExpectedDiff.

No Resolve API, Safety call or Authority transition is allowed.

## ActualDiff

A future ActualDiff describes typed changes observed from base/post snapshots.

It should use the same semantic change vocabulary where practical:

- range removal
- temporal displacement
- unexpected change
- preservation failure

The executor's self-report alone is not authoritative verification.

## Pure Expected-vs-Actual verification

The pure verification layer returns at least:

- MATCH
- MISMATCH
- UNVERIFIED
- STALE

MATCH requires:

- every expected typed change occurred
- exact integer frame equality
- no unexpected change within PreservationScope
- required media/source/duration/track preservation holds
- identity correspondence is sufficient to verify

UNVERIFIED is never promoted to MATCH.

## Exact equality v1

The internal primitive remains integer half-open frames.

No hidden ±1-frame tolerance is allowed.

If expected delta is -40 and actual delta is -39, verification is MISMATCH.

Any future tolerance/sub-frame policy requires a separate ADR.

## Failure classes

Recommended verification reasons include:

- MATCHED
- MISSING_EXPECTED_CHANGE
- UNEXPECTED_CHANGE
- WRONG_PRIMARY_RANGE
- WRONG_DISPLACEMENT
- MEDIA_IDENTITY_CHANGED
- SOURCE_RANGE_CHANGED
- DURATION_CHANGED
- TRACK_MEMBERSHIP_CHANGED
- IDENTITY_UNVERIFIABLE
- POST_SNAPSHOT_STALE

## INV-016 meaning

Expected Diff = Actual Diff means:

> Every expected typed state change occurred exactly, and no unlisted change occurred within the
> validated preservation scope.

It does not mean serialized native objects must be byte-identical.

## Promotion boundary

ADR-015 remains authoritative.

Apply success is not verified apply.

Expected/Actual mismatch or UNVERIFIED postflight cannot produce verified promotion.

## v1 supported case

The initial supported ExpectedDiff case is intentionally narrow:

- one PauseEditProposal
- one contiguous primary removal
- single primary placement
- explicit resolved participant set
- pure participant translations
- uniform integer delta = -removed duration
- no crossing participant
- no unresolved gap interaction
- no topology change
- no unsupported retime
- complete PreservationScope

## TASK-014 boundary

TASK-014 may implement pure immutable foundation only:

- RangeRemovalEffect
- DisplacementParticipationAssessment
- TemporalDisplacement
- TemporalDisplacementManifest
- PreservationScope
- ExpectedDiff
- ExpectedDiffStatus / Reason
- uniform displacement compilation from resolved participants
- exact before/after/delta validation
- pure synthetic ActualDiff values
- pure Expected-vs-Actual verification
- deterministic/immutable tests

TASK-014 must not implement:

- participant selection policy
- actual relationship propagation
- actual ripple command
- Resolve API/mutation
- actual post-snapshot capture
- protected-range Safety verdict
- transaction/rollback
- Authority transition
- persistent native identity resolution
- gap-aware ripple policy

## Accepted v1 decisions

1. Primary change and displacement are separate.
2. Unlisted Object Invariance applies inside PreservationScope.
3. No implicit ripple representation is Safety-ready.
4. Concrete displacement participants must be enumerated.
5. v1 participant displacement is uniform -removed_duration.
6. Uniformity never selects participants.
7. ExpectedDiff Compiler consumes DisplacementParticipationAssessment; it does not select participants.
8. Objects crossing the removal interval are not simple displacement.
9. Gap interaction is never guessed.
10. Pure displacement preserves media/source/duration/track membership.
11. ExpectedDiff completeness and Safety acceptability are separate.
12. A known future Safety violation may still have READY_FOR_PREFLIGHT ExpectedDiff if consequences are complete.
13. Human edits stale ExpectedDiff; no silent rebase.
14. Exact integer-frame equality is required in verification.
15. Unlisted actual changes inside scope are MISMATCH.
16. Missing/wrong expected changes are MISMATCH.
17. UNVERIFIED is not MATCH.
18. Verified promotion requires Expected Diff = Actual Diff.

## Final principle

> Before an AI edit can be considered safe, the system must know not only what it intends to remove,
> but exactly which surviving objects are expected to move and which observed objects are expected
> not to move.
