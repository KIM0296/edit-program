# VS-001I — Adapter-Neutral Runtime Integration Foundation

Status: **GO candidate for review of bounded composition only.**
Live destructive qualification remains **HOLD**. Structural composition readiness
does not qualify live mutation. No commit or push is part of this task.

## Authoritative base and change receipt

- Verified remote main: `26c9574a1415807c7c33a6cd1eca4177e414d467`.
- Verified tree: `eb7b1f83a70ab5e86ff04e2e8bc967c748ed5083`.
- Source: `https://github.com/KIM0296/edit-program.git`, main after PR #53 / VS-001G.
- Branch: `feature/vs001i-runtime-integration`.
- Worktree: `C:/Users/c/source/repos/edit-program-vs001i`.
- HEAD remains the authoritative base; changes are uncommitted.
- Exact new files:
  - `src/davinci_ai_editor/runtime_integration.py`
  - `tests/test_runtime_integration.py`
  - `docs/VS_001I_RUNTIME_INTEGRATION_STATUS.md`

No existing semantic module or configuration changed. No native adapter, Resolve
execution, transport, production persistence, concurrency algorithm, or live
destructive qualification was implemented. No contract change was required.

## Public API and retained types

The seven bounded operations are:

```python
compose_admission(authorized, *, authority, lifecycle, observations, resolution)
advance_execution_once(evidence, *, lifecycle)
reconcile_execution(evidence, *, lifecycle)
request_rollback(evidence, request, *, lifecycle)
finalize_postflight(evidence, verification_ref, *, observations, authority, lifecycle)
prepare_promotion(evidence, *, identity, authority, lifecycle, observations)
publish_promotion(evidence, *, authority)
```

All return `IntegrationResult`. Port arguments use the five existing Protocols;
there is no additional port or run-to-completion operation.

Only three frozen record classes are added:

- `CallRecord`: operation name, exact input references, exact returned object.
  An unexpected side-effecting port exception is retained as the exact exception.
  Order describes this caller's trace, not authenticated runtime event ordering.
- `IntegrationEvidence`: the exact `AuthorizedEdit`, latest returned `Transaction`
  when available, ordered calls, and typed references to retained stage artifacts.
  It stores no independent phase, outcome, readiness, or continuation status.
- `IntegrationResult`: updated evidence plus the exact existing operation result.

Payloads remain `RuntimeAdmissionEvidence`, `AdmissionResult`,
`RuntimeFinalizationEvidence`, `FinalizationResult`, `PortValue`, `PortIssue`,
`LifecycleResult`, `Transaction`, `PrecommitFacts`, `CurrentAuthorityFacts`,
`CandidateWorkState`, `ActualDiff`, and `ApplicationResultEvidence`. Existing
payload aliases and immutable native observations are reused. Type aliases only
describe allowed retained objects; they are not duplicate DTOs or state machines.

## Bounded composition

| Operation | Calls and responsibility | Stop/retention behavior |
| --- | --- | --- |
| Admission | Authority read → recovery observation → admission currentness → resolution → existing PrecommitFacts/RuntimeAdmissionEvidence → admit_execution | Any issue stops. UNKNOWN recovery stops before boolean facts. Readiness and currentness are never upgraded. Resolution/currentness mismatch is not repaired. Original BLOCKED/STALE/READY result retained. |
| Execution | Validate existing Transaction state, then at most one execute_next | APPLYING, no unresolved/failed/active step, and an unstarted declared step required. Returned transaction is adopted before issue interpretation. Definition, exact journal prefix, allowed event kinds, one new start maximum, and no attempted-step restart are checked. |
| Reconciliation | One reconcile call for an existing explicit OUTCOME_UNKNOWN report | An active STEP_STARTED is not rewritten into UNKNOWN. Independent read evidence remains lifecycle producer responsibility. No automatic advancement follows reconciliation. |
| Rollback | One rollback call under existing transaction policy/capability | Failed execution or failed postflight and mutation exposure are required. Unresolved execution blocks. No observation proof means no verified recovery. ROLLING_BACK evidence cannot start rollback again merely because verification is missing. |
| Postflight | Post observation → new authority read → new recovery observation → postflight currentness → finalize_edit | All declared steps must be SUCCEEDED; all_steps_accounted including FAILED is insufficient. ActualDiff is supplied only by observation. First finalization has no promotion facts, identity, or prior postflight. |
| Promotion | Identity first → new authority read → new recovery observation → promotion currentness → second finalize_edit | Identity issues stop before further acquisitions. Requires retained VERIFIED_COMMITTED and exact original PostflightRecord/ActualDiff. Reuses original postflight facts/reference and supplies separate promotion facts/reference. |
| Publication | One publish with exact retained promotion authority, semantic proposal, and promotion currentness | No replacing expected with another read. Accepted semantic transitions are required. Publication result is separate from FinalizationResult. No automatic retry. |

