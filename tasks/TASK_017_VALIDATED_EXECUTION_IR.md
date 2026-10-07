# TASK-017 — Validated Execution IR Foundation

Status: **PREPARED, NOT AUTHORIZED UNTIL TASK-016 IS APPROVED/MERGED**

Basis:
- ADR-006 LLM Emits IR Only
- ADR-015 Candidate Authority
- ADR-022 Read-only Snapshot / IdentityScope
- ADR-025 Expected Diff
- ADR-026 Safety Preflight
- ADR-027 Transaction & Postflight
- ADR-028 Validated Execution IR & Resolve Executor Boundary v1

## Purpose

Implement a pure immutable logical Execution IR and validation foundation for Pause-v1 semantic
effects. No Resolve API is called.

## Mandatory logical vocabulary

Exactly:

- REMOVE_RANGE
- TRANSLATE_PLACEMENT

No generic ripple/close-gap/participant-expanding opcode.

## Required core domain

At minimum:

- ExecutionOpKind
- RemoveRangeOp
- TranslatePlacementOp
- ExecutionTargetBinding
- TargetResolutionStatus
- ExecutionIR
- NativeCapabilityStatus
- ExecutorCapabilityManifest
- EffectModelStatus
- NativeEffectModel
- ReconciliationSpec
- NativeExecutionStep
- LoweringRealization
- NativeLoweringPlan
- ExecutionIRValidationStatus / Reason
- pure validation functions

## Exact semantic coverage

Every ExpectedDiff change must be represented and every IR operation must map to an ExpectedDiff
change.

No missing, extra or duplicate logical effect.

Every approved effect must be realized exactly once in lowering.

## Identity eligibility

Execution identity matrix:

- PERSISTENT_VERIFIED -> eligible
- SESSION_LOCAL_VERIFIED -> eligible only with same session + mutation-stability + postflight
  correspondence evidence
- SNAPSHOT_LOCAL -> UNSUPPORTED
- UNKNOWN -> INCOMPLETE

TargetResolutionStatus must be VERIFIED for destructive readiness.

No first-match, filename, track-name/index, media-only or current-position rebinding.

## Fragment rule

Fragment-producing decomposition is unsupported unless verified intermediate fragment rebinding is
explicitly supplied.

## Native capabilities

NativeCapabilityStatus:

- SUPPORTED_VERIFIED
- SUPPORTED_UNVERIFIED
- UNSUPPORTED
- UNKNOWN

Only SUPPORTED_VERIFIED may support destructive lowering.

SUPPORTED_UNVERIFIED/UNKNOWN -> INCOMPLETE.
UNSUPPORTED -> UNSUPPORTED.

Capabilities are bound to adapter version + Resolve version + platform + session/runtime profile.

## Effect models

EffectModelStatus:

- VERIFIED
- UNVERIFIED
- CONFLICTING
- STALE
- UNKNOWN

Only VERIFIED may support destructive lowering.

Predicted native semantic effect set must equal ExpectedDiff exactly.

No subset/superset and no ExpectedDiff expansion to fit native behavior.

## Post-read and reconciliation

Every destructive native step requires:

- SUPPORTED_VERIFIED post-read capability
- a verified ReconciliationSpec

Without either, not READY_FOR_EXECUTION.

Do not implement retry.

## Rollback separation

Do not make semantic IR INVALID solely because rollback capability is weak/unknown.

Rollback/auto-apply policy remains ADR-027.

## Validation status

Use:

- READY_FOR_EXECUTION
- STALE
- INVALID
- UNSUPPORTED
- INCOMPLETE

Precedence:

```text
STALE > INVALID > UNSUPPORTED > INCOMPLETE > READY_FOR_EXECUTION
```

## Required validation pipeline

1. exact ExpectedDiff/Safety/Authorization/base binding
2. logical semantic coverage
3. exact-once realization
4. target identity/resolution
5. capability profile
6. effect model
7. PreservationScope containment
8. reconciliation readiness
9. post-read readiness
10. runtime/profile currentness

No runtime fallback or semantic repair.

## Required tests

At minimum prove:

