# VS-001G — Runtime Port Interface Foundation

Disposition: GO candidate for PORT DECLARATIONS + TEST_ONLY_SUPPORT CONTRACT TESTS.
VS-001F Chat Gate: APPROVED, including all six additional authoritative conditions.
No runtime, native adapter, execution, transport, or persistence implementation.
No commit or push performed. This is an implementation-stage review receipt.

## Authoritative base and scope

- GitHub main verified: `1672dddae3367a7ef2c00a5c37146cfffc8b0f94`.
- Exact tree: `c518a3a3c527d1dfc55d9605f240dff19793e7a4`.
- Local fetched main SHA/tree independently matched the GitHub receipt.
- PR #52 / VS-001E is merged at that base.
- Branch: `feature/vs001g-runtime-ports`.
- Worktree: `C:\Users\c\source\repos\edit-program-vs001g`.
- Created clean from fetched main; existing worktrees and remote configuration retained.
- Exact new files:
  - `src/davinci_ai_editor/runtime_ports.py`
  - `tests/test_runtime_ports.py`
  - `docs/VS_001G_RUNTIME_PORTS_STATUS.md`
- No existing semantic contract changed; no contract mismatch identified.

Re-audit retained the approved minimum five Protocols. No renames and no extra ports.
`runtime_ports.py` is justified as a declaration boundary around existing payloads;
it contains no native construction, event progression, store, or integration algorithm.
Only common immutable metadata constructors validate their structural fields.

## Five Protocols and ownership

| Protocol | Responsibility | Exclusions |
|---|---|---|
| RuntimeObservationPort | A currentness + D independent postflight observation | No capability declaration, command execution, or state-token generation |
| ExecutionResolutionPort | B execution target/profile/capability/effect/lowering/readiness | No mutation, ActualDiff production, or commit |
| ExecutionLifecyclePort | C execution events, reconciliation, rollback, recovery context | No parallel lifecycle, inferred success, or automatic retry |
| ApplicationResultPort | E result identity/correspondence when actually supplied | No generated result ID, next version, or forced ApplicationRecord |
| AuthorityPort | F authority read and future conditional durable publication | No store or selected concurrency algorithm |

Public methods retain the VS-001F signatures and responsibilities. Tuple aliases name
existing component groupings; they do not redefine their fields. A and D share a port,
not a single acquisition. Separate postflight and promotion acquisitions remain required.

## Payload reuse and common metadata

Existing payloads remain authoritative:

- `ExecutionIRValidationInput`, `TransactionDefinition`, and two `ObservedValue`
  readiness facts form `ResolutionPayload` (targets_resolvable, executor_ready).
- `NativeTimelineSnapshot` + `CurrentAuthorityFacts` form `CurrentnessPayload`.
- `NativeTimelineSnapshot` + `ActualDiff` form `PostflightPayload`.
- `Transaction` + optional `PortIssue` form `LifecycleResult`.
- `ApplicationResultEvidence`, `CandidateWorkState`, and `FinalizationResult` are
  used directly by the corresponding ports.
- Thin test integration assembles existing `PrecommitFacts`,
  `RuntimeAdmissionEvidence`, and `RuntimeFinalizationEvidence`; there are no copies
  of those models and no native construction in orchestration.

Minimal new metadata contracts:

- `PortReceipt`: receipt/producer references, optional acquisition reference, source
  references, limitations, and explicit PRODUCER_ASSERTION or TEST_ONLY_SUPPORT domain.
- `PortValue[T]`: existing immutable payload with its receipt. Availability does not
  imply domain readiness; a payload can legitimately contain UNKNOWN/UNVERIFIED.
- `PortIssue`: kind, reason, receipt. It is never an execution journal replacement.
- `PortIssueKind`: UNAVAILABLE, UNSUPPORTED, UNRESOLVED, AMBIGUOUS, STALE, CONFLICT,
  UNKNOWN. Ordinary runtime uncertainty does not require exceptions.
- `PortResult[T]` is the success/non-success union, not another domain state machine.
- `PublicationDisposition` is PERSISTED or DUPLICATE; other publication outcomes use
  the appropriate distinct PortIssue kind.

