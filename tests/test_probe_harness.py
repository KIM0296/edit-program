import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path

import pytest

from davinci_ai_editor import probe_harness as h
from davinci_ai_editor.probe_evidence import ScopeCompleteness
from test_probe_evidence import PROFILE, DOMAIN, BEFORE, AFTER, SCOPE, p

REG=h.RegisteredProbeEnvironment('environment','registry',1,'disposable-project',1,'catalog','v1',PROFILE)
FACTS=h.EnvironmentFacts(REG,'disposable-project','timeline',PROFILE,'environment-fingerprint')
ENV=h.EnvironmentVerification('environment-proof',FACTS,h.EnvironmentVerificationStatus.VERIFIED,'independent-read')
ASSETS=h.FixtureAssetManifest('assets','v1',(h.FixtureAsset('test-asset','content-hash','canonical-metadata'),))
DEF=h.ProbeFixtureDefinition('fixture','v1',p.ProbeFixtureClass.ISOLATED_PLACEMENT,'catalog','v1',ASSETS,(BEFORE,))
INV=p.NativeInvocationSpec(p.ProbePrimitive.TRANSLATE_PLACEMENT,'invoke-v1',('placement',),delta_frames=-20)
ALLOW=h.PrimitiveAllowlist('allowlist',PROFILE,(INV,),tuple(h.ProbeRunMode))
ENVELOPE=h.ContainmentEnvelope('envelope',('placement',),'project-baseline')
CASE=h.HarnessProbeCase('case',DEF,DOMAIN,INV,SCOPE,ENVELOPE,h.ProbeRunMode.QUALIFYING)


def clean(instance='fixture-instance',mode=h.ProbeRunMode.QUALIFYING):
    state=h.register_environment(REG)
    state=h.verify_environment(state,ENV,FACTS)
    state=h.define_fixture(state,instance,DEF,'timeline',1)
    for phase in (h.FixtureLifecycleState.MATERIALIZING,h.FixtureLifecycleState.MATERIALIZED,h.FixtureLifecycleState.VERIFYING):
        state=h.advance_fixture(state,instance,phase)
    snapshot=h.FixtureSnapshot(REG,instance,'timeline',PROFILE,'pre-snapshot',SCOPE,(BEFORE,))
    proof=h.FixtureVerificationResult('fixture-proof',instance,DEF,snapshot,h.FixtureVerificationStatus.MATCH,'fixture-independent-read')
    state=h.verify_fixture(state,instance,proof)
    binding=h.ProbeRunBinding('run',REG,instance,replace(CASE,mode=mode),snapshot)
    return state,binding


def armed(mode=h.ProbeRunMode.QUALIFYING):
    state,binding=clean(mode=mode)
    state=h.lease_probe(state,'lease',binding)
    state=h.authorize_probe(state,'run','authorization',ALLOW)
    current=h.CurrentInvocationFacts(binding,FACTS,ALLOW,'lease','fixture-proof')
    return state,current


def submitted(mode=h.ProbeRunMode.QUALIFYING):
    state,current=armed(mode)
    return h.final_gate(state,'run',current,'attempt').harness,current


def observed(classification=h.ContainmentClass.CLEAN,status=h.FixtureVerificationStatus.MATCH,mode=h.ProbeRunMode.QUALIFYING):
    state,current=submitted(mode)
    state=h.record_outcome(state,'run',h.NativeInvocationOutcome.SUCCEEDED,'native-metadata')
    snapshot=replace(current.binding.pre_snapshot,snapshot_ref='post-snapshot',states=(AFTER,))
    observation=h.PostObservation('observation',current.binding,snapshot,'observed-diff',status)
    containment=h.ContainmentResult('containment',current.binding,classification,'observation','containment-proof')
    return h.observe_run(state,'run',observation,containment),current


def test_registration_verification_arming_are_separate():
    state=h.register_environment(REG)
    assert state.state==h.ProbeHarnessState.DISARMED
    assert state.verification is None
    assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
    verified=h.verify_environment(state,ENV,FACTS)
    assert verified.state==h.ProbeHarnessState.ENVIRONMENT_VERIFIED
    assert verified.generation_status==h.ProjectGenerationStatus.VERIFIED_CLEAN
    assert verified.runs==()
    state,current=armed()
    assert state.state==h.ProbeHarnessState.ARMED_FOR_ONE_RUN
    assert not state.run('run').authorization_consumed
    assert state.run('run').attempt is None


