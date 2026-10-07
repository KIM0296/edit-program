# Execution Transaction & Postflight Verification Contract v1

Status: **Accepted Chat Product/Architecture baseline**

## Purpose

Define the non-native execution contract that governs what must be true before a destructive apply,
how transaction progress and failure are represented, how rollback capability is treated, how
postflight verification determines commit, and when promotion is allowed.

Core principles:

> Execution success is not edit success. Verified state equality is edit success.

> The product commit point is after postflight MATCH, not after the final native mutation call.

> Rollback capability is never assumed. It must be proven by runtime evidence.

> An unrecovered partial mutation places destructive AI into recovery-required lockdown.

This contract does not implement Resolve mutation.

## Architecture position

```text
ExpectedDiff
  +
SafetyPreflightResult(PASS)
  +
ExecutionAuthorization
        ↓
Precommit Validation
        ↓
Execution Transaction
        ↓
Native Apply (future)
        ↓
Fresh Postflight Observation
        ↓
ActualDiff
        ↓
ExpectedDiff vs ActualDiff
        ↓
Transaction Outcome
        ↓
Promotion Eligibility
```

## Authorization boundary

Safety PASS is not apply permission.

A destructive apply requires an immutable ExecutionAuthorization bound to:

- exact ExpectedDiff
- exact SafetyPreflightResult
- exact base snapshot/state
- explicit approval/authorization reference
- authorization contract version

Changing any bound artifact invalidates the authorization.

## Precommit revalidation

Immediately before mutation, revalidate at least:

- current timeline/project identity
- current snapshot/version/state token
- Safety PASS still current
- authorization still current
- target identities resolvable
- required executor capabilities available
- no global recovery-required lockdown

Failure before mutation produces no mutation and terminates as stale/failed-before-mutation.

Human edits always win over pending AI apply.

## TransactionPhase and TransactionOutcome are separate axes

### TransactionPhase

- PREPARED
- PRECOMMIT_VALIDATING
- APPLYING
- POSTFLIGHT_VERIFYING
- ROLLING_BACK
- TERMINAL

Phase describes where the transaction is.

### TransactionOutcome

- NONE
- VERIFIED_COMMITTED
- ABORTED_STALE
- FAILED_BEFORE_MUTATION
- FAILED_PARTIAL_RECOVERED
- FAILED_PARTIAL_UNRECOVERED
- FAILED_POSTFLIGHT_RECOVERED
- FAILED_POSTFLIGHT_UNRECOVERED
- UNVERIFIED_APPLY

Outcome describes the terminal meaning.

A non-terminal phase must use outcome NONE.

VERIFIED_COMMITTED is the only successful destructive outcome.

## Normal phase path

```text
PREPARED
→ PRECOMMIT_VALIDATING
→ APPLYING
→ POSTFLIGHT_VERIFYING
→ TERMINAL / VERIFIED_COMMITTED
```

APPLYING may never transition directly to VERIFIED_COMMITTED.

Postflight verification is mandatory.

## Product atomicity vs native atomicity

Native/physical atomicity is a runtime capability question.

Product atomicity means:

- partial mutation is never reported as committed success
- postflight mismatch is never committed success
- unrecovered partial mutation is never promoted
- rollback success is independently verified

This contract does not claim Resolve provides a native atomic transaction API.

## ExecutionStepStatus

Each planned native step must be accounted for with one of:

- NOT_STARTED
- SUCCEEDED
- FAILED
- OUTCOME_UNKNOWN

OUTCOME_UNKNOWN is a first-class state.

It represents cases such as transport/bridge timeout where the native operation may or may not have
executed.

## Blind retry is forbidden

An OUTCOME_UNKNOWN mutation must not be blindly retried.

Required sequence:

```text
OUTCOME_UNKNOWN
→ fresh state reconciliation
→ determine observed consequence
→ continue / recover / fail
```

No duplicate destructive retry before reconciliation.

## Execution journal

Use append-style immutable transaction events.

Recommended fields:

- transaction_ref
- sequence_number
- event_kind
- artifact references
- step/result metadata

