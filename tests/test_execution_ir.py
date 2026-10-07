from dataclasses import FrozenInstanceError, replace
import ast
from pathlib import Path

import pytest

from davinci_ai_editor import execution_ir as ir
from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.native_snapshot import IdentityScope, ObservedValue
from davinci_ai_editor.transaction import ArtifactBinding, ExecutionAuthorization, RollbackCapability
from test_safety_preflight import COMPILED, BASE, result as safety_result

S = ir.ExecutionIRValidationStatus
C = ir.NativeCapabilityStatus
M = ir.EffectModelStatus
T = ir.TargetResolutionStatus


def sample():
    diff = COMPILED.expected_diff
    safety = safety_result()
    binding = ArtifactBinding(diff.expected_diff_ref, 'safety', BASE)
    auth = ExecutionAuthorization('auth', 'approval', binding)
    profile = ir.RuntimeProfile('adapter', '1', 'resolve-test', 'test-platform', 'session')
    effects = (*diff.primary_changes, *diff.displacements)
    targets = tuple(ir.ExecutionTargetBinding(
        f'target-{i}', binding, e.before, IdentityScope.PERSISTENT_VERIFIED,
        T.VERIFIED, 'session', f'locator-{i}', 'identity-proof', 'locator-proof',
        'mutation-proof', 'postflight-proof',
    ) for i, e in enumerate(effects))
    ops = (ir.RemoveRangeOp('remove', targets[0].target_ref, effects[0]),
           ir.TranslatePlacementOp('move', targets[1].target_ref, effects[1]))
    logical = ir.ExecutionIR('ir', auth, ops, targets)
    manifest = ir.ExecutorCapabilityManifest(profile, (
        ir.PrimitiveCapability('opaque-primitive', C.SUPPORTED_VERIFIED),
    ), C.SUPPORTED_VERIFIED, C.SUPPORTED_VERIFIED, C.SUPPORTED_VERIFIED)
    model = ir.NativeEffectModel('model', binding, profile, M.VERIFIED,
        ('step',), ('opaque-primitive',), ('remove', 'move'), effects,
        tuple(e.before.object_id for e in effects), ('model-proof',))
    reconciliation = ir.ReconciliationSpec('recon', binding, profile, 'step', M.VERIFIED,
        tuple(e.before for e in effects), 'applied-state-evidence',
        'not-applied-state-evidence', ('read-proof',), ('recon-proof',))
    step = ir.NativeExecutionStep('step', 'opaque-primitive', tuple(t.target_ref for t in targets),
        reconciliation, C.SUPPORTED_VERIFIED)
    realization = ir.LoweringRealization('realization', ('remove', 'move'), ('step',), model)
    plan = ir.NativeLoweringPlan('lowering', 'ir', binding, profile, (step,), (realization,))
    return ir.ExecutionIRValidationInput(diff, 'safety', safety, logical, plan, manifest,
        BASE, profile, ObservedValue.TRUE)


def validate(value=None):
    return ir.validate_execution_ir(sample() if value is None else value)


def target(value, **changes):
    return replace(value, execution_ir=replace(value.execution_ir,
        targets=(replace(value.execution_ir.targets[0], **changes), *value.execution_ir.targets[1:])))


def model(value, **changes):
    r = value.lowering.realizations[0]
    return replace(value, lowering=replace(value.lowering,
        realizations=(replace(r, effect_model=replace(r.effect_model, **changes)),)))


def step(value, **changes):
    return replace(value, lowering=replace(value.lowering,
        steps=(replace(value.lowering.steps[0], **changes),)))


def test_vocabulary_exact_and_ready_effects():
    assert {x.value for x in ir.ExecutionOpKind} == {'REMOVE_RANGE', 'TRANSLATE_PLACEMENT'}
    v = sample()
    assert validate(v).status == S.READY_FOR_EXECUTION
    assert v.execution_ir.ops[0].effect == v.expected_diff.primary_changes[0]
    assert v.execution_ir.ops[1].effect == v.expected_diff.displacements[0]
    assert not hasattr(validate(v), 'apply')


