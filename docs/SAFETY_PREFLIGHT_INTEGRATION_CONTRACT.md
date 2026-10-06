# Safety Preflight Integration Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the mandatory pre-execution Safety Preflight contract for destructive Pause edits.

Safety consumes already-specified consequences and current safety evidence. It does not invent a new
edit, choose a new geometry, select ripple participants, or repair the proposal.

Core principle:

> Safety validates a fully specified consequence. It does not invent a safer edit.

## Architecture position

```text
PauseCandidate
  ↓
Cut Geometry
  ↓
PauseEditProposal
  ↓
ExpectedDiff
  ↓
Safety Preflight
  ↓
SafetyPreflightResult
  ↓
Authority / Approval
  ↓
future Executor
  ↓
future Postflight Verification
```

## PreflightStatus and SafetyVerdict are separate axes

PreflightStatus answers whether Safety could fully evaluate the required contract:

- EVALUATED
- STALE
- UNSUPPORTED
- INCOMPLETE

SafetyVerdict exists only when status == EVALUATED:

- PASS
- REVIEW_REQUIRED
- REJECT

Result invariant:

```text
status != EVALUATED -> verdict is None
status == EVALUATED -> verdict is present
```

## Mandatory precedence

PreflightStatus precedence:

```text
STALE > UNSUPPORTED > INCOMPLETE > EVALUATED
```

When EVALUATED, SafetyVerdict precedence:

```text
REJECT > REVIEW_REQUIRED > PASS
```

All findings are preserved even when a higher-precedence outcome already exists.

## Unknown means less autonomy

Unknown/missing mandatory safety state never defaults to safe.

Examples:

- track lock UNKNOWN
- transition UNKNOWN
- effect/editability UNKNOWN
- keyframe/editability UNKNOWN
- incomplete protection context
- unresolved temporal dependent

These block PASS and normally yield INCOMPLETE rather than REJECT.

Unknown is not the same as a known risk.

## No diagnostic short-circuit

The preflight should evaluate every check whose required evidence is available and preserve all
findings.

A protected-range violation must not hide a second track-lock violation or a known transition risk.

## PAUSE_DESTRUCTIVE_PREFLIGHT_V1 mandatory check set

The v1 safety profile requires exactly these 17 checks:

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

A PASS result requires all 17 mandatory checks to be evaluated successfully.

No empty-check PASS is allowed.

## SafetyPreflightInput

Recommended inputs:

- ExpectedDiff
- current snapshot reference
- native/read-only snapshot safety observations
- ProtectionContext
- SafetyRequirementProfile
- dependency/relationship assessment reference
- planning proposal reference
- optional PreservationProof records
- safety contract version

All inputs are immutable and bound to the same base/current context.

## ExpectedDiff readiness

Safety only evaluates an ExpectedDiff that is READY_FOR_PREFLIGHT.

Safety does not complete, repair, reinterpret, or expand an incomplete diff.

## Base freshness

PauseEditProposal, ExpectedDiff, protection context and current safety evidence must refer to the same
current timeline/base state.

Timeline/version/state mismatch -> STALE.

No stale PASS is emitted.

Human edits after a PASS invalidate that PASS for future apply.

## ExpectedDiff integrity

The ExpectedDiff primary change must exactly preserve the proposal geometry and primary range.

Safety never shrinks, shifts, rounds or substitutes a safer range.

A structurally tampered primary consequence is a hard failure.

## ProtectionContext

Protection data is explicit, immutable and snapshot-bound.

Recommended fields:

- context_ref
- timeline/base binding
- protected object/range records
- completeness
- context version

An empty protected-range tuple only means "known none" when the context is complete.

Unavailable/partial protection evidence -> INCOMPLETE.

## Protected direct change

A primary destructive change overlapping a HARD_LOCK protected range/object -> REJECT.

ADR-010 remains authoritative.

## Protected displacement

A protected object whose absolute timeline position is expected to change -> REJECT.

Direct deletion is not required for a protected-range violation.

## Track lock

For every affected track:

- lock FALSE -> check may pass
- lock TRUE -> REJECT
- lock UNKNOWN/unavailable -> INCOMPLETE

Other native states such as mute/enable/solo/autoselect remain descriptive unless separately approved
as safety requirements.

## Relationship and temporal dependency

Safety does not recompute relationship execution semantics.

The required chain is:

```text
Relationship Evidence
→ Dependency Resolution
→ Participation Resolution
→ ExpectedDiff
→ Safety
```

Unresolved dependency or unknown temporal dependent behavior prevents PASS.

Safety does not create new dependent edits.

## Retime support

Initial Pause destructive support is limited to already-supported exact forward correspondence.

Represented native states:

