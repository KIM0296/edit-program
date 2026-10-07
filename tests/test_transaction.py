from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.expected_diff import DiffVerificationStatus as D
from davinci_ai_editor.native_snapshot import ObservedValue as B
from davinci_ai_editor.safety_preflight import PreflightStatus, SafetyVerdict
from davinci_ai_editor.temporal_mapping import NativeSnapshotRef
from davinci_ai_editor.transaction import (
    ArtifactBinding,
    BaseVerificationEvidence,
    CurrentAuthorityFacts,
    ExecutionAuthorization,
    ExecutionStepResult,
    PostflightEvidence,
    PrecommitFacts,
    PrecommitStatus,
    PromotionEligibility,
    RollbackCommandReport,
    RollbackRequest,
    RollbackSettings,
    StepReconciliation,
    TransactionDefinition,
    TransactionEvent,
    TransactionJournal,
    automatic_rollback_eligible,
    derive_rollback_policy,
    prepare_transaction,
    promotion_eligibility,
    transition,
    validate_precommit,
)
from davinci_ai_editor.transaction import (
    ExecutionStepStatus as Step,
)
from davinci_ai_editor.transaction import (
    RollbackCapability as Cap,
)
from davinci_ai_editor.transaction import (
    RollbackPolicy as Policy,
)
from davinci_ai_editor.transaction import (
    TransactionEventKind as E,
)
from davinci_ai_editor.transaction import (
    TransactionOutcome as O,
)
from davinci_ai_editor.transaction import (
    TransactionPhase as P,
)

BASE = NativeSnapshotRef("main", 42, "base")
POST = NativeSnapshotRef("main", 43, "post")
BINDING = ArtifactBinding("diff", "safety", BASE)
AUTH = ExecutionAuthorization("authorization", "approval", BINDING)
DEF = TransactionDefinition(
    "tx",
    BINDING,
    AUTH,
    ("one", "two"),
    RollbackSettings(Cap.SUPPORTED_VERIFIED, Policy.AUTO_ELIGIBLE),
)
FACTS = PrecommitFacts(
    BINDING,
    "authorization",
    BASE,
    PreflightStatus.EVALUATED,
    SafetyVerdict.PASS,
    B.TRUE,
    B.TRUE,
    B.TRUE,
    B.TRUE,
    False,
)
CURRENT = CurrentAuthorityFacts(BINDING, "authorization", POST, B.TRUE, B.TRUE, False)


def event(tx, kind, payload=None):
    return TransactionEvent("tx", tx.journal.events[-1].sequence_no + 1, kind, payload)


def advance(tx, kind, payload=None):
    return transition(tx, event(tx, kind, payload))


def applying(facts=FACTS):
    tx = advance(prepare_transaction(DEF), E.PRECOMMIT_STARTED)
    return advance(tx, E.PRECOMMIT_PASSED, facts)


def step(tx, name, status=Step.SUCCEEDED, may_have_mutated=True):
    tx = advance(tx, E.STEP_STARTED, name)
    kind = {
        Step.SUCCEEDED: E.STEP_SUCCEEDED,
        Step.FAILED: E.STEP_FAILED,
        Step.OUTCOME_UNKNOWN: E.STEP_OUTCOME_UNKNOWN,
    }[status]
    return advance(tx, kind, ExecutionStepResult(name, status, name + "-report", may_have_mutated))


def postflight(status=D.MATCH, current=CURRENT):
    tx = step(step(applying(), "one"), "two")
    tx = advance(tx, E.POSTFLIGHT_STARTED)
    ev = PostflightEvidence("post-verification", BINDING, status, POST, current)
    kind = {
        D.MATCH: E.POSTFLIGHT_MATCHED,
        D.MISMATCH: E.POSTFLIGHT_MISMATCH,
        D.UNVERIFIED: E.POSTFLIGHT_UNVERIFIED,
        D.STALE: E.POSTFLIGHT_STALE,
    }[status]
    return advance(tx, kind, ev)


def committed():
    return advance(postflight(), E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)


def partial():
    return step(step(applying(), "one"), "two", Step.FAILED, False)