@pytest.mark.parametrize('mode', ['missing', 'extra', 'duplicate', 'wrong-range', 'wrong-delta', 'track', 'source'])
def test_ir_exact_semantics(mode):
    v = sample()
    remove, move = v.execution_ir.ops
    ops = (remove, move)
    if mode == 'missing': ops = (remove,)
    if mode == 'extra': ops += (replace(remove, op_ref='extra'),)
    if mode == 'duplicate': ops += (remove,)
    if mode == 'wrong-range': ops = (replace(remove, effect=replace(remove.effect, removed_timeline_range=FrameRange(111, 150))), move)
    if mode == 'wrong-delta':
        e = move.effect
        after = replace(e.after, timeline_range=FrameRange(161, 221))
        ops = (remove, replace(move, effect=replace(e, after=after, delta_frames=-39)))
    if mode in ('track', 'source'):
        before = replace(remove.effect.before, **({'track_id': 'other'} if mode == 'track' else {'source_range': FrameRange(1, 201)}))
        ops = (replace(remove, effect=replace(remove.effect, before=before)), move)
    changed = replace(v, execution_ir=replace(v.execution_ir, ops=ops))
    assert validate(changed).status == S.INVALID
    assert changed.execution_ir.ops == tuple(sorted(ops, key=lambda o: o.op_ref))


@pytest.mark.parametrize('mode', ['missing', 'extra', 'duplicate', 'wrong-range'])
def test_native_exact_effect_multiplicity(mode):
    v = sample()
    effects = v.lowering.realizations[0].effect_model.predicted_effects
    changed = effects[:-1] if mode == 'missing' else (*effects, effects[0])
    if mode == 'wrong-range':
        changed = (replace(effects[0], removed_timeline_range=FrameRange(110, 149)), effects[1])
    assert validate(model(v, predicted_effects=changed)).status == S.INVALID


@pytest.mark.parametrize('field', ['op_refs', 'step_refs'])
def test_duplicate_realization_is_invalid(field):
    v = sample()
    r = v.lowering.realizations[0]
    bad = replace(r, **{field: (*getattr(r, field), getattr(r, field)[0])})
    assert validate(replace(v, lowering=replace(v.lowering, realizations=(bad,)))).status == S.INVALID
    assert validate(replace(v, lowering=replace(v.lowering, realizations=(r, replace(r, realization_ref='again'))))).status == S.INVALID


@pytest.mark.parametrize('scope,status', [(IdentityScope.PERSISTENT_VERIFIED,S.READY_FOR_EXECUTION),
    (IdentityScope.SESSION_LOCAL_VERIFIED,S.READY_FOR_EXECUTION), (IdentityScope.SNAPSHOT_LOCAL,S.UNSUPPORTED),
    (IdentityScope.UNKNOWN,S.INCOMPLETE)])
def test_identity_matrix(scope,status):
    assert validate(target(sample(), identity_scope=scope)).status == status


@pytest.mark.parametrize('field', ['identity_proof_ref','locator_proof_ref','native_locator_ref',
    'mutation_stability_ref','postflight_correspondence_ref'])
def test_session_requires_all_proofs(field):
    v = target(sample(), identity_scope=IdentityScope.SESSION_LOCAL_VERIFIED)
    assert validate(target(v, **{field: None})).status == S.INCOMPLETE


def test_session_change_is_stale_and_locator_not_identity():
    v = sample()
    assert v.execution_ir.targets[0].before.object_id != v.execution_ir.targets[0].native_locator_ref
    assert validate(target(v, session_ref='another')).status == S.STALE
    assert validate(target(v, identity_scope=IdentityScope.SNAPSHOT_LOCAL,
        native_locator_ref='first-match')).status == S.UNSUPPORTED


@pytest.mark.parametrize('resolution,status', [(T.VERIFIED,S.READY_FOR_EXECUTION), (T.STALE,S.STALE),
    (T.AMBIGUOUS,S.INCOMPLETE),(T.UNRESOLVED,S.INCOMPLETE),(T.UNSUPPORTED,S.UNSUPPORTED)])
