from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.expected_diff import DiffVerificationStatus as D
from davinci_ai_editor.native_snapshot import ObservedValue as B
from davinci_ai_editor.safety_preflight import PreflightStatus, SafetyVerdict
from davinci_ai_editor.temporal_mapping import NativeSnapshotRef
from davinci_ai_editor.transaction import (
    ArtifactBinding, BaseVerificationEvidence, CurrentAuthorityFacts, ExecutionAuthorization,
    ExecutionStepResult, ExecutionStepStatus as Step, PostflightEvidence, PrecommitFacts,
    PrecommitStatus, PromotionEligibility, RollbackCapability as Cap, RollbackCommandReport,
    RollbackPolicy as Policy, RollbackRequest, RollbackSettings, StepReconciliation,
    TransactionDefinition, TransactionEvent, TransactionEventKind as E, TransactionJournal,
    TransactionOutcome as O, TransactionPhase as P, automatic_rollback_eligible,
    derive_rollback_policy, prepare_transaction, promotion_eligibility, transition,
    validate_precommit,
)

BASE=NativeSnapshotRef('main',42,'base')
POST=NativeSnapshotRef('main',43,'post')
BINDING=ArtifactBinding('diff','safety',BASE)
AUTH=ExecutionAuthorization('authorization','approval',BINDING)
DEF=TransactionDefinition('tx',BINDING,AUTH,('one','two'),RollbackSettings(Cap.SUPPORTED_VERIFIED,Policy.AUTO_ELIGIBLE))
FACTS=PrecommitFacts(BINDING,'authorization',BASE,PreflightStatus.EVALUATED,SafetyVerdict.PASS,
                   B.TRUE,B.TRUE,B.TRUE,B.TRUE,False)
CURRENT=CurrentAuthorityFacts(BINDING,'authorization',POST,B.TRUE,B.TRUE,False)


def event(tx,kind,payload=None):
    return TransactionEvent('tx',tx.journal.events[-1].sequence_no+1,kind,payload)


def advance(tx,kind,payload=None):
    return transition(tx,event(tx,kind,payload))


def applying(facts=FACTS):
    tx=advance(prepare_transaction(DEF),E.PRECOMMIT_STARTED)
    return advance(tx,E.PRECOMMIT_PASSED,facts)


def step(tx,name,status=Step.SUCCEEDED,may_have_mutated=True):
    tx=advance(tx,E.STEP_STARTED,name)
    kind={Step.SUCCEEDED:E.STEP_SUCCEEDED,Step.FAILED:E.STEP_FAILED,Step.OUTCOME_UNKNOWN:E.STEP_OUTCOME_UNKNOWN}[status]
    return advance(tx,kind,ExecutionStepResult(name,status,name+'-report',may_have_mutated))


def postflight(status=D.MATCH,current=CURRENT):
    tx=step(step(applying(),'one'),'two')
    tx=advance(tx,E.POSTFLIGHT_STARTED)
    ev=PostflightEvidence('post-verification',BINDING,status,POST,current)
    kind={D.MATCH:E.POSTFLIGHT_MATCHED,D.MISMATCH:E.POSTFLIGHT_MISMATCH,
          D.UNVERIFIED:E.POSTFLIGHT_UNVERIFIED,D.STALE:E.POSTFLIGHT_STALE}[status]
    return advance(tx,kind,ev)


def committed():
    return advance(postflight(),E.TRANSACTION_TERMINATED,O.VERIFIED_COMMITTED)


def partial():
    return step(step(applying(),'one'),'two',Step.FAILED,False)


def rolled_back(tx,status=D.MATCH,command=Step.SUCCEEDED):
    tx=advance(tx,E.ROLLBACK_STARTED,RollbackRequest(True))
    tx=advance(tx,E.ROLLBACK_COMMAND_COMPLETED,RollbackCommandReport('undo-report',command))
    proof=BaseVerificationEvidence('base-verification',BINDING,status,POST,POST)
    return advance(tx,E.ROLLBACK_VERIFIED if status==D.MATCH else E.ROLLBACK_FAILED,proof)