def rolled_back(tx, status=D.MATCH, command=Step.SUCCEEDED):
    tx = advance(tx, E.ROLLBACK_STARTED, RollbackRequest(True))
    tx = advance(tx, E.ROLLBACK_COMMAND_COMPLETED, RollbackCommandReport("undo-report", command))
    proof = BaseVerificationEvidence("base-verification", BINDING, status, POST, POST)
    return advance(tx, E.ROLLBACK_VERIFIED if status == D.MATCH else E.ROLLBACK_FAILED, proof)


def test_normal_path_and_commit_point():
    tx = prepare_transaction(DEF)
    assert tx.state.phase == P.PREPARED and tx.state.outcome == O.NONE
    tx = advance(tx, E.PRECOMMIT_STARTED)
    assert tx.state.phase == P.PRECOMMIT_VALIDATING
    tx = advance(tx, E.PRECOMMIT_PASSED, FACTS)
    assert tx.state.phase == P.APPLYING
    tx = step(step(tx, "one"), "two")
    assert tx.state.outcome == O.NONE
    tx = advance(tx, E.POSTFLIGHT_STARTED)
    assert tx.state.phase == P.POSTFLIGHT_VERIFYING
    tx = advance(
        tx, E.POSTFLIGHT_MATCHED, PostflightEvidence("verify", BINDING, D.MATCH, POST, CURRENT)
    )
    assert tx.state.outcome == O.NONE
    tx = advance(tx, E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)
    assert tx.state.phase == P.TERMINAL and tx.state.outcome == O.VERIFIED_COMMITTED
    assert promotion_eligibility(tx, CURRENT) == PromotionEligibility.ELIGIBLE
    assert tx.definition.binding.base_snapshot == BASE


def test_phase_outcome_separate_and_constructor_invariants():
    assert P is not O
    with pytest.raises(ValueError):
        replace(applying().state, outcome=O.VERIFIED_COMMITTED)
    with pytest.raises(ValueError):
        replace(committed().state, postflight=None)


@pytest.mark.parametrize(
    "tx",
    [
        prepare_transaction(DEF),
        applying(),
        step(applying(), "one"),
        step(step(applying(), "one"), "two"),
    ],
)
def test_no_direct_commit_or_skipped_postflight(tx):
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)


@pytest.mark.parametrize(
    "snapshot",
    [
        NativeSnapshotRef("other", 42, "base"),
        NativeSnapshotRef("main", 43, "base"),
        NativeSnapshotRef("main", 42, "changed"),
    ],
)
def test_precommit_stale(snapshot):
    facts = replace(FACTS, current_snapshot=snapshot)
    assert validate_precommit(DEF, facts).status == PrecommitStatus.STALE
    tx = advance(advance(prepare_transaction(DEF), E.PRECOMMIT_STARTED), E.PRECOMMIT_FAILED, facts)
    assert tx.state.outcome == O.ABORTED_STALE
    assert all(s.status == Step.NOT_STARTED and not s.may_have_mutated for s in tx.state.steps)
    with pytest.raises(ValueError):
        advance(tx, E.STEP_STARTED, "one")


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization_current", B.UNKNOWN),
        ("safety_current", B.UNKNOWN),
        ("targets_resolvable", B.FALSE),
        ("executor_ready", B.UNKNOWN),
        ("recovery_required", True),
        ("safety_verdict", SafetyVerdict.REJECT),
    ],
)
def test_before_mutation_failure(field, value):
    facts = replace(FACTS, **{field: value})
    tx = advance(advance(prepare_transaction(DEF), E.PRECOMMIT_STARTED), E.PRECOMMIT_FAILED, facts)
    assert tx.state.outcome == O.FAILED_BEFORE_MUTATION
    assert not any(s.may_have_mutated for s in tx.state.steps)


def test_precommit_must_be_truthfully_classified():
    tx = advance(prepare_transaction(DEF), E.PRECOMMIT_STARTED)
    with pytest.raises(ValueError):
        advance(tx, E.PRECOMMIT_FAILED, FACTS)
    with pytest.raises(ValueError):
        advance(tx, E.PRECOMMIT_PASSED, replace(FACTS, recovery_required=True))