def test_target_resolution(resolution,status):
    assert validate(target(sample(), resolution=resolution)).status == status


@pytest.mark.parametrize('cap,status', [(C.SUPPORTED_VERIFIED,S.READY_FOR_EXECUTION),
    (C.SUPPORTED_UNVERIFIED,S.INCOMPLETE),(C.UNKNOWN,S.INCOMPLETE),(C.UNSUPPORTED,S.UNSUPPORTED)])
@pytest.mark.parametrize('field', ['primitive','target_identity','post_read','reconciliation'])
def test_capability_matrix(cap,status,field):
    v = sample()
    changes = {field: cap} if field != 'primitive' else {'primitives': (ir.PrimitiveCapability('opaque-primitive',cap),)}
    assert validate(replace(v, manifest=replace(v.manifest, **changes))).status == status


@pytest.mark.parametrize('status,expected', [(M.VERIFIED,S.READY_FOR_EXECUTION),(M.UNVERIFIED,S.INCOMPLETE),
    (M.UNKNOWN,S.INCOMPLETE),(M.CONFLICTING,S.INVALID),(M.STALE,S.STALE)])
def test_effect_model_matrix(status,expected):
    assert validate(model(sample(), status=status)).status == expected


def test_model_evidence_required():
    assert validate(model(sample(), evidence_refs=())).status == S.INCOMPLETE


@pytest.mark.parametrize('field', ['adapter_version','resolve_version','platform','session_ref'])
def test_runtime_profile_currentness(field):
    v = sample()
    assert validate(replace(v, current_profile=replace(v.current_profile, **{field:'changed'}))).status == S.STALE


@pytest.mark.parametrize('field', ['post_read','reconciliation'])
def test_each_step_postread_and_reconciliation_required(field):
    v = sample()
    changed = C.UNKNOWN if field == 'post_read' else None
    assert validate(step(v, **{field:changed})).status == S.INCOMPLETE


@pytest.mark.parametrize('field', ['status','applied_state_ref','not_applied_state_ref','read_evidence_refs','evidence_refs'])
def test_reconciliation_evidence_required(field):
    v = sample()
    r = v.lowering.steps[0].reconciliation
    bad = M.UNVERIFIED if field == 'status' else (() if field.endswith('refs') else None)
    assert validate(step(v, reconciliation=replace(r, **{field:bad}))).status == S.INCOMPLETE


def test_scope_expansion_not_repaired():
    v = sample()
    bad = (*v.lowering.realizations[0].effect_model.possible_subjects, TimelineObjectId('other','extra'))
    assert validate(model(v, possible_subjects=bad)).status == S.UNSUPPORTED
    assert len(v.expected_diff.inputs.scope.objects) == 3


@pytest.mark.parametrize('cap', list(RollbackCapability))
def test_rollback_separate(cap):
    v = sample()
    assert validate(replace(v, manifest=replace(v.manifest, rollback_capability=cap))).status == S.READY_FOR_EXECUTION


def test_fragment_decomposition_requires_bound_verified_evidence():
    v = sample()
    original = v.lowering.steps[0]
    steps = (replace(original, step_ref='prepare', reconciliation=replace(original.reconciliation, step_ref='prepare')),
             replace(original, step_ref='finish', reconciliation=replace(original.reconciliation, step_ref='finish')))
    r = v.lowering.realizations[0]
    refs = ('prepare','finish')
    r = replace(r, step_refs=refs, produces_fragments=True,
        effect_model=replace(r.effect_model, step_refs=refs, primitive_kinds=('opaque-primitive','opaque-primitive')))
    v = replace(v, lowering=replace(v.lowering, steps=steps, realizations=(r,)))
    assert validate(v).status == S.UNSUPPORTED
    proof = ir.FragmentEvidence('fragments', v.lowering.binding, v.current_profile,
        'realization', refs, M.VERIFIED, ir.FragmentPath.INTERMEDIATE_REBINDING, ('proof',))
    valid = replace(v, lowering=replace(v.lowering, realizations=(replace(r, fragment_evidence=proof),)))
    assert validate(valid).status == S.READY_FOR_EXECUTION
    bad = replace(proof, step_refs=('finish','prepare'))
    assert validate(replace(v, lowering=replace(v.lowering, realizations=(replace(r,fragment_evidence=bad),)))).status != S.READY_FOR_EXECUTION