No existing domain type expresses this generic call availability/provenance contract.
Metadata validation establishes shape only, not authenticity, freshness, truth,
durability, or native qualification. No receipt persistence mechanism is supplied.

## Currentness, recovery, admission, and races

Snapshot/token equality does not establish currentness. New receipt strings likewise
do not establish a new acquisition. Producers own evidence authenticity, acquisition
timing/order, source retention, coverage, and disclosed limitations.

Recovery UNKNOWN returns a typed issue BEFORE any falsely certain
`CurrentAuthorityFacts(recovery_required=False)` can be constructed. The synthetic
observer test counts fact construction and verifies zero constructions on UNKNOWN.
Known TRUE is preserved and blocks admission; known FALSE is explicit fixture input.
Missing recovery history is not proof of FALSE.

Admission composition remains outside shared orchestration:

1. Supply authority state and recovery assessment with receipts.
2. Observe currentness using actual authorization/Safety/human-change evidence.
3. Resolve execution using that observation and exact approved artifacts.
4. Compose existing PrecommitFacts and RuntimeAdmissionEvidence and call admit_execution.

The test integration preserves current snapshot and authorization facts in both
validation input and precommit. Existing Safety status/verdict remain unchanged;
for the exact approved PASS artifact, safety_pass_current supplies safety_current.
Target/executor readiness comes from the resolution port. Missing components stop
composition rather than generating placeholder identities or state tokens.

Capture consistency does not establish observation-to-execution atomicity. No atomic
capture/lock/lease capability is asserted; missing guarantees must be disclosed and
cannot be interpreted as permission for live destructive dispatch.

## Lifecycle and read evidence boundary

After admission, the lifecycle producer owns the latest Transaction and exact
precommit prefix. STEP_STARTED is retained before possible dispatch; actual result
events are appended through existing transaction.transition as they happen.

- Pre-dispatch refusal may preserve the pre-mutation journal.
- Missing result with no explicit report retains the active STEP_STARTED plus UNKNOWN.
- With sufficient uncertainty-report evidence, STEP_OUTCOME_UNKNOWN records the
  existing OUTCOME_UNKNOWN status and may_have_mutated=True.
- A defect after possible dispatch retains the latest journal, explicitly reports
  uncertainty, stops, and does not retry. A pre-dispatch programming defect may raise.
- Reconciliation reads evidence through a separate synthetic observation producer;
  command reports alone cannot add RECONCILIATION_RECORDED.
- Rollback acknowledgment records only ROLLBACK_COMMAND_COMPLETED. Verified recovery
  requires independent BaseVerificationEvidence. Unknown recovery remains UNKNOWN.

LifecycleResult always includes the Transaction even on ordinary uncertainty. The
test implementations use existing transaction transitions, not parallel state axes.
Crash-safe retention, restart ownership, and exactly-once behavior remain unresolved.

## Postflight, identity, and authority publication

ActualDiff remains an observation producer responsibility. The observer method accepts
only binding/scope references and retained before observation, not ExpectedDiff values.
The test observer reuses the existing TEST_ONLY_SUPPORT simulator's independent
before/post reader; no production ActualDiff algorithm is introduced.

The independence test keeps the same simulated runtime observation and correspondence,
changes ExpectedDiff's displacement effects, and proves ActualDiff is unchanged. The
original expectation compares MATCH; the changed expectation compares MISMATCH.
Topology/relation/identity/scope truth remains a future producer obligation.

Separate acquisitions are necessary for postflight and promotion. The synthetic
integration fixture uses an explicitly supplied acquisition schedule to demonstrate
that reusing an observation or relabeling its receipt does not create freshness.
Changing both labels to an acquisition absent from that schedule also fails. This is
not a production authenticity or temporal-ordering algorithm. Orchestration's existing
distinct-reference check is preserved, not treated as sufficient provenance proof.