1. immutable/frozen domain
2. logical vocabulary exactly two kinds
3. no generic ripple op
4. exact primary RemoveRange mapping
5. exact displacement Translate mapping
6. missing ExpectedDiff effect -> INVALID
7. extra IR effect -> INVALID
8. duplicate realization -> INVALID
9. one effect realized exactly once -> valid
10. multiple ops fused by one realization only with verified effect model
11. fusion with extra predicted native effect -> INVALID/UNSUPPORTED
12. fusion with missing predicted effect -> non-ready
13. PERSISTENT_VERIFIED target eligible
14. SESSION_LOCAL_VERIFIED requires matching session proof
15. session change -> STALE
16. SNAPSHOT_LOCAL -> UNSUPPORTED
17. UNKNOWN identity -> INCOMPLETE
18. ambiguous target -> non-ready
19. unresolved target -> non-ready
20. stale target -> STALE
21. no first-match fallback
22. domain identity/native locator separation
23. fragment decomposition without rebinding -> UNSUPPORTED
24. verified fragment rebinding path may validate structurally
25. capability SUPPORTED_VERIFIED -> may continue
26. SUPPORTED_UNVERIFIED -> INCOMPLETE
27. UNKNOWN capability -> INCOMPLETE
28. UNSUPPORTED capability -> UNSUPPORTED
29. effect model VERIFIED required
30. effect model UNVERIFIED/UNKNOWN -> INCOMPLETE
31. effect model CONFLICTING -> non-ready
32. stale effect model -> STALE
33. exact effect equality required
34. no ExpectedDiff expansion to fit native behavior
35. PreservationScope side-effect expansion -> non-ready
36. verified post-read required
37. verified reconciliation required for each destructive step
38. rollback weakness does not by itself invalidate semantic lowering
39. runtime profile mismatch -> STALE
40. runtime fallback not performed
41. no semantic repair of range/delta/track
42. no participant discovery
43. no mapper/planner/geometry resolver/ExpectedDiff compiler/Safety call
44. no actual Resolve API
45. no transaction execution
46. no rollback
47. no Authority transition
48. TASK-001..016 regression remains green

## Explicitly out of scope

- actual native target lookup
- actual Resolve mutation
- actual capability/effect-model probe
- actual post-read
- actual reconciliation execution
- transaction execution
- rollback
- performance optimization / lowering ranking
- native fragment generation
- authority promotion

## Workflow

1. Do not start until TASK-016 is Chat APPROVED and merged unless Chat explicitly reorders work.
2. Start from then-current main.
3. Treat ADR-028 and this spec as authoritative.
4. Record ambiguity as OPEN; do not invent native/runtime guarantees.
5. Red-first tests.
6. Implement pure immutable domain/validators.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_017_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or auto-start a following task.

## Success definition

Represent the exact Pause-v1 semantic mutation as bounded logical IR and prove that a proposed native
lowering covers every approved effect exactly once using verified execution identity, verified
capability/effect semantics, verified post-read and verified reconciliation evidence, without calling
Resolve or changing the semantic plan.

## TASK-017 implementation notes (before code)

- Reuse exact RangeRemovalEffect / TemporalDisplacement values, NativeSnapshotRef, IdentityScope,
  SafetyPreflightResult and ExecutionAuthorization. Proposed IR is validated, not selected or repaired.
- One LoweringRealization owns a disjoint set of logical op refs and an ordered native step sequence.
  A caller-supplied NativeEffectModel binds that whole sequence and its net semantic effects. This
  permits structural validation of fusion/decomposition without treating intermediate fragments as
  new logical opcodes. No intermediate state or binding is inferred.
- Every step carries bound typed reconciliation evidence and post-read capability. Fragment-producing
  sequences additionally require verified compound or intermediate-rebinding evidence bound to the
  same realization, base, profile and steps. These are supplied facts, never native guarantees.
- Equality uses full effect values (including before state), and multiplicity is retained. Sorting
  unordered evidence collections never deduplicates effects or chooses a preferred lowering.
- OPEN-017 evidence production/authenticity and OPEN-001 native identity remain unresolved. This task
  validates structural evidence only, with no probe, native execution or retry implementation.
