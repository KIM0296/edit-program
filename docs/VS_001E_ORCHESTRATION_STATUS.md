# VS-001E — Production shared orchestration foundation

Disposition: GO candidate for PURE APPLICATION-LAYER COMPOSITION review only.
No production runtime, native qualification, execution, or persistence is implemented.

## Base receipt and scope

- Base: main commit `678460c2810180752ef9e6825d58678acbf12de6`.
- Verified tree: `016eedac71110e9f50fbef3e4213955ff1acee4d`.
- Branch: `feature/vs001e-orchestration`.
- Worktree: `C:\Users\c\source\repos\edit-program-vs001e`.
- Created clean from that commit. No Free/integration working files copied.
- Original tracked files remain byte-content unchanged according to Git diff.
- New files: `src/davinci_ai_editor/orchestration.py`,
  `tests/test_orchestration.py`, and this document.
- No commit/push; no changes to existing domain, Safety, IR, transaction, authority,
  FakeTimeline, VS-001C support, Free/Studio code, transport, or checkpoints.

## Public boundary

Four pure application operations:

- `prepare_edit(PreparationInputs) -> PreparationResult`
- `authorize_edit(PreparedEdit, BoundApproval, CandidateWorkState) -> AuthorizationResult`
- `admit_execution(AuthorizedEdit, RuntimeAdmissionEvidence, CandidateWorkState) -> AdmissionResult`
- `finalize_edit(AuthorizedEdit, RuntimeFinalizationEvidence, CandidateWorkState) -> FinalizationResult`

Preparation retains existing immutable artifacts and their exact input objects.
`editorial_candidate` is `pause.PauseCandidate`; `authority_candidate` is
`authority.Candidate`. These are never aliased. Preparation recomputes classification,
resolves unique geometry, plans, compiles explicit participation/preservation scope,
and runs existing Safety. It checks identity/base/range/media continuity. It neither
discovers participants nor repairs facts. Geometry support provenance is retained in
the complete resolution, not flattened into the planner's smaller provenance type.

Preparation READY means the evaluated artifacts are available for review, not native
readiness. An evaluated non-PASS Safety result can be inspected but cannot authorize.
No native locator, capability manifest, lowering, runtime profile, or ActualDiff enters
PreparedEdit.

BoundApproval is a correlation record, not another approval state. It retains the
exact PreparedEdit, candidate/base and ArtifactBinding. Existing Authority APPROVED
and apply eligibility remain necessary. No approval is inferred from editorial
action/confidence. Structural equality and deterministic recomposition reject altered
artifacts even when string references are unchanged. Authorization uses the explicit
approval reference as its one-to-one in-process reference; this is not a security or
currentness token. No cross-process digest/registry is introduced. Authentic human
approval supply remains a caller/port obligation; constructing a dataclass does not
authenticate a person.

## Runtime admission and lifecycle

RuntimeAdmissionEvidence retains existing ExecutionIRValidationInput,
TransactionDefinition and PrecommitFacts. Existing IR validation and precommit are
run without weakening their requirements. Shared composition additionally checks
complete ExpectedDiff/Safety/authorization equality, exact ordered lowering steps,
matching rollback capability, and current Authority eligibility.

All runtime/currentness/readiness/recovery facts are supplied, never filled with
optimistic defaults. Missing/unknown runtime facts cannot yield READY. Native IR is
constructed outside preparation, after runtime resolution. The orchestrator executes
no command.

Successful admission creates only TRANSACTION_PREPARED, PRECOMMIT_STARTED and
PRECOMMIT_PASSED before handoff. The runtime/event port must preserve real step-start,
result, reconciliation and rollback events as they happen. Finalization requires the
exact admission prefix and a valid existing journal. It does not reconstruct missing
execution history or infer step success from ActualDiff. Semantic journal validation
does not authenticate the producer or independently establish wall-clock ordering.

## Independent actual evidence and postflight

ActualDiff is supplied independently by the runtime evidence producer. Production
orchestration has no ActualDiff constructor/producer and does not import the simulator.
Existing verify_diff is the comparator. Missing ActualDiff, unaccounted execution,
OUTCOME_UNKNOWN, MISMATCH, UNVERIFIED and STALE never cause verified commit.