@pytest.mark.parametrize('field,value',[('production',True),('authoritative',True),('disposable',False),('isolated',False)])
def test_production_working_or_duplicate_in_user_project_rejected(field,value):
    with pytest.raises(ValueError): replace(REG,**{field:value})


def test_name_path_sentinel_not_registration_authority():
    with pytest.raises(TypeError): h.RegisteredProbeEnvironment(project_name='probe',path='test',sentinel='safe')
    assert not hasattr(REG,'project_name')
    assert not hasattr(REG,'sentinel')


@pytest.mark.parametrize('status',[h.EnvironmentVerificationStatus.STALE,h.EnvironmentVerificationStatus.MISMATCH,
    h.EnvironmentVerificationStatus.INCOMPLETE,h.EnvironmentVerificationStatus.CONTAMINATED])
def test_nonverified_environment_cannot_arm(status):
    state=h.verify_environment(h.register_environment(REG),replace(ENV,status=status),FACTS)
    assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
    assert state.state!=h.ProbeHarnessState.ENVIRONMENT_VERIFIED


@pytest.mark.parametrize('field', ['registry_generation','project_generation','fixture_catalog_version','profile'])
def test_environment_verification_exact_binding(field):
    value=2 if field.endswith('generation') else ('new' if field=='fixture_catalog_version' else replace(PROFILE,adapter_version='new'))
    current=replace(FACTS,registration=replace(REG,**{field:value}))
    state=h.verify_environment(h.register_environment(REG),ENV,current)
    assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED


def test_fixture_legal_path_and_illegal_direct_clean():
    state=h.verify_environment(h.register_environment(REG),ENV,FACTS)
    state=h.define_fixture(state,'fixture-instance',DEF,'timeline',1)
    with pytest.raises(ValueError): h.advance_fixture(state,'fixture-instance',h.FixtureLifecycleState.CLEAN_VERIFIED)
    with pytest.raises(ValueError): h.advance_fixture(state,'fixture-instance',h.FixtureLifecycleState.MATERIALIZED)
    final,_=clean()
    assert final.fixture('fixture-instance').state==h.FixtureLifecycleState.CLEAN_VERIFIED


@pytest.mark.parametrize('status',[h.FixtureVerificationStatus.MISMATCH,h.FixtureVerificationStatus.INCOMPLETE,h.FixtureVerificationStatus.STALE])
def test_match_only_fixture_verification(status):
    state,binding=clean()
    instance=state.fixture('fixture-instance')
    # New independent instance with a supplied non-MATCH observation.
    state=h.define_fixture(state,'bad',DEF,'timeline',2)
    for phase in (h.FixtureLifecycleState.MATERIALIZING,h.FixtureLifecycleState.MATERIALIZED,h.FixtureLifecycleState.VERIFYING):
        state=h.advance_fixture(state,'bad',phase)
    proof=replace(instance.verification,verification_ref='bad-proof',instance_ref='bad',snapshot=replace(binding.pre_snapshot,instance_ref='bad'),status=status)
    state=h.verify_fixture(state,'bad',proof)
    assert state.fixture('bad').state!=h.FixtureLifecycleState.CLEAN_VERIFIED
    with pytest.raises(ValueError): h.lease_probe(state,'bad-lease',replace(binding,fixture_instance_ref='bad',pre_snapshot=proof.snapshot))
    with pytest.raises(ValueError): h.advance_fixture(state,'bad',h.FixtureLifecycleState.VERIFYING)


def test_wrong_canonical_definition_version_or_assets_cannot_verify():
    state,binding=clean()
    state=h.define_fixture(state,'bad',DEF,'timeline',2)
    for phase in (h.FixtureLifecycleState.MATERIALIZING,h.FixtureLifecycleState.MATERIALIZED,h.FixtureLifecycleState.VERIFYING): state=h.advance_fixture(state,'bad',phase)
    proof=h.FixtureVerificationResult('bad-proof','bad',replace(DEF,version='wrong'),replace(binding.pre_snapshot,instance_ref='bad'),h.FixtureVerificationStatus.MATCH,'read')
    out=h.verify_fixture(state,'bad',proof)
    assert out.fixture('bad').state!=h.FixtureLifecycleState.CLEAN_VERIFIED
    with pytest.raises(ValueError): h.FixtureAsset('filename.mov','','metadata')


