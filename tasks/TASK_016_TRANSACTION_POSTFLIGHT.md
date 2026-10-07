# TASK-016 — Transaction State & Postflight Verification Foundation

Status: **Implemented; validation and Chat Gate tracked in docs/reports/TASK_016_COMPLETION.md**

Basis:
- ADR-006 LLM Emits IR Only
- ADR-009 Version Advances on Successful Plan Commit
- ADR-015 Candidate Authority
- ADR-016 Human Priority
- ADR-025 Expected Diff & Temporal Displacement
- ADR-026 Safety Preflight Integration
- ADR-027 Execution Transaction & Postflight Verification v1
- INV-012/013/014/015/016

## Purpose

Implement a pure immutable state-machine foundation for execution authorization, transaction
progress/failure, rollback capability-policy separation, postflight outcome interpretation, lockdown,
and promotion eligibility.

No Resolve mutation is implemented.

## Required domain

At minimum:

- ExecutionAuthorization
- TransactionPhase
- TransactionOutcome
- ExecutionStepStatus
- ExecutionStepResult
- TransactionEventKind
- TransactionEvent
- TransactionJournal
- RollbackCapability
- RollbackPolicy
- PrecommitStatus / PrecommitResult
- RecoveryState or recovery_required flag/value
- PromotionEligibility
- pure transition / validation / derivation functions

## Mandatory transaction phases

- PREPARED
- PRECOMMIT_VALIDATING
- APPLYING
- POSTFLIGHT_VERIFYING
- ROLLING_BACK
- TERMINAL

## Mandatory outcomes

- NONE
- VERIFIED_COMMITTED
- ABORTED_STALE
- FAILED_BEFORE_MUTATION
- FAILED_PARTIAL_RECOVERED
- FAILED_PARTIAL_UNRECOVERED
- FAILED_POSTFLIGHT_RECOVERED
- FAILED_POSTFLIGHT_UNRECOVERED
- UNVERIFIED_APPLY

Non-terminal phase requires outcome NONE.

VERIFIED_COMMITTED is only legal in TERMINAL.

## Execution step states

- NOT_STARTED
- SUCCEEDED
- FAILED
- OUTCOME_UNKNOWN

OUTCOME_UNKNOWN must never be silently converted to FAILED/SUCCEEDED.

Blind retry is forbidden until explicit reconciliation input is supplied.

## Authorization

Authorization must bind exact:

- ExpectedDiff ref
- Safety result ref
- base snapshot ref
- approval/authorization ref
- contract version

Authorization mismatch invalidates precommit.

Do not invent approval semantics.

## Precommit

Represent pure caller-supplied checks for:

- current base/snapshot match
- Safety PASS/currentness
- authorization currentness
- target resolvability
- executor capability readiness
- no recovery-required lockdown

No mutation side effects.

Stale -> ABORTED_STALE path.

Other pre-mutation failure -> FAILED_BEFORE_MUTATION path.

## Phase-transition rules

At minimum enforce:

```text
PREPARED
→ PRECOMMIT_VALIDATING

PRECOMMIT_VALIDATING
→ APPLYING
or TERMINAL failure

APPLYING
→ POSTFLIGHT_VERIFYING
or ROLLING_BACK
or TERMINAL unrecovered failure

POSTFLIGHT_VERIFYING
→ TERMINAL VERIFIED_COMMITTED
or ROLLING_BACK
or TERMINAL UNVERIFIED_APPLY/unrecovered failure

ROLLING_BACK
→ TERMINAL recovered/unrecovered failure
```

No APPLYING -> VERIFIED_COMMITTED direct transition.

## Commit rule

VERIFIED_COMMITTED requires:

- all required execution steps accounted for as successfully applied
- postflight status MATCH
- no recovery-required condition
- current authorization/Safety references retained

Do not increment TimelineVersion in this task, but expose pure eligibility/commit semantics consistent
with ADR-009.

## Rollback capability

Implement:

- SUPPORTED_VERIFIED
- SUPPORTED_UNVERIFIED
- UNSUPPORTED
- UNKNOWN