def test_partial_failure_never_success_or_before_mutation():
    tx = partial()
    for outcome in (O.VERIFIED_COMMITTED, O.FAILED_BEFORE_MUTATION, O.ABORTED_STALE):
        with pytest.raises(ValueError):
            advance(tx, E.TRANSACTION_TERMINATED, outcome)
    failed = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_UNRECOVERED)
    assert failed.state.recovery_required and not failed.state.new_destructive_execution_eligible
    assert promotion_eligibility(failed, CURRENT) == PromotionEligibility.NOT_ELIGIBLE


def test_first_failure_explicitly_no_mutation():
    tx = step(applying(), "one", Step.FAILED, False)
    tx = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_BEFORE_MUTATION)
    assert not tx.state.recovery_required


def test_unknown_is_distinct_and_blocks_retry_or_success():
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    assert tx.state.steps[0].status == Step.OUTCOME_UNKNOWN
    assert not tx.state.retry_eligible
    assert not automatic_rollback_eligible(tx)
    for kind, payload in [
        (E.STEP_STARTED, "one"),
        (E.STEP_STARTED, "two"),
        (E.STEP_SUCCEEDED, ExecutionStepResult("one", Step.SUCCEEDED, "late-success", True)),
        (E.POSTFLIGHT_STARTED, None),
        (E.ROLLBACK_STARTED, RollbackRequest(True)),
    ]:
        with pytest.raises(ValueError):
            advance(tx, kind, payload)


def test_reconciliation_required_and_preserves_unknown_history():
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    report = ExecutionStepResult("one", Step.SUCCEEDED, "reconciled-report", True)
    proof = StepReconciliation(BINDING, "one-report", report, POST, POST, "reconcile-evidence")
    tx = advance(tx, E.RECONCILIATION_RECORDED, proof)
    assert tx.state.steps[0].status == Step.SUCCEEDED
    assert E.STEP_OUTCOME_UNKNOWN in [e.kind for e in tx.journal.events]
    assert tx.journal.events[-1].kind == E.RECONCILIATION_RECORDED
    tx = step(tx, "two")
    assert not tx.state.retry_eligible
    with pytest.raises(ValueError):
        advance(tx, E.STEP_STARTED, "one")


@pytest.mark.parametrize("status", [D.MISMATCH, D.UNVERIFIED, D.STALE])
def test_only_match_can_commit(status):
    tx = postflight(status)
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)
    outcome = (
        O.UNVERIFIED_APPLY if status in (D.UNVERIFIED, D.STALE) else O.FAILED_POSTFLIGHT_UNRECOVERED
    )
    tx = advance(tx, E.TRANSACTION_TERMINATED, outcome)
    assert promotion_eligibility(tx, CURRENT) == PromotionEligibility.NOT_ELIGIBLE
    assert not tx.state.new_destructive_execution_eligible
    if outcome == O.FAILED_POSTFLIGHT_UNRECOVERED:
        assert tx.state.recovery_required


def test_capability_policy_exact_vocab_and_defaults():
    assert {v.value for v in Cap} == {
        "SUPPORTED_VERIFIED",
        "SUPPORTED_UNVERIFIED",
        "UNSUPPORTED",
        "UNKNOWN",
    }
    assert {v.value for v in Policy} == {"AUTO_ELIGIBLE", "MANUAL_ONLY", "NOT_AVAILABLE"}
    assert derive_rollback_policy(Cap.SUPPORTED_VERIFIED) == Policy.AUTO_ELIGIBLE
    assert derive_rollback_policy(Cap.SUPPORTED_UNVERIFIED) == Policy.MANUAL_ONLY
    for cap in (Cap.UNKNOWN, Cap.UNSUPPORTED):
        assert derive_rollback_policy(cap) == Policy.NOT_AVAILABLE


@pytest.mark.parametrize("cap", [Cap.SUPPORTED_UNVERIFIED, Cap.UNKNOWN, Cap.UNSUPPORTED])
def test_auto_requires_verified_capability(cap):
    with pytest.raises(ValueError):
        RollbackSettings(cap, Policy.AUTO_ELIGIBLE)