def test_single_active_lease_and_no_duplicate_run_or_auth():
    state,current=armed()
    with pytest.raises(ValueError): h.lease_probe(state,'second',replace(current.binding,run_ref='second'))
    with pytest.raises(ValueError): h.authorize_probe(state,'run','second-authorization',ALLOW)


@pytest.mark.parametrize('mode',list(h.ProbeRunMode))
@pytest.mark.parametrize('mismatch',['project','timeline','fixture','generation','profile','pre-snapshot','case','domain','scope','envelope','primitive','lease','verification','allowlist','mode'])
def test_final_gate_mismatch_consumes_auth_with_zero_attempts(mode,mismatch):
    state,current=armed(mode)
    b=current.binding
    if mismatch=='project': current=replace(current,environment=replace(FACTS,project_ref='working'))
    if mismatch=='timeline': current=replace(current,environment=replace(FACTS,timeline_ref='other'))
    if mismatch=='fixture': current=replace(current,binding=replace(b,fixture_instance_ref='other'))
    if mismatch=='generation': current=replace(current,binding=replace(b,registration=replace(REG,project_generation=2)))
    if mismatch=='profile': current=replace(current,environment=replace(FACTS,profile=replace(PROFILE,adapter_version='new')))
    if mismatch=='pre-snapshot': current=replace(current,binding=replace(b,pre_snapshot=replace(b.pre_snapshot,snapshot_ref='changed')))
    if mismatch=='case': current=replace(current,binding=replace(b,case=replace(b.case,case_ref='other')))
    if mismatch=='domain': current=replace(current,binding=replace(b,case=replace(b.case,domain=replace(DOMAIN,conditions=('narrowed',)))))
    if mismatch=='scope': current=replace(current,binding=replace(b,case=replace(b.case,scope=replace(SCOPE,scope_ref='expanded'))))
    if mismatch=='envelope': current=replace(current,binding=replace(b,case=replace(b.case,envelope=replace(ENVELOPE,envelope_ref='expanded'))))
    if mismatch=='primitive': current=replace(current,binding=replace(b,case=replace(b.case,invocation=replace(INV,delta_frames=-21))))
    if mismatch=='lease': current=replace(current,lease_ref='other')
    if mismatch=='verification': current=replace(current,fixture_verification_ref='other')
    if mismatch=='allowlist': current=replace(current,allowlist=replace(ALLOW,invocations=()))
    if mismatch=='mode': current=replace(current,binding=replace(b,case=replace(b.case,mode=h.ProbeRunMode.EXPLORATORY if mode==h.ProbeRunMode.QUALIFYING else h.ProbeRunMode.QUALIFYING)))
    result=h.final_gate(state,'run',current,'attempt')
    assert result.submission is None
    run=result.harness.run('run')
    assert run.attempt is None and run.authorization_consumed
    assert run.outcome==h.ProbeRunOutcome.ABORTED
    with pytest.raises(ValueError): h.final_gate(result.harness,'run',current,'retry')


@pytest.mark.parametrize('outcome',list(h.NativeInvocationOutcome))
def test_submitted_consumed_regardless_of_acknowledgement(outcome):
    state,current=submitted()
    assert state.run('run').authorization_consumed
    assert state.run('run').attempt is not None
    state=h.record_outcome(state,'run',outcome,'raw-result')
    assert state.run('run').authorization_consumed
    with pytest.raises(ValueError): h.final_gate(state,'run',current,'retry')
    with pytest.raises(ValueError): h.record_outcome(state,'run',outcome,'duplicate')
    if outcome in (h.NativeInvocationOutcome.TIMEOUT,h.NativeInvocationOutcome.OUTCOME_UNKNOWN):
        assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
        assert state.fixture('fixture-instance').state==h.FixtureLifecycleState.QUARANTINED


def test_invalidated_lease_is_not_reactivated_by_old_authorization():
    state,current=armed()
    state=h.invalidate_lease(state,'lease')
    out=h.final_gate(state,'run',current,'attempt')
    assert out.submission is None
    assert out.harness.run('run').authorization_consumed


@pytest.mark.parametrize('classification,generation',[(h.ContainmentClass.CLEAN,h.ProjectGenerationStatus.VERIFIED_CLEAN),
    (h.ContainmentClass.UNEXPECTED_FIXTURE_LOCAL,h.ProjectGenerationStatus.REVERIFY_REQUIRED),
    (h.ContainmentClass.PROJECT_LEVEL_CONTAMINATION,h.ProjectGenerationStatus.CONTAMINATED),
    (h.ContainmentClass.ENVIRONMENT_UNCERTAIN,h.ProjectGenerationStatus.REVERIFY_REQUIRED)])