Finalization appends only legal postflight events and, when existing transaction
conditions permit, VERIFIED_COMMITTED. Failed/uncertain cases retain their journal
for an external recovery decision; the foundation does not auto-rollback or invent a
terminal recovery outcome.

PostflightRecord retains the exact ExpectedDiff, ActualDiff, comparison result and
PostflightEvidence. A resumed finalization with an existing postflight journal must
provide this record. Same-reference replacement evidence is rejected structurally.
The record is an in-process artifact binding, not persisted evidence or a native proof.

## Authority and Human Edit Wins

Postflight and promotion use separately supplied CurrentAuthorityFacts and distinct
observation references. The foundation never copies postflight facts into promotion
facts. Distinct references alone do not prove freshness: the runtime observation
producer is responsible for their truth and acquisition order.

Runtime ApplicationResultEvidence binds a supplied ApplicationRecord to transaction,
authorization, ActualDiff, post snapshot and identity correspondence evidence. It does
not create result IDs or increment timeline versions. After verified commit and fresh
promotion eligibility, existing RecordApplication, RecordVerification(True), and
PromoteCandidate transitions are evaluated. AI results never use ObserveHumanVersion.

FinalizationResult separates transaction outcome, transaction promotion eligibility,
Authority transition results, and `durable_promotion = NOT_PERFORMED`. Transaction
eligibility alone is insufficient when result correspondence or Authority checks fail.
Authority before/after values support a future conditional persistence port. Repeated
delivery to an already-promoted/stale Authority state does not reapply the events.
Returned in-memory transitions are not durable publication or exactly-once guarantees.

Human/base advance before admission rejects without READY. Same-reference UNKNOWN/FALSE
currentness also rejects. Fresh post-state mismatch prevents commit/promotion. A human
edit after verified commit blocks promotion while preserving the historical commit.
An accepted promoted historical candidate may remain APPLIED/VERIFIED/PROMOTED/STALE.
There is no rebase or repair to FRESH.

OPEN-002 production result identity and OPEN-008 persistence/concurrency remain open.
No database, compare-and-swap implementation, lock, lease, scheduler, native observer,
atomic snapshot, or observation-to-execution race guarantee is provided.

## Verification receipt

All test runtime/identity/capability facts are explicitly synthetic TEST_ONLY_SUPPORT
fixtures. VERIFIED enum literals in test port inputs are not native qualification.
VS-001C remains test-only, including its independent simulated ActualDiff producer.
No suffix-only/single-translation simulator restriction is added to production policy.

- Targeted orchestration: **49 passed**.
- Full pytest: **1482 passed, 2 skipped**.
- Skips: host symlink creation privilege; opt-in intentional red invariant test.
- Repository Ruff: **PASS**.
- Existing strict mypy configuration: **PASS, 34 source files**.
- Explicit strict mypy of the two new Python files: **PASS, 2 source files**.
- Tracked-file diff and whitespace checks: **PASS**.

Coverage includes all 20 requested cases: composition/ambiguity; Safety versus approval;
exact approval binding and artifact substitution; stale/currentness/IR/precommit rejection;
MATCH/MISMATCH/missing/unverified actual evidence; unknown execution and missing history;
post-execution human edits; historical commit preservation; result mismatch; no AI
ObserveHumanVersion path; missing separate promotion facts; no durable promotion claim.
Additional checks cover primary-media continuity, rollback/step correspondence,
resumed postflight artifact substitution, and repeated semantic promotion attempts.

Validation environment is outside the repository:
`C:\Users\c\source\repos\vs001e-validation-env` (Python 3.11, pytest 9.1.1,
Ruff 0.17.0, mypy 2.4.0, NumPy 2.3.5). Commands use this worktree's `src;tests`
on PYTHONPATH. Explicit two-file mypy also uses `MYPYPATH=src;tests` with
`--strict --follow-untyped-imports --explicit-package-bases`.

Next gate: review these three files and the pure port/artifact contracts. Runtime,
native readiness, persistence, commit and push require their separate authorization.