def test_normal_path_and_commit_point():
    tx=prepare_transaction(DEF)
    assert tx.state.phase==P.PREPARED and tx.state.outcome==O.NONE
    tx=advance(tx,E.PRECOMMIT_STARTED)
    assert tx.state.phase==P.PRECOMMIT_VALIDATING
    tx=advance(tx,E.PRECOMMIT_PASSED,FACTS)
    assert tx.state.phase==P.APPLYING
    tx=step(step(tx,'one'),'two')
    assert tx.state.outcome==O.NONE
    tx=advance(tx,E.POSTFLIGHT_STARTED)
    assert tx.state.phase==P.POSTFLIGHT_VERIFYING
    tx=advance(tx,E.POSTFLIGHT_MATCHED,PostflightEvidence('verify',BINDING,D.MATCH,POST,CURRENT))
    assert tx.state.outcome==O.NONE
    tx=advance(tx,E.TRANSACTION_TERMINATED,O.VERIFIED_COMMITTED)
    assert tx.state.phase==P.TERMINAL and tx.state.outcome==O.VERIFIED_COMMITTED
    assert promotion_eligibility(tx,CURRENT)==PromotionEligibility.ELIGIBLE
    assert tx.definition.binding.base_snapshot==BASE


def test_phase_outcome_separate_and_constructor_invariants():
    assert P is not O
    with pytest.raises(ValueError):
        replace(applying().state,outcome=O.VERIFIED_COMMITTED)
    with pytest.raises(ValueError):
        replace(committed().state,postflight=None)


@pytest.mark.parametrize('tx',[prepare_transaction(DEF),applying(),step(applying(),'one'),
    step(step(applying(),'one'),'two')])
def test_no_direct_commit_or_skipped_postflight(tx):
    with pytest.raises(ValueError):
        advance(tx,E.TRANSACTION_TERMINATED,O.VERIFIED_COMMITTED)


@pytest.mark.parametrize('snapshot',[NativeSnapshotRef('other',42,'base'),NativeSnapshotRef('main',43,'base'),NativeSnapshotRef('main',42,'changed')])
def test_precommit_stale(snapshot):
    facts=replace(FACTS,current_snapshot=snapshot)
    assert validate_precommit(DEF,facts).status==PrecommitStatus.STALE
    tx=advance(advance(prepare_transaction(DEF),E.PRECOMMIT_STARTED),E.PRECOMMIT_FAILED,facts)
    assert tx.state.outcome==O.ABORTED_STALE
    assert all(s.status==Step.NOT_STARTED and not s.may_have_mutated for s in tx.state.steps)
    with pytest.raises(ValueError):
        advance(tx,E.STEP_STARTED,'one')


@pytest.mark.parametrize('field,value',[('authorization_current',B.UNKNOWN),('safety_current',B.UNKNOWN),
    ('targets_resolvable',B.FALSE),('executor_ready',B.UNKNOWN),('recovery_required',True),
    ('safety_verdict',SafetyVerdict.REJECT)])
def test_before_mutation_failure(field,value):
    facts=replace(FACTS,**{field:value})
    tx=advance(advance(prepare_transaction(DEF),E.PRECOMMIT_STARTED),E.PRECOMMIT_FAILED,facts)
    assert tx.state.outcome==O.FAILED_BEFORE_MUTATION
    assert not any(s.may_have_mutated for s in tx.state.steps)


def test_precommit_must_be_truthfully_classified():
    tx=advance(prepare_transaction(DEF),E.PRECOMMIT_STARTED)
    with pytest.raises(ValueError):
        advance(tx,E.PRECOMMIT_FAILED,FACTS)
    with pytest.raises(ValueError):
        advance(tx,E.PRECOMMIT_PASSED,replace(FACTS,recovery_required=True))


def test_partial_failure_never_success_or_before_mutation():
    tx=partial()
    for outcome in (O.VERIFIED_COMMITTED,O.FAILED_BEFORE_MUTATION,O.ABORTED_STALE):
        with pytest.raises(ValueError):
            advance(tx,E.TRANSACTION_TERMINATED,outcome)
    failed=advance(tx,E.TRANSACTION_TERMINATED,O.FAILED_PARTIAL_UNRECOVERED)
    assert failed.state.recovery_required and not failed.state.new_destructive_execution_eligible
    assert promotion_eligibility(failed,CURRENT)==PromotionEligibility.NOT_ELIGIBLE


def test_first_failure_explicitly_no_mutation():
    tx=step(applying(),'one',Step.FAILED,False)
    tx=advance(tx,E.TRANSACTION_TERMINATED,O.FAILED_BEFORE_MUTATION)
    assert not tx.state.recovery_required