Authority is acquired separately at admission, postflight, and promotion. The
promotion read is the publication expected state. Human edits are handled by
existing authority/orchestration semantics; no silent rebase occurs.

`VERIFIED_COMMITTED` with `FRESH_PROMOTION_FACTS_MISSING` is a historical commit
with intentionally pending promotion, not execution failure. Missing identity or
later human change preserves that exact committed transaction. Semantic promotion
still has `durable_promotion == NOT_PERFORMED`. PERSISTED/DUPLICATE receipts and
STALE/CONFLICT/UNAVAILABLE/UNKNOWN issues do not mutate this semantic result.
The persistence producer remains responsible for actual conditional-write and
duplicate evidence; test replies do not implement a store.

## Continuity, provenance, and receipt retention

The integration retains all admission authority/recovery/currentness/resolution
receipts, admission aggregate/result, lifecycle input transaction and returned
tuple, post observation, postflight authority/recovery/currentness, finalization
aggregate/result/PostflightRecord, identity result, promotion acquisitions and
aggregate/result, and exact publication arguments/result. Partial acquisition
successes and all issues remain in `calls` even when the stage cannot finish.
No serialization or reconstruction of these payloads occurs.

Currentness receipts must name an acquisition and correlate through `source_refs`
to the authority and recovery receipts actually supplied to that call. Resolution
must reference admission currentness. Post observation must reference retained
admission currentness. Identity must reference retained post observation.
These are integration correlation requirements using existing metadata, not new
claims about native authenticity.

Snapshot timeline/version/token identifiers are compared for correspondence only.
Neither snapshot equality nor state-token equality creates currentness. Supplied
binding/authorization/recovery facts must agree across ports; mismatches stop.
Missing postflight acquisition provenance blocks finalization.

Promotion rejects the same currentness PortValue, receipt ref, acquisition ref,
or snapshot capture reused from earlier observations, absent acquisition refs,
receipt-only relabeling, reused admission/postflight authority reads, and missing
source links to the newly called authority/recovery producers. It also rejects a
reused post-observation acquisition/capture. Changing strings cannot authenticate
freshness. No timestamp, sleep window, numeric/lexical ordering, or synthetic
acquisition-order algorithm is used.

Publication additionally checks that its exact authority/currentness/proposal
objects were retained from their producing calls. A substituted expected-state
wrapper is rejected. Calling publish again with evidence of a prior attempt is
blocked; coordination of independent callers holding older evidence remains open.

## Ordinary uncertainty and defective producers

All seven existing PortIssue kinds are normal bounded outcomes, retained exactly.
Lifecycle issues remain alongside the latest returned Transaction; they never
replace its journal. Integration-detected missing evidence or correlation failure
returns an existing PortIssue with a comparison-only receipt and no acquisition.
An invalid returned lifecycle prefix/definition/multi-step progression is retained
as returned evidence, flagged as a producer contract violation, and barred from
further progression. The integration does not fix or certify that returned journal.

Programming defects before dispatch may raise. At a lifecycle call boundary,
dispatch cannot safely be ruled out if a producer raises without returning a
journal. The exact exception and last known input are retained, `transaction` is
set to None to avoid calling that input the latest journal, and an UNKNOWN
contract/instrumentation failure is returned. Subsequent progression stops. No
missing event is invented, and the operation is not rerun. The two localized broad
exception handlers cover this lifecycle boundary and possibly completed publication;
they retain the failure rather than converting it into success or retry permission.

Reconciliation and rollback evidence are supplied by the lifecycle producer's
independent read producer. A command acknowledgement or return value is never
observation proof. This integration does not authenticate read provenance. UNKNOWN
recovery at any acquisition fence stops before CurrentAuthorityFacts can falsely
encode recovery_required=False.

## TEST_ONLY_SUPPORT verification

The test harness supplies scripted immutable values and delegates lifecycle
transitions to existing test support/transaction contracts. Every synthetic port
receipt is marked TEST_ONLY_SUPPORT. VERIFIED/current literals are fixtures, not
native qualification. No adapter, persistent store, or production ActualDiff
algorithm is present.