def test_containment_matrix(classification,generation):
    state,_=observed(classification)
    assert state.generation_status==generation
    if classification!=h.ContainmentClass.CLEAN:
        assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
        assert state.run('run').outcome!=h.ProbeRunOutcome.PASS_OBSERVED
        assert state.fixture('fixture-instance').state==h.FixtureLifecycleState.QUARANTINED


@pytest.mark.parametrize('status',[h.EnvironmentVerificationStatus.VERIFIED,h.EnvironmentVerificationStatus.MISMATCH,h.EnvironmentVerificationStatus.INCOMPLETE])
def test_fixture_local_requires_independent_project_reverification(status):
    state,_=observed(h.ContainmentClass.UNEXPECTED_FIXTURE_LOCAL)
    state=h.seal_run(state,'run','seal')
    with pytest.raises(ValueError): h.reverify_environment(state,replace(ENV,verification_ref='fresh-proof',status=status),FACTS)
    state=h.discard_fixture(state,'fixture-instance')
    with pytest.raises(ValueError): h.reverify_environment(state,ENV,FACTS)
    proof=replace(ENV,verification_ref='fresh-proof',status=status,independent_read_ref='fresh-project-read')
    state=h.reverify_environment(state,proof,FACTS)
    expected=h.ProjectGenerationStatus.VERIFIED_CLEAN if status==h.EnvironmentVerificationStatus.VERIFIED else h.ProjectGenerationStatus.CONTAMINATED
    assert state.generation_status==expected


def test_contaminated_cannot_clean_in_place_new_generation_only():
    state,_=observed(h.ContainmentClass.PROJECT_LEVEL_CONTAMINATION)
    state=h.discard_fixture(h.seal_run(state,'run','seal'),'fixture-instance')
    with pytest.raises(ValueError): h.reverify_environment(state,replace(ENV,verification_ref='fresh'),FACTS)
    with pytest.raises(ValueError): h.verify_environment(state,replace(ENV,verification_ref='fresh'),FACTS)
    with pytest.raises(ValueError): h.rebuild_environment(state,REG)
    new=replace(REG,project_generation=2)
    state=h.rebuild_environment(state,new)
    assert state.registration==new
    assert state.run('run').sealed_evidence is not None
    assert state.generation_history[-1].registration==REG
    assert state.verification is None
    stale=h.verify_environment(state,ENV,FACTS)
    assert stale.no_further_mutation==h.NoFurtherMutationGate.BLOCKED


def test_crash_before_invocation_requires_new_verification_and_new_run():
    state,current=armed()
    state=h.crash(state,'run','crash-before')
    assert state.run('run').attempt is None
    assert state.run('run').authorization_consumed
    assert state.fixture('fixture-instance').state==h.FixtureLifecycleState.ABORTED
    with pytest.raises(ValueError): h.lease_probe(state,'new-lease',replace(current.binding,run_ref='new-run'))
    state=h.advance_fixture(state,'fixture-instance',h.FixtureLifecycleState.VERIFYING)
    old=state.fixture('fixture-instance').verification
    with pytest.raises(ValueError): h.verify_fixture(state,'fixture-instance',old)
    state=h.verify_fixture(state,'fixture-instance',replace(old,verification_ref='fresh-proof',independent_read_ref='fresh-read'))
    state=h.lease_probe(state,'new-lease',replace(current.binding,run_ref='new-run'))
    with pytest.raises(ValueError): h.authorize_probe(state,'new-run','authorization',ALLOW)


def test_crash_during_call_blocks_without_claiming_cancellation():
    state,current=submitted()
    attempted=state.run('run').attempt
    state=h.crash(state,'run','bridge-loss')
    assert state.run('run').attempt.attempt_ref==attempted.attempt_ref
    assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
    assert state.state==h.ProbeHarnessState.LOCKED_DOWN
    assert not hasattr(state,'cancel_native_call')
    assert state.run('run').effective_containment==h.ContainmentClass.ENVIRONMENT_UNCERTAIN
    with pytest.raises(ValueError): h.final_gate(state,'run',current,'retry')