Result identity may be unavailable, unresolved, ambiguous, stale, or unknown after
VERIFIED_COMMITTED. The existing historical transaction remains intact while missing
ApplicationResultEvidence blocks authority promotion. The transaction-level promotion
eligibility flag alone is not evidence that identity or authority publication succeeded.
Human changes after commit likewise block promotion without rewriting commit history.

Authority publication is a declaration only. PERSISTED requires durable evidence for
the complete accepted semantic proposal; DUPLICATE requires evidence of the same prior
durable publication, not matching state values. STALE, CONFLICT, UNAVAILABLE, and UNKNOWN
remain distinct. Unknown write outcome is not safe retry permission. Test authority
fixtures return explicitly scripted receipts and perform no writes or state comparison.
No CAS/lock/lease or final concurrency algorithm is selected.
`FinalizationResult.durable_promotion` remains NOT_PERFORMED in all tests.

## Contract tests and verification receipt

Environment: external `C:\Users\c\source\repos\vs001e-validation-env`.
Commands use Python 3.11 with `PYTHONPATH=src;tests`, `MYPYPATH=src;tests`, and
`PYTHONDONTWRITEBYTECODE=1`. No runtime/native tools are invoked.

| Check | Result |
|---|---|
| New port tests | 44 passed |
| Targeted port + orchestration tests | 93 passed |
| Full pytest | 1527 passed, 1 skipped |
| Repository Ruff (`ruff check .`) | PASS |
| Existing strict mypy (`mypy`) | PASS, 35 source files |
| Explicit strict mypy for both new Python files | PASS, 2 source files |
| Existing tracked-file diff/whitespace | PASS; no tracked-file edits |
| New-file whitespace and exact three-file allowlist | PASS |

The only skip is the opt-in intentional red invariant test. Unlike the earlier VS-001E
receipt, the host symlink test passed in this validation context.

Commands:

```text
python -m pytest tests/test_runtime_ports.py -q
python -m pytest tests/test_runtime_ports.py tests/test_orchestration.py -q
python -m pytest -q
python -m ruff check .
python -m mypy
python -m mypy --strict --follow-untyped-imports --explicit-package-bases src/davinci_ai_editor/runtime_ports.py tests/test_runtime_ports.py
git diff --check
git diff --exit-code HEAD
# For each of the three new files:
git -c core.autocrlf=false diff --no-index --check -- NUL <new-file>
```

The new-file checks emitted no whitespace diagnostics. Their exit 1 denotes the
new-file difference under --no-index, not whitespace damage; explicit trailing-space,
final-newline, and extra-blank-EOF checks also passed. No files were staged for checks.

All 20 requested behaviors are covered, including same-token UNKNOWN currentness,
unknown recovery, missing/unknown execution reports, failed reconciliation, independent
reconciliation/base reads, acknowledgment-only rollback, post-dispatch instrumentation
loss without retry, typed uncertainty versus programming defects, ActualDiff independence,
reused/relabeled observations, missing identity and later human change, distinct
publication outcomes, and explicit TEST_ONLY_SUPPORT limitations.

AST tests check exactly five Protocols with declaration-only method bodies, neutral
public interfaces, allowed imports, and no duplicate lifecycle/candidate/Safety/diff
models. Static Protocol assignments check all five synthetic implementations.

## Open dependencies and stop point

- OPEN-002: production result identity and authority evidence/observation coordination.
- OPEN-008: concurrent invalidation, conditional publication, lifecycle coordination,
  race handling, durable persistence, and crash/restart ownership.
- Production persistent placement identity and native currentness authenticity.
- Observation-to-execution atomicity and exactly-once execution/persistence.
- Qualified native target/capability/effect/read/reconciliation/rollback producers.
- Protocol conformance does not mechanically certify producer semantic obligations.

Edition-neutral public contracts select no transport mechanism. Runtime track status:
Studio runtime qualification HOLD; Free external transport HOLD; Free read capability
evidence ACTIVE. Read evidence does not qualify mutation. No work on those tracks.

Next gate: review only these three files. GO candidate for this interface/test
foundation; runtime/native/persistence implementation and qualification remain HOLD.
STOP before commit/push.