| Coverage | Checks |
| --- | --- |
| Admission | Happy-path order and exact retention; each normal issue kind at authority/currentness/resolution; UNKNOWN recovery; original BLOCKED/STALE; UNKNOWN/FALSE readiness preserved; resolution correspondence mismatch. |
| Execution | One call per advancement; explicit two-step progression; active/UNKNOWN/FAILED stop; latest transaction retained with issue; prefix/definition/multiple-step producer violations; no run-to-completion API. |
| Reconciliation | Active start cannot be repaired; independent read required; successful reconciliation never auto-advances; every normal issue preserves the journal. |
| Rollback | Acknowledgement alone is not recovery; independent base read verifies recovery through existing semantics; missing verification never triggers another rollback. |
| Postflight | FAILED with all_steps_accounted rejected; authority/recovery reacquired; issues and snapshot mismatch stop; MATCH commits with pending promotion; mismatch/unverified evidence cannot promote. |
| ActualDiff | Exact port-produced object retained; changing ExpectedDiff changes comparison result but not the same synthetic runtime observation's ActualDiff. |
| Promotion | Identity precedes acquisition; every identity issue preserves commit and avoids acquisition; separate authority/recovery/currentness calls; same object/acquisition/capture/relabel or missing provenance rejected; exact committed evidence reused; later human edit preserves commit and blocks promotion. |
| Later recovery | UNKNOWN at postflight/promotion stops before currentness; promotion acquisition issues preserve historical commit. |
| Publication | Exact arguments and no extra read; PERSISTED/DUPLICATE separate; STALE/CONFLICT/UNAVAILABLE/UNKNOWN retained with no retry; prior semantic result unchanged; substituted expected receipt rejected; bare publication exception retained as UNKNOWN. |
| Defects/structure | Predispatch programming exception; postdispatch bare exception preserves last-known evidence without claiming latest; frozen containers; five Protocol assignments type-check; AST restricts public operations/imports/classes and excludes parallel machines, native constructors, transport, and timestamp heuristics. |

Validation used the existing `vs001e-validation-env` interpreter with
`PYTHONPATH=src;tests`, `MYPYPATH=src;tests`, and `PYTHONDONTWRITEBYTECODE=1`.

| Command | Final receipt |
| --- | --- |
| `python -m pytest -q -p no:cacheprovider tests/test_runtime_integration.py` | 98 passed, 0 failed, 0 skipped |
| `python -m pytest -q -p no:cacheprovider tests/test_runtime_integration.py tests/test_runtime_ports.py tests/test_orchestration.py` | 191 passed, 0 failed, 0 skipped |
| `python -m pytest -q -p no:cacheprovider` | 1625 passed, 0 failed, 1 skipped |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check src/davinci_ai_editor/runtime_integration.py tests/test_runtime_integration.py` | 2 files already formatted |
| `python -m mypy` | Success, 36 source files; existing strict configuration |
| `python -m mypy --strict --follow-untyped-imports --explicit-package-bases src/davinci_ai_editor/runtime_integration.py tests/test_runtime_integration.py` | Success, 2 explicit source files |
| `git diff --check` and `git -c core.autocrlf=false diff --no-index --check -- NUL <each-new-file>` | PASS; trailing whitespace and final-newline checks also passed |
| `git diff --exit-code HEAD` and exact untracked-file allowlist | PASS; only the three listed new files, all existing tracked files unchanged |

The one full-suite skip is the existing opt-in intentional red test at
`tests/test_naive_inv001.py:27`; its normal regression test runs.
Final remote `git ls-remote` verification still reports the authoritative main SHA
above. Existing tracked files remain identical to the authoritative base.

## Open dependencies and limits

- OPEN-002: production result identity and authority evidence boundary.
- OPEN-008: concurrent work invalidation, conditional publication, races, and
  candidate lifecycle coordination.
- Production persistent placement identity.
- Native currentness authenticity and acquisition authenticity/temporal meaning.
- Observation-to-execution atomicity: no approved lock, lease, atomic
  snapshot+dispatch, or compare-and-execute primitive.
- Crash-safe journal retention and exactly-once execution/persistence.
- Interrupted rollback resume policy and concurrent caller coordination.

Public integration interfaces remain edition/transport neutral. Studio runtime
qualification remains HOLD; Free external transport remains HOLD; Free read
capability evidence remains ACTIVE. Read evidence does not qualify mutation.

Contract mismatch: none requiring a change to existing semantic modules. An active
STEP_STARTED without an explicit outcome report remains a bounded unresolved stop
under existing transaction semantics, not a reason to add a repair event here.

Next recommended task: review this composition foundation and its test receipts.
Native qualification and unresolved producer/concurrency contracts require separate
approval and evidence. Stop before commit/push.