def test_policy_may_be_stricter_and_auto_not_execution():
    assert (
        RollbackSettings(Cap.SUPPORTED_VERIFIED, Policy.NOT_AVAILABLE).policy
        == Policy.NOT_AVAILABLE
    )
    assert automatic_rollback_eligible(partial())
    assert partial().state.phase == P.APPLYING


def test_command_success_is_not_recovery():
    tx = advance(partial(), E.ROLLBACK_STARTED, RollbackRequest(True))
    tx = advance(tx, E.ROLLBACK_COMMAND_COMPLETED, RollbackCommandReport("undo", Step.SUCCEEDED))
    assert tx.state.phase == P.ROLLING_BACK
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_RECOVERED)


@pytest.mark.parametrize(
    "factory,recovered",
    [
        (partial, O.FAILED_PARTIAL_RECOVERED),
        (lambda: postflight(D.MISMATCH), O.FAILED_POSTFLIGHT_RECOVERED),
    ],
)
def test_verified_recovery_remains_failed_edit(factory, recovered):
    tx = rolled_back(factory())
    tx = advance(tx, E.TRANSACTION_TERMINATED, recovered)
    assert tx.state.outcome == recovered and not tx.state.recovery_required
    assert promotion_eligibility(tx, CURRENT) == PromotionEligibility.NOT_ELIGIBLE
    kinds = [e.kind for e in tx.journal.events]
    assert E.ROLLBACK_VERIFIED in kinds and (
        E.STEP_FAILED in kinds or E.POSTFLIGHT_MISMATCH in kinds
    )
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)


@pytest.mark.parametrize("status", [D.MISMATCH, D.UNVERIFIED, D.STALE])
def test_rollback_nonmatch_unrecovered(status):
    tx = advance(
        rolled_back(partial(), status), E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_UNRECOVERED
    )
    assert tx.state.recovery_required and not tx.state.new_destructive_execution_eligible


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization_ref", "other"),
        ("authorization_current", B.FALSE),
        ("safety_pass_current", B.FALSE),
        ("recovery_required", True),
        ("current_snapshot", NativeSnapshotRef("main", 44, "human")),
        ("binding", replace(BINDING, safety_result_ref="other")),
    ],
)
def test_promotion_every_current_prerequisite(field, value):
    assert (
        promotion_eligibility(committed(), replace(CURRENT, **{field: value}))
        == PromotionEligibility.NOT_ELIGIBLE
    )


@pytest.mark.parametrize(
    "binding",
    [
        replace(BINDING, expected_diff_ref="other"),
        replace(BINDING, safety_result_ref="other"),
        replace(BINDING, base_snapshot=POST),
    ],
)
def test_authorization_artifacts_cannot_be_reused(binding):
    definition = replace(DEF, authorization=replace(AUTH, binding=binding))
    assert validate_precommit(definition, FACTS).status != PrecommitStatus.READY
    assert validate_precommit(DEF, replace(FACTS, binding=binding)).status != PrecommitStatus.READY


def test_journal_monotonic_append_and_defensive_copy():
    tx = prepare_transaction(DEF)
    events = list(tx.journal.events)
    journal = TransactionJournal(events)
    events.clear()
    assert journal == tx.journal
    next_event = TransactionEvent("tx", 10, E.PRECOMMIT_STARTED)
    next_tx = transition(tx, next_event)
    assert len(tx.journal.events) == 1 and len(next_tx.journal.events) == 2
    assert next_tx.journal.events[-1].sequence_no == 10
    for seq in (10, 9):
        with pytest.raises(ValueError):
            transition(next_tx, TransactionEvent("tx", seq, E.PRECOMMIT_PASSED, FACTS))
    with pytest.raises(ValueError):
        TransactionJournal(tuple(reversed(next_tx.journal.events)))


def test_immutable_deterministic_states():
    tx = committed()
    assert committed() == tx and tx.state == tx.state
    for value in (
        AUTH,
        BINDING,
        DEF,
        FACTS,
        CURRENT,
        tx,
        tx.state,
        tx.journal,
        tx.journal.events[0],
        tx.state.steps[0],
        tx.state.postflight,
    ):
        with pytest.raises(FrozenInstanceError):
            value.changed = True