## Rollback policy

Implement:

- AUTO_ELIGIBLE
- MANUAL_ONLY
- NOT_AVAILABLE

Capability and policy are distinct.

Default pure derivation must never allow AUTO_ELIGIBLE unless capability == SUPPORTED_VERIFIED.

A caller may choose a more restrictive policy.

## Rollback verification

Represent rollback result separately from native command return.

Recovered outcomes require explicit supplied base-state verification evidence/status.

Do not infer rollback success from a command-success boolean.

## Recovery lockdown

Unrecovered partial/postflight failures must derive:

```text
recovery_required = true
```

While recovery_required:

- promotion eligibility false
- new destructive execution eligibility false

Pure domain may expose these booleans/statuses; no UI/runtime enforcement in TASK-016.

## Transaction journal

Journal is immutable append-style event history with explicit monotonic sequence numbers.

Do not overwrite prior events.

Reject duplicate/non-monotonic sequence numbers.

Derivation should preserve raw event history.

## Step uncertainty

OUTCOME_UNKNOWN must require reconciliation before:

- retry
- proceeding as success
- rollback-success claim
- verified commit

Do not implement actual retry.

## Postflight

Consume precomputed postflight status only:

- MATCH
- MISMATCH
- UNVERIFIED
- STALE

Do not call ActualDiff verifier or snapshot adapter.

MATCH is required for VERIFIED_COMMITTED.

UNVERIFIED -> UNVERIFIED_APPLY or recovery path as supplied by approved state semantics; never commit.

MISMATCH cannot commit.

## Promotion eligibility

ELIGIBLE only when all supplied facts prove:

- authorization current
- Safety PASS/current
- transaction terminal outcome VERIFIED_COMMITTED
- postflight MATCH
- recovery_required false

Otherwise NOT_ELIGIBLE.

Do not call Authority transition.

## Required tests

At minimum prove:

1. frozen/immutable domain values
2. defensive event collections
3. TransactionPhase and TransactionOutcome are distinct types
4. nonterminal phase cannot carry terminal outcome
5. TERMINAL VERIFIED_COMMITTED requires exact legal prerequisites
6. normal phase path valid
7. skipping postflight before commit invalid
8. precommit stale -> terminal ABORTED_STALE
9. failed-before-mutation cannot report mutated steps
10. partial step failure never VERIFIED_COMMITTED
11. OUTCOME_UNKNOWN is distinct from FAILED/SUCCEEDED
12. OUTCOME_UNKNOWN blocks blind retry eligibility
13. reconciliation required before unknown step can be classified
14. executor self-report alone cannot derive commit
15. postflight MATCH required for commit
16. postflight MISMATCH blocks commit
17. postflight UNVERIFIED blocks commit
18. postflight STALE blocks commit
19. RollbackCapability enum exact
20. RollbackPolicy enum exact
21. AUTO_ELIGIBLE impossible unless capability SUPPORTED_VERIFIED
22. SUPPORTED_UNVERIFIED defaults no more permissive than MANUAL_ONLY
23. UNKNOWN/UNSUPPORTED defaults NOT_AVAILABLE
24. rollback command success without base-state verification is not recovered
25. verified rollback -> recovered failure outcome, never VERIFIED_COMMITTED
26. rollback mismatch -> unrecovered failure
27. partial unrecovered -> recovery_required true
28. postflight unrecovered -> recovery_required true
29. recovered failure -> no promotion
30. recovery_required -> no promotion
31. VERIFIED_COMMITTED + postflight MATCH + current auth/safety + no lockdown -> promotion eligible
32. UNVERIFIED_APPLY -> promotion not eligible
33. authorization bound refs cannot be swapped/reused silently
34. Safety result ref mismatch blocks precommit/eligibility
35. base snapshot ref mismatch blocks precommit
36. journal sequence numbers explicit and monotonic
37. duplicate/nonmonotonic journal sequence rejected
38. journal records failure then recovery without rewriting history
39. failed transaction remains failed after successful recovery
40. deterministic state derivation
41. no actual Resolve API
42. no actual rollback/Undo
43. no actual snapshot capture
44. no ExpectedDiff compiler call
45. no Safety preflight call
46. no Authority transition
47. no FakeTimeline.apply
48. TASK-001..015 regression remains green

