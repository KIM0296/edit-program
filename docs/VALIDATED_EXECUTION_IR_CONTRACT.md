# Validated Execution IR & Resolve Executor Boundary Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the contract that lowers an already-approved semantic consequence into a bounded logical
Execution IR, validates exact semantic coverage against verified native capabilities/effect models,
and establishes the boundary of the Resolve Executor.

Core principles:

> The executor executes an approved state transition. It does not reinterpret editorial intent.

> A native command is executable only when the system can prove both who it will touch and exactly
> what that command is allowed to change.

## Architecture position

```text
ExpectedDiff
+
SafetyPreflightResult(PASS)
+
ExecutionAuthorization
        ↓
Execution IR Compiler
        ↓
ExecutionIR
        ↓
Semantic / Coverage Validation
        ↓
Target Identity Validation
        ↓
Native Capability + Effect Model Validation
        ↓
ValidatedExecutionIR
        ↓
Resolve Executor
        ↓
ADR-027 Transaction / Postflight
```

## Pause v1 logical IR vocabulary

Pause v1 supports exactly two logical operation kinds:

- REMOVE_RANGE
- TRANSLATE_PLACEMENT

Do not add generic RIPPLE, CLOSE_GAP_AUTO, DELETE_ALL_AFTER, or other participant-expanding
operations.

### REMOVE_RANGE

Represents the exact approved contiguous primary range removal on one bound placement.

It does not imply ripple, linked deletion, gap closure, participant selection, or any other
collateral effect.

### TRANSLATE_PLACEMENT

Represents one already-approved surviving placement translation with exact before/after ranges and
integer delta while preserving media identity, source range, duration and track membership.

## Exact semantic coverage

ExecutionIR must cover ExpectedDiff exactly.

- every ExpectedDiff change must be covered
- every IR operation must reference an approved ExpectedDiff change
- no extra semantic effect may be introduced
- every approved logical effect must be realized exactly once

Missing effect -> invalid.

Extra effect -> invalid.

Duplicate realization -> invalid.

## Native fusion

A single verified native primitive may realize multiple logical operations only when:

- NativeCapabilityStatus == SUPPORTED_VERIFIED
- a current VERIFIED NativeEffectModel exists
- predicted semantic effects equal the approved ExpectedDiff effect set exactly
- targets and side-effect scope are verified
- reconciliation/post-read requirements are satisfied

API existence or common NLE behavior is not evidence.

## Observation identity vs execution identity

Read-only observability is weaker than destructive target authority.

Execution target identity must support precommit identification, mutation-time correspondence, and
postflight correspondence.

IdentityScope eligibility:

- PERSISTENT_VERIFIED -> eligible
- SESSION_LOCAL_VERIFIED -> conditionally eligible only in the same proven session with mutation
  stability and postflight correspondence proof
- SNAPSHOT_LOCAL -> unsupported for destructive v1 execution
- UNKNOWN -> incomplete

Do not supplement weak identity using filename, track name/index, current position or first-match
heuristics.

## ExecutionTargetBinding

Recommended fields:

- target_ref
- expected_change_ref
- base_snapshot_ref
- session_ref
- placement_identity
- identity_scope
- identity_proof_ref
- track_identity
- before_timeline_range
- source_range
- media_identity
- native_locator_ref
- locator_proof_ref
- contract_version

Domain identity and native locator are separate concepts.

A native handle/locator is not automatically stable proof.

## TargetResolutionStatus

Use at least:

- VERIFIED
- STALE
- AMBIGUOUS
- UNRESOLVED
- UNSUPPORTED

Only VERIFIED may enter destructive lowering.

Never choose the first ambiguous match or silently rebind by nearby position/name/media.

## Fragment-producing lowering

If native lowering creates intermediate fragments, v1 requires either:

1. a verified compound primitive whose semantic effect is modeled without exposing ambiguous
   intermediate fragment correspondence, or
2. a verified intermediate fragment identity/rebinding model.