def test_no_existing_layer_execution(monkeypatch):
    from davinci_ai_editor import (
        authority,
        expected_diff,
        native_snapshot,
        safety,
        safety_preflight,
        temporal_mapping,
    )
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        pytest.fail("unexpected external execution")

    for module, name in [
        (expected_diff, "compile_expected_diff"),
        (expected_diff, "verify_diff"),
        (native_snapshot, "evaluate_readiness"),
        (temporal_mapping, "map_range"),
        (safety, "preflight"),
        (safety_preflight, "preflight"),
        (authority, "transition"),
        (FakeTimeline, "apply"),
    ]:
        monkeypatch.setattr(module, name, forbidden)
    assert promotion_eligibility(committed(), CURRENT) == PromotionEligibility.ELIGIBLE


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization", replace(AUTH, approval_ref="different-approval")),
        ("authorization", replace(AUTH, authorization_ref="different-authorization")),
        ("rollback", RollbackSettings(Cap.UNKNOWN, Policy.NOT_AVAILABLE)),
        ("step_refs", ("two", "one")),
        ("binding", replace(BINDING, expected_diff_ref="other")),
    ],
)
def test_prepared_history_binds_exact_artifacts(field, value):
    tx = applying()
    with pytest.raises(ValueError):
        replace(tx, definition=replace(DEF, **{field: value}))


def test_exact_phase_outcome_step_vocabularies():
    assert {x.value for x in P} == {
        "PREPARED",
        "PRECOMMIT_VALIDATING",
        "APPLYING",
        "POSTFLIGHT_VERIFYING",
        "ROLLING_BACK",
        "TERMINAL",
    }
    assert {x.value for x in O} == {
        "NONE",
        "VERIFIED_COMMITTED",
        "ABORTED_STALE",
        "FAILED_BEFORE_MUTATION",
        "FAILED_PARTIAL_RECOVERED",
        "FAILED_PARTIAL_UNRECOVERED",
        "FAILED_POSTFLIGHT_RECOVERED",
        "FAILED_POSTFLIGHT_UNRECOVERED",
        "UNVERIFIED_APPLY",
    }
    assert {x.value for x in Step} == {"NOT_STARTED", "SUCCEEDED", "FAILED", "OUTCOME_UNKNOWN"}


@pytest.mark.parametrize(
    "kind,payload",
    [
        (E.STEP_STARTED, "one"),
        (E.POSTFLIGHT_STARTED, None),
        (E.ROLLBACK_STARTED, RollbackRequest(True)),
        (E.PRECOMMIT_PASSED, FACTS),
    ],
)
def test_prepared_cannot_skip_validation(kind, payload):
    with pytest.raises(ValueError):
        advance(prepare_transaction(DEF), kind, payload)


def test_step_order_single_active_and_report_kind_enforced():
    tx = applying()
    with pytest.raises(ValueError):
        advance(tx, E.STEP_STARTED, "two")
    with pytest.raises(ValueError):
        advance(tx, E.STEP_SUCCEEDED, ExecutionStepResult("one", Step.SUCCEEDED, "r", True))
    active = advance(tx, E.STEP_STARTED, "one")
    with pytest.raises(ValueError):
        advance(active, E.STEP_STARTED, "two")
    with pytest.raises(ValueError):
        advance(active, E.STEP_SUCCEEDED, ExecutionStepResult("one", Step.FAILED, "r", False))
    with pytest.raises(ValueError):
        advance(active, E.TRANSACTION_TERMINATED, O.FAILED_BEFORE_MUTATION)
    with pytest.raises(ValueError):
        advance(active, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_UNRECOVERED)


def test_unknown_can_only_terminate_unrecovered_without_reconciliation():
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    for outcome in (O.FAILED_BEFORE_MUTATION, O.FAILED_PARTIAL_RECOVERED, O.VERIFIED_COMMITTED):
        with pytest.raises(ValueError):
            advance(tx, E.TRANSACTION_TERMINATED, outcome)
    done = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_UNRECOVERED)
    assert done.state.recovery_required
    assert done.state.steps[0].status == Step.OUTCOME_UNKNOWN