def test_unknown_is_distinct_and_blocks_retry_or_success():
    tx=step(applying(),'one',Step.OUTCOME_UNKNOWN)
    assert tx.state.steps[0].status==Step.OUTCOME_UNKNOWN
    assert not tx.state.retry_eligible
    assert not automatic_rollback_eligible(tx)
    for kind,payload in [(E.STEP_STARTED,'one'),(E.STEP_STARTED,'two'),
        (E.STEP_SUCCEEDED,ExecutionStepResult('one',Step.SUCCEEDED,'late-success',True)),
        (E.POSTFLIGHT_STARTED,None),(E.ROLLBACK_STARTED,RollbackRequest(True))]:
        with pytest.raises(ValueError):
            advance(tx,kind,payload)


def test_reconciliation_required_and_preserves_unknown_history():
    tx=step(applying(),'one',Step.OUTCOME_UNKNOWN)
    report=ExecutionStepResult('one',Step.SUCCEEDED,'reconciled-report',True)
    proof=StepReconciliation(BINDING,'one-report',report,POST,POST,'reconcile-evidence')
    tx=advance(tx,E.RECONCILIATION_RECORDED,proof)
    assert tx.state.steps[0].status==Step.SUCCEEDED
    assert E.STEP_OUTCOME_UNKNOWN in [e.kind for e in tx.journal.events]
    assert tx.journal.events[-1].kind==E.RECONCILIATION_RECORDED
    tx=step(tx,'two')
    assert not tx.state.retry_eligible
    with pytest.raises(ValueError):
        advance(tx,E.STEP_STARTED,'one')


@pytest.mark.parametrize('status',[D.MISMATCH,D.UNVERIFIED,D.STALE])
def test_only_match_can_commit(status):
    tx=postflight(status)
    with pytest.raises(ValueError):
        advance(tx,E.TRANSACTION_TERMINATED,O.VERIFIED_COMMITTED)
    outcome=O.UNVERIFIED_APPLY if status in (D.UNVERIFIED,D.STALE) else O.FAILED_POSTFLIGHT_UNRECOVERED
    tx=advance(tx,E.TRANSACTION_TERMINATED,outcome)
    assert promotion_eligibility(tx,CURRENT)==PromotionEligibility.NOT_ELIGIBLE
    assert not tx.state.new_destructive_execution_eligible
    if outcome==O.FAILED_POSTFLIGHT_UNRECOVERED:
        assert tx.state.recovery_required


def test_capability_policy_exact_vocab_and_defaults():
    assert {v.value for v in Cap}=={'SUPPORTED_VERIFIED','SUPPORTED_UNVERIFIED','UNSUPPORTED','UNKNOWN'}
    assert {v.value for v in Policy}=={'AUTO_ELIGIBLE','MANUAL_ONLY','NOT_AVAILABLE'}
    assert derive_rollback_policy(Cap.SUPPORTED_VERIFIED)==Policy.AUTO_ELIGIBLE
    assert derive_rollback_policy(Cap.SUPPORTED_UNVERIFIED)==Policy.MANUAL_ONLY
    for cap in (Cap.UNKNOWN,Cap.UNSUPPORTED):
        assert derive_rollback_policy(cap)==Policy.NOT_AVAILABLE


@pytest.mark.parametrize('cap',[Cap.SUPPORTED_UNVERIFIED,Cap.UNKNOWN,Cap.UNSUPPORTED])
def test_auto_requires_verified_capability(cap):
    with pytest.raises(ValueError):
        RollbackSettings(cap,Policy.AUTO_ELIGIBLE)


def test_policy_may_be_stricter_and_auto_not_execution():
    assert RollbackSettings(Cap.SUPPORTED_VERIFIED,Policy.NOT_AVAILABLE).policy==Policy.NOT_AVAILABLE
    assert automatic_rollback_eligible(partial())
    assert partial().state.phase==P.APPLYING


def test_command_success_is_not_recovery():
    tx=advance(partial(),E.ROLLBACK_STARTED,RollbackRequest(True))
    tx=advance(tx,E.ROLLBACK_COMMAND_COMPLETED,RollbackCommandReport('undo',Step.SUCCEEDED))
    assert tx.state.phase==P.ROLLING_BACK
    with pytest.raises(ValueError):
        advance(tx,E.TRANSACTION_TERMINATED,O.FAILED_PARTIAL_RECOVERED)