## Explicitly out of scope

- Resolve mutation
- Resolve Undo/rollback
- execution IR native lowering
- postflight snapshot acquisition
- ActualDiff calculation
- automatic retry/recovery
- crash persistence/restart reconciliation
- TimelineVersion mutation
- authority promotion action
- executor implementation
- production identity resolution

## Workflow

1. Do not start until TASK-015 is Chat APPROVED and merged, unless Chat explicitly reorders tasks.
2. Start from then-current main.
3. Treat ADR-027 and this spec as authoritative.
4. Record architecture ambiguity as OPEN; do not invent Resolve/runtime guarantees.
5. Red-first tests.
6. Implement pure immutable transaction/postflight foundation.
7. Full regression.
8. Python 3.11 CI / Ruff / strict mypy.
9. Write docs/reports/TASK_016_COMPLETION.md.
10. Open PR and request Chat Gate.
11. Do not merge or start the next task automatically.

## Success definition

Represent and validate the full logical transaction lifecycle from authorization through postflight,
recovery state and promotion eligibility without performing native mutation, assuming rollback, or
mistaking uncertain/partial execution for verified success.


## TASK-016 implementation notes (before source)

- Add transaction.py with immutable bound authorization, caller facts, ordered opaque step
  refs (not commands/IR), typed event payloads and append-only journal. Only value enums/
  snapshot refs are imported from earlier layers; no evaluator or executor is called.
- The prepared event binds the complete immutable definition, including authorization/approval,
  ordered step refs and rollback capability/policy; these cannot be swapped under existing history.
- Transaction validates its journal through a deterministic pure fold. Its derived state
  cannot be submitted as a replacement history. Constructors reject illegal phase/outcome,
  payload, sequence, artifact and step-order combinations. Sequence gaps are allowed;
  duplicates/reversal and mixed transaction journals are rejected, never sorted/repaired.
- Add explicit PRECOMMIT_STARTED and POSTFLIGHT_STALE events alongside suggested event kinds.
  Precommit consumes current snapshot, bound Safety status/verdict/currentness, authorization
  currentness, target/capability facts and recovery lockdown. Stale takes precedence over
  other before-mutation failures. No mutation report is legal on a failed-precommit path.
- STEP_STARTED is journal progress, not a fifth execution status. One active step at a time;
  a report is required before continuing. SUCCEEDED may have mutated; FAILED explicitly
  records whether mutation may have occurred; OUTCOME_UNKNOWN always preserves uncertainty.
- Unknown reports require bound fresh StepReconciliation before classification/continuation
  or recovered claims. No retry transition is implemented, even after reconciliation.
  Unresolved uncertainty may terminate unrecovered, never committed/recovered.
- Postflight consumes precomputed DiffVerificationStatus and independently supplied current
  authorization/Safety facts. MATCH plus all accounted successful steps permits commit only
  after POSTFLIGHT_VERIFYING. No verification function or TimelineVersion update is called.
- Rollback requests are explicit caller events. Policy is no more permissive than capability;
  automatic eligibility is metadata only. Recovery requires a command-report record followed
  by fresh base-state verification MATCH. Base verification is also reconciliation of an
  uncertain rollback response; native return alone never certifies recovery.
- Terminal outcomes are explicit requested classifications validated against prior evidence.
  Failed edits remain failures after recovery. Terminal journals cannot be rewritten/resumed.
- Unrecovered outcomes derive recovery_required. UNVERIFIED_APPLY also blocks promotion and
  new-destructive-attempt eligibility; no lockdown-release/runtime policy is implemented.
- Promotion consumes freshly supplied bound authorization/Safety/current post-state facts,
  verified commit, successful accounted steps and no lockdown. It never calls Authority.