@pytest.mark.parametrize(
    "field,value",
    [
        ("binding", replace(BINDING, expected_diff_ref="other")),
        ("unknown_report_ref", "other-report"),
        ("current_snapshot", NativeSnapshotRef("main", 44, "human")),
        ("classification", ExecutionStepResult("two", Step.SUCCEEDED, "r", True)),
    ],
)
def test_reconciliation_requires_exact_command_and_fresh_binding(field, value):
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    report = ExecutionStepResult("one", Step.SUCCEEDED, "reconciled", True)
    evidence = StepReconciliation(BINDING, "one-report", report, POST, POST, "evidence")
    with pytest.raises(ValueError):
        advance(tx, E.RECONCILIATION_RECORDED, replace(evidence, **{field: value}))


def test_reconciled_no_mutation_failure_still_cannot_retry():
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    evidence = StepReconciliation(
        BINDING,
        "one-report",
        ExecutionStepResult("one", Step.FAILED, "observed-not-applied", False),
        POST,
        POST,
        "reconciliation",
    )
    tx = advance(tx, E.RECONCILIATION_RECORDED, evidence)
    assert not tx.state.retry_eligible
    with pytest.raises(ValueError):
        advance(tx, E.STEP_STARTED, "one")
    tx = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_BEFORE_MUTATION)
    assert tx.state.outcome == O.FAILED_BEFORE_MUTATION
    assert E.STEP_OUTCOME_UNKNOWN in [e.kind for e in tx.journal.events]


def test_reconciled_partial_failure_allows_explicit_recovery_only():
    tx = step(applying(), "one", Step.OUTCOME_UNKNOWN)
    proof = StepReconciliation(
        BINDING,
        "one-report",
        ExecutionStepResult("one", Step.FAILED, "observed-partial", True),
        POST,
        POST,
        "evidence",
    )
    tx = advance(tx, E.RECONCILIATION_RECORDED, proof)
    assert automatic_rollback_eligible(tx)
    recovered = advance(rolled_back(tx), E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_RECOVERED)
    assert recovered.state.outcome == O.FAILED_PARTIAL_RECOVERED


@pytest.mark.parametrize(
    "current",
    [
        replace(CURRENT, authorization_current=B.FALSE),
        replace(CURRENT, safety_pass_current=B.UNKNOWN),
        replace(CURRENT, recovery_required=True),
        replace(CURRENT, authorization_ref="other"),
        replace(CURRENT, binding=replace(BINDING, safety_result_ref="other")),
    ],
)
def test_match_without_current_authorization_or_safety_does_not_commit(current):
    tx = postflight(D.MATCH, current)
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.VERIFIED_COMMITTED)
    assert not automatic_rollback_eligible(tx)
    tx = advance(tx, E.TRANSACTION_TERMINATED, O.UNVERIFIED_APPLY)
    assert promotion_eligibility(tx, CURRENT) == PromotionEligibility.NOT_ELIGIBLE


def test_postflight_report_binding_and_freshness():
    tx = advance(step(step(applying(), "one"), "two"), E.POSTFLIGHT_STARTED)
    good = PostflightEvidence("p", BINDING, D.MATCH, POST, CURRENT)
    for bad in (
        replace(good, binding=replace(BINDING, expected_diff_ref="other")),
        replace(good, observed_snapshot=BASE),
        replace(good, status=D.MISMATCH),
    ):
        with pytest.raises(ValueError):
            advance(tx, E.POSTFLIGHT_MATCHED, bad)
    once = advance(tx, E.POSTFLIGHT_MATCHED, good)
    with pytest.raises(ValueError):
        advance(once, E.POSTFLIGHT_MATCHED, good)