Otherwise lowering is unsupported.

## ExecutorCapabilityManifest

Capability is multidimensional and must be bound to current runtime profile.

Recommended fields include:

- adapter name/version
- Resolve version
- platform
- session ref
- primitive capabilities
- target identity capability
- post-read capability
- reconciliation capability
- rollback capability reference
- capability contract version

Do not transplant a verified capability across a different version/platform/session profile without
new evidence.

## NativeCapabilityStatus

- SUPPORTED_VERIFIED
- SUPPORTED_UNVERIFIED
- UNSUPPORTED
- UNKNOWN

Mapping for destructive lowering:

- SUPPORTED_VERIFIED -> may continue
- SUPPORTED_UNVERIFIED -> incomplete
- UNKNOWN -> incomplete
- UNSUPPORTED -> unsupported

## NativeEffectModel

A NativeEffectModel describes a verified semantic effect model for one native primitive under one
runtime profile.

Recommended fields:

- effect_model_ref
- primitive_kind
- adapter/runtime profile ref
- covered logical op refs
- predicted semantic effects
- possible side-effect scope
- verification evidence refs
- effect contract version

Effect model status:

- VERIFIED
- UNVERIFIED
- CONFLICTING
- STALE
- UNKNOWN

Only VERIFIED is eligible for destructive lowering.

## Exact native effect equality

For v1:

```text
PredictedNativeEffects == ExpectedDiffChanges
```

Neither subset nor superset is acceptable.

ExpectedDiff must never be expanded after the fact to accommodate native side effects.

## PreservationScope containment

If a native primitive may affect state beyond the validated PreservationScope and that wider scope
cannot be explicitly observed/verified, the lowering is unsupported.

## Verified post-read is mandatory before execution

Post-read capability is not optional because ADR-027 requires postflight verification.

If post-read is not SUPPORTED_VERIFIED, destructive execution must not begin.

## Verified reconciliation path is mandatory

Every destructive NativeExecutionStep must have a verified reconciliation path before execution.

This is required because any step may become OUTCOME_UNKNOWN.

A reconciliation specification should identify:

- observable subjects
- expected state if the step applied
- expected state if the step did not apply
- required read capabilities
- reconciliation contract version

Reconciliation defines observable evidence, not retry policy.

Blind retry remains forbidden by ADR-027.

## Rollback is a separate axis

Lowering semantic readiness and rollback capability/policy are separate.

A ValidatedExecutionIR can be semantically READY while transaction policy later blocks automatic
apply because rollback is UNKNOWN/UNSUPPORTED.

Rollback weakness does not make a correct semantic IR invalid.

## NativeLoweringPlan

Recommended fields:

- lowering_ref
- execution_ir_ref
- adapter profile ref
- native steps
- realization/coverage map
- effect model refs
- lowering contract version

Each native step records which logical ops/expected changes it realizes.

## Exact-once realization

Every approved logical effect belongs to exactly one lowering realization.

Fusion may map several logical ops to one native step.

Decomposition may map one logical op to several native steps only when intermediate identity/effect
semantics are verified.

Double realization is invalid.

## No runtime fallback

If a selected native lowering becomes unavailable at runtime, the executor may not silently choose a
different native method.

A new NativeLoweringPlan must be built and validated again.

## No semantic repair

Adapter/executor must not:

- move cut boundaries
- change delta
- add/remove participants
- change tracks/source ranges
- unlock tracks
- override protection
- generate safer alternatives
- reinterpret relationship semantics

Those require a new upstream semantic artifact.

## ValidatedExecutionIR status

Use:

- READY_FOR_EXECUTION
- STALE
- INVALID
- UNSUPPORTED
- INCOMPLETE

Recommended precedence:

```text
STALE > INVALID > UNSUPPORTED > INCOMPLETE > READY_FOR_EXECUTION
```

### STALE

Runtime/profile/artifact binding no longer matches.

### INVALID