def test_compound_fragment_path():
    v = sample()
    r = v.lowering.realizations[0]
    proof = ir.FragmentEvidence('compound',v.lowering.binding,v.current_profile,'realization',('step',),
        M.VERIFIED,ir.FragmentPath.COMPOUND_PRIMITIVE,('proof',))
    r = replace(r, produces_fragments=True, fragment_evidence=proof)
    assert validate(replace(v, lowering=replace(v.lowering, realizations=(r,)))).status == S.READY_FOR_EXECUTION


@pytest.mark.parametrize('field', ['expected_diff_ref','safety_result_ref'])
def test_authorization_artifact_mismatch(field):
    v = sample()
    auth = v.execution_ir.authorization
    auth = replace(auth, binding=replace(auth.binding, **{field:'wrong'}))
    assert validate(replace(v, execution_ir=replace(v.execution_ir, authorization=auth))).status == S.INVALID


def test_stale_base_and_authorization():
    v = sample()
    assert validate(replace(v,current_snapshot=replace(BASE,state_token='new'))).status == S.STALE
    assert validate(replace(v,authorization_current=ObservedValue.FALSE)).status == S.STALE
    assert validate(replace(v,authorization_current=ObservedValue.UNKNOWN)).status == S.INCOMPLETE


def test_safety_failure_cannot_be_worked_around():
    v = sample()
    assert validate(replace(v,safety=safety_result(protection=None))).status == S.INCOMPLETE


def test_precedence_and_diagnostic_retention():
    v = model(target(sample(),identity_scope=IdentityScope.SNAPSHOT_LOCAL),predicted_effects=())
    v = replace(v,current_snapshot=replace(BASE,state_token='new'))
    r = validate(v)
    assert r.status == S.STALE
    assert {f.status for f in r.findings} >= {S.STALE,S.INVALID,S.UNSUPPORTED}


def test_immutable_defensive_copy_determinism():
    v = sample()
    raw = list(v.execution_ir.ops)
    logical = replace(v.execution_ir,ops=raw)
    raw.clear()
    assert len(logical.ops)==2
    with pytest.raises(FrozenInstanceError): logical.ir_ref='changed'
    with pytest.raises(FrozenInstanceError): validate(v).status=S.INVALID
    assert validate(v)==validate(v)
    reordered = replace(v,execution_ir=replace(v.execution_ir,ops=tuple(reversed(v.execution_ir.ops)),targets=tuple(reversed(v.execution_ir.targets))))
    assert validate(v)==validate(reordered)


def test_typed_inputs_no_enum_or_boolean_coercion():
    with pytest.raises(TypeError): target(sample(),identity_scope='PERSISTENT_VERIFIED')
    with pytest.raises(TypeError): replace(sample(),authorization_current=True)
    with pytest.raises(TypeError): model(sample(),status='VERIFIED')


def test_no_upstream_or_execution_calls(monkeypatch):
    v = sample()
    def forbidden(*args,**kwargs): raise AssertionError('side effect')
    from davinci_ai_editor import expected_diff, safety_preflight, transaction, temporal_mapping
    for module,name in [(expected_diff,'compile_expected_diff'),(expected_diff,'verify_diff'),
        (safety_preflight,'preflight'),(transaction,'transition'),(temporal_mapping,'map_range')]:
        monkeypatch.setattr(module,name,forbidden)
    assert validate(v).status==S.READY_FOR_EXECUTION
    tree=ast.parse(Path(ir.__file__).read_text(encoding='utf-8'))
    allowed={'dataclasses','enum','collections','typing','domain','expected_diff','native_snapshot',
        'safety_preflight','temporal_mapping','transaction'}
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)} <= allowed
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