def test_observation_scope_expansion_cannot_qualify_or_relabel():
    state,current=submitted()
    state=h.record_outcome(state,'run',h.NativeInvocationOutcome.SUCCEEDED,'result')
    expanded=replace(SCOPE,scope_ref='expanded',subject_refs=('placement','other'))
    snapshot=replace(current.binding.pre_snapshot,snapshot_ref='post',scope=expanded,states=(AFTER,))
    observation=h.PostObservation('obs',current.binding,snapshot,'diff',h.FixtureVerificationStatus.MATCH)
    containment=h.ContainmentResult('c',current.binding,h.ContainmentClass.CLEAN,'obs','proof')
    state=h.observe_run(state,'run',observation,containment)
    assert state.run('run').outcome!=h.ProbeRunOutcome.PASS_OBSERVED
    assert state.no_further_mutation==h.NoFurtherMutationGate.BLOCKED
    assert state.run('run').observation.snapshot.scope==expanded
    assert state.run('run').binding.case.scope==SCOPE


@pytest.mark.parametrize('status',[h.FixtureVerificationStatus.MATCH,h.FixtureVerificationStatus.MISMATCH])
def test_mutated_pass_and_fail_fixture_never_reused_evidence_survives_discard(status):
    state,current=observed(status=status)
    state=h.seal_run(state,'run','sealed')
    sealed=state.run('run').sealed_evidence
    with pytest.raises(ValueError): h.advance_fixture(state,'fixture-instance',h.FixtureLifecycleState.VERIFYING)
    state=h.discard_fixture(state,'fixture-instance')
    assert state.run('run').sealed_evidence==sealed
    with pytest.raises(ValueError): h.lease_probe(state,'second',replace(current.binding,run_ref='second'))
    with pytest.raises(ValueError): h.define_fixture(state,'fixture-instance',DEF,'timeline',2)
    with pytest.raises(FrozenInstanceError): sealed.evidence_ref='rewrite'


def test_exploratory_does_not_count_and_suite_no_implicit_editor_work():
    state,_=observed(mode=h.ProbeRunMode.EXPLORATORY)
    state=h.seal_run(state,'run','sealed')
    evidence=state.run('run').sealed_evidence
    suite=h.ProbeSuite('suite',PROFILE,p.CapabilityVerificationPolicy(INV.primitive),h.SuitePurpose.DEVELOPMENT,(evidence,))
    assert suite.qualifying_evidence_refs==()
    assert suite.production_editor_manual_probe_work==0
    with pytest.raises(TypeError): replace(suite,purpose='ordinary-edit')


def test_fake_shell_has_only_logical_boundary_and_no_native_callback():
    state,current=armed()
    shell=h.FakeProbeHarness(state)
    result=shell.submit('run',current,'attempt')
    assert result.submission is not None
    assert result.harness.run('run').attempt.outcome is None
    assert shell.harness.run('run').attempt is None
    with pytest.raises(ValueError): h.FakeProbeHarness(result.harness).submit('run',current,'retry')


def test_immutable_defensive_copy_deterministic():
    state,current=armed()
    values=list(state.fixtures)
    copy=replace(state,fixtures=values);values.clear()
    assert len(copy.fixtures)==1
    assert h.final_gate(state,'run',current,'attempt')==h.final_gate(state,'run',current,'attempt')
    def frozen(value):
        if is_dataclass(value):
            field=fields(value)[0]
            with pytest.raises(FrozenInstanceError): setattr(value,field.name,getattr(value,field.name))
            for field in fields(value): frozen(getattr(value,field.name))
        elif isinstance(value,tuple):
            for item in value: frozen(item)
    frozen(state)


def test_no_native_or_upstream_calls(monkeypatch):
    state,current=armed()
    def forbidden(*args,**kwargs): raise AssertionError('side effect')
    from davinci_ai_editor import probe_evidence,native_snapshot,transaction,authority
    from davinci_ai_editor.fake_timeline import FakeTimeline
    for module,name in ((probe_evidence,'derive_capability'),(native_snapshot,'evaluate_readiness'),(transaction,'transition'),(authority,'transition')): monkeypatch.setattr(module,name,forbidden)
    monkeypatch.setattr(FakeTimeline,'apply',forbidden)
    assert h.FakeProbeHarness(state).submit('run',current,'attempt').submission is not None
    tree=ast.parse(Path(h.__file__).read_text(encoding='utf-8-sig'))
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)} <= {'dataclasses','enum','typing','probe_evidence'}