- supported exact IDENTITY_1X / AFFINE_FORWARD -> may continue
- UNKNOWN -> INCOMPLETE
- REVERSE / FREEZE / VARIABLE_RETIME -> UNSUPPORTED

Do not assume unsupported retime is 1x.

## Topology preservation

Pause v1 expects no topology mutation:

- no track creation
- no track deletion
- no reorder
- no cross-track membership move

A planned topology mutation -> UNSUPPORTED for Pause v1.

## Pure displacement preservation

Temporal displacement must preserve:

- media identity
- source range
- duration
- track membership

Known mutation to these values is a hard safety failure for a change represented as pure
displacement.

## Transition / Effect / Keyframe observation states

These three areas use the same four-way interpretation pattern:

### KNOWN_ABSENT

Trusted native observation confirms the structure is absent.

The corresponding check may pass.

### UNKNOWN

The system cannot establish whether relevant structure is present or preserved.

Preflight is INCOMPLETE.

### KNOWN_PRESENT_WITHOUT_PROOF

Relevant structure exists, but no approved preservation proof is supplied.

Preflight may be EVALUATED with REVIEW_REQUIRED when every other mandatory safety fact is known.

### PRESERVATION_PROVEN

Relevant structure exists, and an explicit typed preservation proof accepted by the v1 Safety profile
demonstrates that the expected edit preserves the required structure.

The corresponding check may pass.

Presence alone is not proof.

## PreservationProof

Safety may consume a typed immutable PreservationProof.

Recommended fields:

- proof_ref
- proof_kind: TRANSITION / EFFECT / KEYFRAME
- snapshot/base binding
- object/range subjects
- expected_diff_ref
- producer/proof contract version
- proof outcome: PRESERVATION_PROVEN
- evidence/provenance refs

Safety validates proof binding and type. It does not generate the proof.

How real Resolve/runtime code creates trustworthy proofs is deferred to OPEN-015.

## Transition integrity

- trusted absent -> PASS check
- unknown/unavailable -> INCOMPLETE
- present + valid PreservationProof -> PASS check
- present without proof -> REVIEW_REQUIRED
- explicit handle/range violation proven -> REJECT

## Effect editability

- trusted absent -> PASS check
- unknown/unavailable -> INCOMPLETE
- present + valid PreservationProof -> PASS check
- present without proof -> REVIEW_REQUIRED
- explicit destructive replacement/flatten/editability violation -> REJECT

ADR-017 Preserve Editability remains authoritative.

## Keyframe editability

- trusted absent -> PASS check
- unknown/unavailable -> INCOMPLETE
- present + valid PreservationProof -> PASS check
- present without proof -> REVIEW_REQUIRED
- explicit keyframe integrity violation -> REJECT

## PreservationScope

ExpectedDiff's PreservationScope must cover the complete known expected impact.

All changed objects must be in scope.

Known impacted/dependent object outside scope -> INCOMPLETE.

Within scope, an object absent from ExpectedDiff is expected unchanged.

## ExpectedDiff completeness != Safety acceptability

A fully specified ExpectedDiff may be READY_FOR_PREFLIGHT even when Safety will reject it.

Example: a protected participant is explicitly displaced.

This separation is mandatory:

```text
complete consequence != acceptable consequence
```

## SafetyCheckKind

v1 check kinds are the 17 mandatory items listed above.

Each check result retains:

- check kind
- invariant references
- subjects
- outcome
- reason codes
- evidence/proof refs

## Check outcomes

For individual evaluated checks:

- PASS
- REVIEW_REQUIRED
- REJECT

If mandatory evidence for a check is absent/unknown, the overall PreflightStatus becomes INCOMPLETE
instead of fabricating a PASS/REJECT check.

## Invariant linkage

Recommended mapping:

- BASE_FRESHNESS -> INV-012
- PROTECTED_RANGE -> INV-003 / INV-017
- RELATIONSHIP_INTEGRITY -> INV-004 / INV-006
- RETIME_SUPPORT -> INV-007
- TRANSITION_INTEGRITY -> INV-009
- EFFECT_EDITABILITY / KEYFRAME_EDITABILITY -> INV-010
- media/source preservation -> INV-002 / INV-011
- temporal dependent coverage -> INV-018
- topology preservation -> INV-019
- ExpectedDiff integrity / later postflight -> INV-016

## Hard reject classes

Initial hard rejection classes include:

- protected direct destructive change
- protected displacement
- locked-track mutation
- ExpectedDiff/proposal primary mismatch or tampering
- media replacement in a pure displacement
- source-range mutation in a pure displacement
- duration mutation in a pure displacement
- track-membership mutation in a pure displacement
- explicit transition integrity violation
- explicit effect/editability violation
- explicit keyframe integrity violation