Semantic contradiction, such as uncovered expected change, extra IR effect, wrong geometry/delta,
duplicate realization, or incompatible immutable bindings.

### UNSUPPORTED

Known system limitations prevent safe lowering, such as SNAPSHOT_LOCAL execution identity,
unsupported primitive, or unverified fragment decomposition.

### INCOMPLETE

Required evidence is missing or unverified, such as UNKNOWN capability/effect model/identity proof.

### READY_FOR_EXECUTION

Only means that the exact authorized semantic effect can be represented by verified native semantics
for the exact current runtime profile.

It does not mean applied, committed, rollback-capable, or promoted.

## Native lowering validation order

1. Artifact binding
2. ExpectedDiff <-> logical IR exact semantic coverage
3. Exact-once realization
4. Target identity/resolution
5. Native capability status
6. Native effect model
7. PreservationScope containment
8. Reconciliation readiness
9. Post-read readiness
10. Current runtime/profile binding

No fallback or repair occurs during validation.

## Adapter responsibilities

The adapter is limited to:

- typed target resolution
- capability reporting
- verified native lowering
- native command execution
- raw native result reporting
- read-only observation support

It is not a planner, product layer, or Safety layer.

## Executor responsibilities

The executor consumes a ValidatedExecutionIR / validated lowering plan, submits native steps into the
ADR-027 transaction state machine, and records raw step outcomes.

The executor does not declare commit or verified rollback.

## TASK-017 boundary

TASK-017 may implement pure immutable foundation only:

- ExecutionOpKind
- RemoveRangeOp
- TranslatePlacementOp
- ExecutionTargetBinding
- TargetResolutionStatus
- ExecutionIR
- ExecutorCapabilityManifest
- NativeCapabilityStatus
- NativeEffectModel / EffectModelStatus
- ReconciliationSpec
- NativeExecutionStep
- LoweringRealization
- NativeLoweringPlan
- ValidatedExecutionIR status/reasons
- exact semantic coverage validator
- exact-once realization validator
- capability/effect-model/identity/post-read/reconciliation validation
- deterministic/immutable tests

TASK-017 must not implement:

- actual Resolve target lookup
- actual Resolve mutation
- actual native split/delete/ripple/move
- actual capability probing
- actual effect-model production
- actual postflight capture
- transaction execution
- rollback
- authority promotion
- performance-based lowering selection

## Accepted v1 decisions

1. Pause v1 logical IR vocabulary is exactly REMOVE_RANGE + TRANSLATE_PLACEMENT.
2. Generic ripple/participant-expanding opcode is forbidden.
3. Exact-once semantic coverage is a hard invariant.
4. ExecutionIR may not introduce effects outside ExpectedDiff.
5. Native fusion requires SUPPORTED_VERIFIED + VERIFIED NativeEffectModel.
6. Execution identity is stronger than observation identity.
7. PERSISTENT_VERIFIED is execution eligible.
8. SESSION_LOCAL_VERIFIED is eligible only in the same proven session with mutation-stability and
   postflight correspondence proof.
9. SNAPSHOT_LOCAL is unsupported for destructive v1 targeting.
10. Target ambiguity never resolves by first match.
11. Domain identity and native locator are separate.
12. Every destructive step requires a verified reconciliation path.
13. Verified post-read capability is required before execution starts.
14. Fragment-producing decomposition requires verified intermediate rebinding.
15. Capability UNKNOWN/UNVERIFIED never becomes destructive support.
16. Predicted native effects must equal ExpectedDiff effects exactly.
17. ExpectedDiff is never expanded to accommodate native side effects.
18. Runtime fallback requires a new lowering plan and validation.
19. Rollback capability/policy is separate from lowering semantic readiness.
20. READY_FOR_EXECUTION does not mean applied, committed or promoted.

## Final principle

> The Resolve Executor is a deterministic actuator, not an editor. Every effect it is permitted to
> cause must already exist in the authorized and safety-validated semantic plan.