@pytest.mark.parametrize('factory,recovered',[(partial,O.FAILED_PARTIAL_RECOVERED),
    (lambda:postflight(D.MISMATCH),O.FAILED_POSTFLIGHT_RECOVERED)])
def test_verified_recovery_remains_failed_edit(factory,recovered):
    tx=rolled_back(factory())
    tx=advance(tx,E.TRANSACTION_TERMINATED,recovered)
    assert tx.state.outcome==recovered and not tx.state.recovery_required
    assert promotion_eligibility(tx,CURRENT)==PromotionEligibility.NOT_ELIGIBLE
    kinds=[e.kind for e in tx.journal.events]
    assert E.ROLLBACK_VERIFIED in kinds and (E.STEP_FAILED in kinds or E.POSTFLIGHT_MISMATCH in kinds)
    with pytest.raises(ValueError):
        advance(tx,E.TRANSACTION_TERMINATED,O.VERIFIED_COMMITTED)


@pytest.mark.parametrize('status',[D.MISMATCH,D.UNVERIFIED,D.STALE])
def test_rollback_nonmatch_unrecovered(status):
    tx=advance(rolled_back(partial(),status),E.TRANSACTION_TERMINATED,O.FAILED_PARTIAL_UNRECOVERED)
    assert tx.state.recovery_required and not tx.state.new_destructive_execution_eligible


@pytest.mark.parametrize('field,value',[('authorization_ref','other'),('authorization_current',B.FALSE),
    ('safety_pass_current',B.FALSE),('recovery_required',True),
    ('current_snapshot',NativeSnapshotRef('main',44,'human')),
    ('binding',replace(BINDING,safety_result_ref='other'))])
def test_promotion_every_current_prerequisite(field,value):
    assert promotion_eligibility(committed(),replace(CURRENT,**{field:value}))==PromotionEligibility.NOT_ELIGIBLE


@pytest.mark.parametrize('binding',[replace(BINDING,expected_diff_ref='other'),
    replace(BINDING,safety_result_ref='other'),replace(BINDING,base_snapshot=POST)])
def test_authorization_artifacts_cannot_be_reused(binding):
    definition=replace(DEF,authorization=replace(AUTH,binding=binding))
    assert validate_precommit(definition,FACTS).status!=PrecommitStatus.READY
    assert validate_precommit(DEF,replace(FACTS,binding=binding)).status!=PrecommitStatus.READY


def test_journal_monotonic_append_and_defensive_copy():
    tx=prepare_transaction(DEF)
    events=list(tx.journal.events); journal=TransactionJournal(events); events.clear()
    assert journal==tx.journal
    next_event=TransactionEvent('tx',10,E.PRECOMMIT_STARTED)
    next_tx=transition(tx,next_event)
    assert len(tx.journal.events)==1 and len(next_tx.journal.events)==2
    assert next_tx.journal.events[-1].sequence_no==10
    for seq in (10,9):
        with pytest.raises(ValueError):
            transition(next_tx,TransactionEvent('tx',seq,E.PRECOMMIT_PASSED,FACTS))
    with pytest.raises(ValueError):
        TransactionJournal(tuple(reversed(next_tx.journal.events)))


def test_immutable_deterministic_states():
    tx=committed(); assert committed()==tx and tx.state==tx.state
    for value in (AUTH,BINDING,DEF,FACTS,CURRENT,tx,tx.state,tx.journal,tx.journal.events[0],tx.state.steps[0],tx.state.postflight):
        with pytest.raises(FrozenInstanceError):
            value.changed=True


def test_no_existing_layer_execution(monkeypatch):
    from davinci_ai_editor import authority,expected_diff,native_snapshot,safety,safety_preflight,temporal_mapping
    from davinci_ai_editor.fake_timeline import FakeTimeline
    def forbidden(*args,**kwargs):
        pytest.fail('unexpected external execution')
    for module,name in [(expected_diff,'compile_expected_diff'),(expected_diff,'verify_diff'),
        (native_snapshot,'evaluate_readiness'),(temporal_mapping,'map_range'),(safety,'preflight'),
        (safety_preflight,'preflight'),(authority,'transition'),(FakeTimeline,'apply')]:
        monkeypatch.setattr(module,name,forbidden)
    assert promotion_eligibility(committed(),CURRENT)==PromotionEligibility.ELIGIBLE