@pytest.mark.parametrize(
    "cap,policy,auto_ok,manual_ok",
    [
        (Cap.SUPPORTED_VERIFIED, Policy.AUTO_ELIGIBLE, True, True),
        (Cap.SUPPORTED_VERIFIED, Policy.MANUAL_ONLY, False, True),
        (Cap.SUPPORTED_VERIFIED, Policy.NOT_AVAILABLE, False, False),
        (Cap.SUPPORTED_UNVERIFIED, Policy.MANUAL_ONLY, False, True),
        (Cap.UNKNOWN, Policy.NOT_AVAILABLE, False, False),
        (Cap.UNSUPPORTED, Policy.NOT_AVAILABLE, False, False),
    ],
)
def test_rollback_request_policy_matrix(cap, policy, auto_ok, manual_ok):
    definition = replace(DEF, rollback=RollbackSettings(cap, policy))
    tx = advance(prepare_transaction(definition), E.PRECOMMIT_STARTED)
    tx = advance(tx, E.PRECOMMIT_PASSED, FACTS)
    tx = step(step(tx, "one"), "two", Step.FAILED, False)
    assert automatic_rollback_eligible(tx) == auto_ok
    for automatic, allowed in ((True, auto_ok), (False, manual_ok)):
        if allowed:
            assert (
                advance(tx, E.ROLLBACK_STARTED, RollbackRequest(automatic)).state.phase
                == P.ROLLING_BACK
            )
        else:
            with pytest.raises(ValueError):
                advance(tx, E.ROLLBACK_STARTED, RollbackRequest(automatic))


@pytest.mark.parametrize("cap", [Cap.UNKNOWN, Cap.UNSUPPORTED])
def test_unsupported_capability_cannot_be_upgraded_to_manual(cap):
    with pytest.raises(ValueError):
        RollbackSettings(cap, Policy.MANUAL_ONLY)


def test_base_verification_requires_attempt_report_and_fresh_exact_binding():
    proof = BaseVerificationEvidence("v", BINDING, D.MATCH, POST, POST)
    tx = advance(partial(), E.ROLLBACK_STARTED, RollbackRequest(True))
    with pytest.raises(ValueError):
        advance(tx, E.ROLLBACK_VERIFIED, proof)
    tx = advance(tx, E.ROLLBACK_COMMAND_COMPLETED, RollbackCommandReport("undo", Step.SUCCEEDED))
    for bad in (
        replace(proof, binding=replace(BINDING, base_snapshot=POST)),
        replace(proof, current_snapshot=BASE),
        replace(proof, status=D.MISMATCH),
    ):
        with pytest.raises(ValueError):
            advance(tx, E.ROLLBACK_VERIFIED, bad)
    once = advance(tx, E.ROLLBACK_VERIFIED, proof)
    with pytest.raises(ValueError):
        advance(once, E.ROLLBACK_FAILED, replace(proof, status=D.MISMATCH))


@pytest.mark.parametrize("report", [Step.SUCCEEDED, Step.FAILED, Step.OUTCOME_UNKNOWN])
def test_rollback_response_alone_never_recovery(report):
    tx = advance(partial(), E.ROLLBACK_STARTED, RollbackRequest(True))
    tx = advance(tx, E.ROLLBACK_COMMAND_COMPLETED, RollbackCommandReport("undo", report))
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_RECOVERED)
    proof = BaseVerificationEvidence("fresh-base-equality", BINDING, D.MATCH, POST, POST)
    tx = advance(tx, E.ROLLBACK_VERIFIED, proof)
    tx = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_RECOVERED)
    assert tx.state.rollback_report.status == report
    assert tx.state.outcome != O.VERIFIED_COMMITTED


def test_failure_origin_cannot_be_rewritten_after_recovery():
    tx = rolled_back(partial())
    with pytest.raises(ValueError):
        advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_POSTFLIGHT_RECOVERED)
    tx = rolled_back(postflight(D.MISMATCH), D.MISMATCH)
    done = advance(tx, E.TRANSACTION_TERMINATED, O.FAILED_POSTFLIGHT_UNRECOVERED)
    assert done.state.recovery_required


def test_terminal_history_and_recovery_lockdown_cannot_be_acknowledged_away():
    tx = advance(partial(), E.TRANSACTION_TERMINATED, O.FAILED_PARTIAL_UNRECOVERED)
    with pytest.raises(ValueError):
        advance(tx, E.PRECOMMIT_STARTED)
    with pytest.raises(TypeError):
        replace(tx.state, recovery_required=False)
    facts = replace(FACTS, recovery_required=tx.state.recovery_required)
    assert validate_precommit(DEF, facts).status == PrecommitStatus.BLOCKED


@pytest.mark.parametrize("sequence", [0, -1, True, 1.0])
def test_journal_sequences_are_explicit_positive_integers(sequence):
    with pytest.raises(ValueError):
        prepare_transaction(DEF, sequence)