Ordering uses explicit sequence numbers, not timestamps alone.

Events are appended, never rewritten.

Suggested event kinds:

- TRANSACTION_PREPARED
- PRECOMMIT_PASSED
- PRECOMMIT_FAILED
- STEP_STARTED
- STEP_SUCCEEDED
- STEP_FAILED
- STEP_OUTCOME_UNKNOWN
- RECONCILIATION_RECORDED
- POSTFLIGHT_STARTED
- POSTFLIGHT_MATCHED
- POSTFLIGHT_MISMATCH
- POSTFLIGHT_UNVERIFIED
- ROLLBACK_STARTED
- ROLLBACK_COMMAND_COMPLETED
- ROLLBACK_VERIFIED
- ROLLBACK_FAILED
- TRANSACTION_TERMINATED

## Native executor report is not truth

Native command return values and executor self-report are diagnostic evidence only.

Commit requires fresh read-only postflight observation and typed diff verification.

## Postflight

After mutation, obtain a fresh read-only observation through the observation/read path.

ActualDiff is derived from:

```text
Base Snapshot + Post Snapshot
```

and compared with ExpectedDiff.

ExpectedDiff == ActualDiff uses ADR-025 / INV-016 semantics.

## Postflight status

Reuse or align with:

- MATCH
- MISMATCH
- UNVERIFIED
- STALE

### MATCH

All expected typed changes occurred exactly and no unlisted change occurred within the validated
preservation scope.

### MISMATCH

Any extra, missing or wrong typed change.

### UNVERIFIED

State may appear plausible but required identity/capability evidence is insufficient.

### STALE

The verification relationship itself is invalid.

Only MATCH may support VERIFIED_COMMITTED.

## Exact verification

v1 integer-frame equality is exact.

No implicit ±1 frame tolerance.

Expected -40 / actual -39 is mismatch.

Media/source/duration/track/topology preservation requirements also remain exact according to the
approved diff contract.

## Product commit point

The product commit point occurs only after postflight MATCH.

Native mutation calls completing successfully do not commit the product transaction.

TimelineVersion advances once only after VERIFIED_COMMITTED, preserving ADR-009.

Failure, mismatch, unverification, or verified rollback do not advance committed TimelineVersion.

## RollbackCapability and RollbackPolicy are separate axes

### RollbackCapability

- SUPPORTED_VERIFIED
- SUPPORTED_UNVERIFIED
- UNSUPPORTED
- UNKNOWN

This describes runtime evidence about the mechanism.

### RollbackPolicy

- AUTO_ELIGIBLE
- MANUAL_ONLY
- NOT_AVAILABLE

This describes whether the product may automatically attempt rollback.

Default v1 relationship:

- SUPPORTED_VERIFIED -> may be AUTO_ELIGIBLE
- SUPPORTED_UNVERIFIED -> MANUAL_ONLY
- UNSUPPORTED / UNKNOWN -> NOT_AVAILABLE

A future policy may be more restrictive, never more permissive without review.

RollbackCapability must not be inferred from the existence of an Undo menu/API name.

## Rollback triggers

Rollback eligibility is evaluated after at least:

- prior mutation followed by a later step failure
- reconciled OUTCOME_UNKNOWN showing unexpected partial state
- postflight MISMATCH

Rollback may also be required by future approved failure classes.

## Rollback verification

Rollback command success is not rollback success.

Required path:

```text
rollback attempt
→ fresh read-only snapshot
→ compare with transaction base
→ base-state MATCH
```

Only then may rollback be recorded as verified.

A rollback API success with non-matching observed state is ROLLBACK_FAILED.

## Failure + recovery is not success

A failed transaction that restores the base is still a failed edit:

- FAILED_PARTIAL_RECOVERED
- FAILED_POSTFLIGHT_RECOVERED

Do not rewrite it as VERIFIED_COMMITTED.

Recovery outcome and edit success remain separate concepts.

## Unrecovered partial mutation lockdown

If partial mutation remains and recovery is not verified:

- outcome is FAILED_PARTIAL_UNRECOVERED or FAILED_POSTFLIGHT_UNRECOVERED
- global destructive AI execution enters recovery-required lockdown

Allowed during lockdown:

- read-only snapshot
- diagnostics
- diff inspection
- recovery guidance/reconciliation

Blocked during lockdown:

- new destructive AI apply
- blind retry
- promotion
- automatic continuation of another destructive transaction

Lockdown is released only after a new coherent authoritative state is explicitly re-established.

User acknowledgement alone is not sufficient evidence of state coherence.

## Promotion eligibility

Promotion is a pure eligibility derivation.

Promotion requires all of:

- authorization current
- Safety PASS current
- all execution steps accounted for
- transaction outcome VERIFIED_COMMITTED
- postflight MATCH
- no recovery-required lockdown

Any missing condition -> NOT_ELIGIBLE.

UNVERIFIED_APPLY can never promote.

## Stable execution targets

All native targets must be resolved against the authorized base before mutation.

Do not re-resolve later targets by current timeline position after earlier mutations.

No mid-transaction "find whatever is now at frame X" targeting.

Stable placement/source correspondence remains required.

## Idempotency and uncertain command response

Destructive operations are not assumed idempotent.

Timeout/transport uncertainty does not mean failure.

State reconciliation precedes any retry.

## Executor capability declaration

A future executor/adapter should explicitly declare capabilities such as:

- range removal
- placement move
- native ripple primitive
- undo/rollback
- post-read

Missing required lowering capability -> execution unsupported before mutation.

## Execution IR boundary

Future native execution should use:

```text
ExpectedDiff
→ Validated Execution IR
→ Resolve-native commands
```

Safety does not emit raw native commands.

LLM-generated script strings are never executed directly.

Execution IR is immutable and bound to exact ExpectedDiff, Safety PASS and Authorization.

## Crash/restart

An unfinished transaction after restart must never be assumed committed.

Future persistence/restart reconciliation must inspect unfinished journal + current Resolve state.

Crash recovery implementation is deferred.

## TASK-016 boundary

TASK-016 may implement pure immutable transaction/postflight foundation only:

- ExecutionAuthorization
- TransactionPhase
- TransactionOutcome
- ExecutionStepStatus / ExecutionStepResult
- TransactionEvent / TransactionJournal
- RollbackCapability
- RollbackPolicy
- precommit validation input/result
- postflight verification input/result references
- recovery-required state
- PromotionEligibility
- pure state-transition validation
- pure outcome derivation
- pure rollback-policy derivation
- deterministic/immutable tests

TASK-016 must not implement:

- actual Resolve mutation
- actual Undo/rollback
- actual postflight snapshot capture
- native executor
- execution IR lowering to Resolve
- crash persistence
- automatic recovery
- persistent identity resolution
- authority promotion action

## Accepted v1 decisions

1. Product commit point is after postflight MATCH.
2. Native mutation success is not commit.
3. Rollback capability is never assumed.
4. Rollback itself requires fresh-state verification.
5. Unrecovered partial mutation triggers destructive AI lockdown.
6. TransactionPhase and TransactionOutcome are separate axes.
7. OUTCOME_UNKNOWN is a first-class execution-step state.
8. Blind retry after uncertain mutation response is forbidden.
9. RollbackCapability and RollbackPolicy are separate.
10. Automatic rollback eligibility requires SUPPORTED_VERIFIED capability and an allowing policy.
11. Safety PASS is not execution authorization.
12. Precommit currentness is mandatory.
13. Human edits win over pending AI execution.
14. Executor does not replan or reinterpret.
15. LLM code is never directly executed.
16. Partial mutation is never committed success.
17. Product success requires VERIFIED_COMMITTED.
18. Failed edit + successful recovery remains failed edit.
19. Promotion requires current authorization + current Safety PASS + VERIFIED_COMMITTED + postflight MATCH + no lockdown.
20. UNVERIFIED_APPLY cannot promote.

## Final principle

> The executor's job is not to make a command run. Its job is to produce exactly the authorized
> state transition — and prove that it did.