## Review classes

Initial review cases include:

- known transition present without preservation proof
- known effect structure present without preservation proof
- known keyframe structure present without preservation proof

Review is not a generic bypass for hard violations.

## Incomplete classes

Initial incomplete cases include:

- unknown track lock
- unknown transition presence/integrity
- unknown effect/editability state
- unknown keyframe state
- incomplete ProtectionContext
- unresolved/unknown temporal dependent coverage
- missing mandatory safety capability/evidence

## Unsupported classes

Initial unsupported cases include:

- unsupported retime
- Pause v1 planned topology mutation
- change class outside the approved Pause destructive profile

Unsupported means the v1 system cannot safely evaluate/support the operation; it does not claim the
edit is inherently unsafe.

## Aggregation

When all mandatory evidence is available:

- any REJECT check -> verdict REJECT
- else any REVIEW_REQUIRED check -> verdict REVIEW_REQUIRED
- else -> verdict PASS

PASS requires all 17 mandatory checks.

## Safety result is not authority

Safety PASS is distinct from:

- user approval
- apply permission
- successful apply
- verified apply
- promotion

ADR-015 remains authoritative.

## Safety result binding

A SafetyPreflightResult must retain:

- ExpectedDiff ref
- base/current snapshot ref
- safety profile ID/version
- ProtectionContext ref/version
- preservation proof refs
- safety contract version

A PASS cannot be reused for a different ExpectedDiff or changed safety context.

## No generic hard-safety override

v1 provides no universal "force apply" path for SEV-0/SEV-1 safety failures.

REVIEW_REQUIRED means human judgment is needed; it does not mean a hard violation can be overridden.

## Safety never replans

If a plan is rejected or incomplete, Safety returns typed findings upstream.

Safety does not:

- choose a different cut
- modify retained duration
- exclude a problematic participant
- flatten effects
- unlock tracks
- remove protection
- choose alternate topology

Upstream planning must produce a new artifact.

## Postflight relationship

Safety PASS means only that the expected consequence was acceptable before execution.

After execution, verified promotion still requires:

```text
ExpectedDiff == ActualDiff
```

under ADR-025 / INV-016.

Executor success alone is insufficient.

## TASK-015 boundary

TASK-015 may implement pure immutable Safety Preflight integration only:

- SafetyRequirementProfile
- PAUSE_DESTRUCTIVE_PREFLIGHT_V1 with exactly 17 mandatory checks
- ProtectionContext
- PreservationProof
- SafetyCheckKind / SafetyCheckOutcome / SafetyCheckResult
- PreflightStatus
- SafetyVerdict
- SafetyPreflightInput
- SafetyPreflightResult
- pure mandatory-evidence/readiness checks
- pure aggregation logic
- synthetic Pause v1 safety checks over supplied immutable data
- deterministic/immutable tests

TASK-015 must not implement:

- Resolve API/mutation
- participant selection
- geometry generation
- ExpectedDiff compilation
- preservation-proof generation
- actual track unlock/protection changes
- transaction/rollback
- approval/authority transition
- postflight snapshot capture
- automatic replanning
- generic safety override

## Accepted v1 decisions

1. PreflightStatus and SafetyVerdict are separate.
2. Status precedence: STALE > UNSUPPORTED > INCOMPLETE > EVALUATED.
3. Verdict precedence: REJECT > REVIEW_REQUIRED > PASS.
4. Unknown safety state reduces autonomy and never defaults safe.
5. All evaluable findings are retained; no diagnostic short-circuit.
6. PAUSE_DESTRUCTIVE_PREFLIGHT_V1 has exactly 17 mandatory checks.
7. PASS requires all 17 checks to be evaluated.
8. ExpectedDiff completeness and Safety acceptability are separate.
9. Safety consumes consequences and never repairs/replans them.
10. Hard protection/lock/preservation violations reject.
11. Unknown mandatory safety evidence yields INCOMPLETE.
12. Unsupported retime/topology yields UNSUPPORTED.
13. Transition/effect/keyframe TRUE may PASS only with valid typed PRESERVATION_PROVEN evidence.
14. Known transition/effect/keyframe presence without proof yields REVIEW_REQUIRED.
15. PreservationProof is consumed, not generated, by Safety.
16. Safety PASS is snapshot/profile/protection/proof bound.
17. Human edits invalidate prior PASS.
18. No generic hard-safety override.
19. Safety PASS is not Approval/Apply/Verified Apply/Promotion.
20. Postflight ExpectedDiff = ActualDiff remains mandatory.

## Final principle

> Safety Preflight does not ask whether the edit is creatively good. It asks whether this fully
> specified consequence may touch this exact current timeline without violating the project's
> integrity contracts.