def test_journal_payload_and_transaction_identity_validation():
    tx = prepare_transaction(DEF)
    with pytest.raises(TypeError):
        TransactionEvent("tx", 2, E.STEP_SUCCEEDED, True)
    with pytest.raises(ValueError):
        transition(tx, TransactionEvent("other", 2, E.PRECOMMIT_STARTED))
    with pytest.raises(ValueError):
        replace(tx, journal=TransactionJournal(()))
    with pytest.raises(ValueError):
        TransactionJournal((tx.journal.events[0], tx.journal.events[0]))


def test_unknown_and_success_cannot_claim_no_possible_mutation():
    for status in (Step.SUCCEEDED, Step.OUTCOME_UNKNOWN):
        with pytest.raises(ValueError):
            ExecutionStepResult("one", status, "r", False)
    with pytest.raises(ValueError):
        ExecutionStepResult("one", Step.NOT_STARTED, "r", False)
    with pytest.raises(ValueError):
        ExecutionStepResult("one", Step.FAILED, None, False)


def test_no_bool_or_enum_coercion():
    with pytest.raises(TypeError):
        replace(FACTS, authorization_current=True)
    with pytest.raises(TypeError):
        replace(FACTS, recovery_required=1)
    with pytest.raises(TypeError):
        ExecutionStepResult("one", "SUCCEEDED", "r", True)
    with pytest.raises(TypeError):
        replace(applying().state, phase=O.NONE)


def test_contract_versions_and_safety_ref_fail_closed():
    assert (
        validate_precommit(replace(DEF, contract_version="v2"), FACTS).status
        == PrecommitStatus.BLOCKED
    )
    assert (
        validate_precommit(
            replace(DEF, authorization=replace(AUTH, contract_version="v2")), FACTS
        ).status
        == PrecommitStatus.BLOCKED
    )
    result = validate_precommit(
        DEF, replace(FACTS, binding=replace(BINDING, safety_result_ref="other"))
    )
    assert result.status == PrecommitStatus.BLOCKED
    with pytest.raises(ValueError):
        replace(result, status=PrecommitStatus.READY)


def test_precommit_stale_dominates_lockdown_but_preserves_reasons():
    facts = replace(FACTS, current_snapshot=POST, recovery_required=True, executor_ready=B.FALSE)
    r = validate_precommit(DEF, facts)
    assert r.status == PrecommitStatus.STALE and len(r.reasons) >= 3


def test_prepared_steps_and_events_are_defensive_copies():
    refs = ["one", "two"]
    definition = replace(DEF, step_refs=refs)
    refs.clear()
    assert definition.step_refs == ("one", "two")
    tx = prepare_transaction(definition)
    steps = list(tx.state.steps)
    state = replace(tx.state, steps=steps)
    steps.clear()
    assert len(state.steps) == 2
    for value in (
        StepReconciliation(
            BINDING, "r", ExecutionStepResult("one", Step.FAILED, "proof", False), POST, POST, "ev"
        ),
        RollbackRequest(False),
        RollbackCommandReport("r", Step.OUTCOME_UNKNOWN),
        BaseVerificationEvidence("r", BINDING, D.MATCH, POST, POST),
        validate_precommit(DEF, FACTS),
    ):
        with pytest.raises(FrozenInstanceError):
            value.changed = True


def test_state_constructor_rejects_execution_evidence_in_prepared_phase():
    with pytest.raises(ValueError):
        replace(applying().state, phase=P.PREPARED)
    with pytest.raises(ValueError):
        replace(applying().state, phase=P.POSTFLIGHT_VERIFYING)
    with pytest.raises(ValueError):
        replace(applying().state, phase=P.ROLLING_BACK)


def test_no_runtime_imports_or_native_commands():
    import ast
    from pathlib import Path

    from davinci_ai_editor import transaction

    tree = ast.parse(Path(transaction.__file__).read_text(encoding="utf-8-sig"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {
        "dataclasses",
        "enum",
        "itertools",
        "typing",
        "expected_diff",
        "native_snapshot",
        "safety_preflight",
        "temporal_mapping",
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    assert not hasattr(DEF, "commands")
