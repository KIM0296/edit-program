from dataclasses import FrozenInstanceError, replace
from itertools import permutations

import pytest

from davinci_ai_editor import authority, dependency, evidence, native_snapshot, pause, pause_planning, safety, temporal_mapping
from davinci_ai_editor.cut_geometry import (
    ExplicitGeometryInput, GeometryConfidence as GC, GeometryConstraint,
    GeometryConstraintKind as K, GeometryProducerKind as PK, GeometryProducerRef,
    GeometryResolutionInput, GeometryResolutionReason as R, GeometryResolutionStatus as S,
    resolve_geometry,
)
from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.evidence import EvidenceStrength
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.pause import (
    Confidence, ContentMode, DecisionReason, PauseAction, PauseBoundaryKind, PauseCandidate,
    PauseObservation, PauseSignal, RelativePauseBand,
)
from davinci_ai_editor.pause_planning import PlanningBinding
from davinci_ai_editor.temporal_mapping import MappingStatus, NativeSnapshotRef

SNAP=NativeSnapshotRef('main',42,'state')
OBJECT=TimelineObjectId('audio','placement')
PAUSE=FrameRange(100,160)
CUT=FrameRange(110,150)
OBS=PauseObservation('main',42,OBJECT,PAUSE,RelativePauseBand.LONG,
    PauseBoundaryKind.WITHIN_PHRASE,(PauseSignal.HESITATION,),20,ContentMode.SPOKEN_CONTENT)
CANDIDATE=PauseCandidate(OBS,PauseAction.TIGHTEN,Confidence.MEDIUM,(DecisionReason.HESITATION,),20)
BINDING=PlanningBinding('candidate',SNAP,OBJECT,PAUSE)
PRODUCER=GeometryProducerRef(PK.EXPLICIT_CALLER,'caller','1','v1')
BASE=GeometryResolutionInput('resolution',CANDIDATE,BINDING,SNAP,FrameRange(0,200),MappingStatus.EXACT)


def constraint(ref,kind,payload,confidence=GC.UNKNOWN,producer=PRODUCER):
    return GeometryConstraint(ref,BINDING,kind,payload,producer,confidence)


def explicit(ref='explicit',removed=CUT,confidence=GC.UNKNOWN,producer=PRODUCER):
    return ExplicitGeometryInput(ref,BINDING,(removed,),producer,confidence)


def resolve(constraints=(),geometries=(),**changes):
    return resolve_geometry(replace(BASE,constraints=constraints,explicit_geometries=geometries,**changes))


def test_vocabulary_exactly_four_and_confidence_types_separate():
    assert {k.value for k in K} == {'CUT_START_ANCHOR','CUT_END_ANCHOR','MUST_PRESERVE_RANGE','ALLOWED_REMOVAL_RANGE'}
    assert GC is not EvidenceStrength and GC is not Confidence
    for value in (EvidenceStrength.STRONG,Confidence.HIGH,'STRONG',0.9):
        with pytest.raises(TypeError):
            explicit(confidence=value)


def test_duration_alone_is_unresolved_no_implicit_cut():
    result=resolve()
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert result.inputs.candidate.action == PauseAction.TIGHTEN


def test_unique_explicit_geometry_and_retained_metadata():
    result=resolve(geometries=(explicit(confidence=GC.WEAK),))
    assert result.status == S.RESOLVED and len(result.candidates) == 1
    candidate=result.candidates[0]
    assert candidate.removed_range == CUT and candidate.binding == BINDING
    assert candidate.retained_leading_frames == 10 and candidate.retained_trailing_frames == 10
    assert candidate.retained_total_frames == 20
    assert candidate.geometry_confidences == (GC.WEAK,)
    assert candidate.support_input_ids == ('explicit',)


@pytest.mark.parametrize('removed,reason',[(FrameRange(110,149),R.REQUIRED_DURATION_MISMATCH),
    (FrameRange(99,139),R.OUTSIDE_PAUSE),(FrameRange(121,161),R.OUTSIDE_PAUSE)])
def test_invalid_explicit_geometry_not_repaired(removed,reason):
    item=explicit(removed=removed)
    result=resolve(geometries=(item,))
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert reason in {d.reason for d in result.diagnostics}
    assert result.inputs.explicit_geometries == (item,)


def test_valid_anchor_pair_only():
    constraints=(constraint('start',K.CUT_START_ANCHOR,110,GC.STRONG),
                 constraint('end',K.CUT_END_ANCHOR,150,GC.MODERATE))
    result=resolve(constraints)
    assert result.status == S.RESOLVED
    assert result.candidates[0].removed_range == CUT
    assert set(result.candidates[0].source_constraint_ids) == {'start','end'}
    assert set(result.candidates[0].geometry_confidences) == {GC.STRONG,GC.MODERATE}


@pytest.mark.parametrize('constraints',[
    (constraint('s',K.CUT_START_ANCHOR,110),),
    (constraint('e',K.CUT_END_ANCHOR,150),),
    (constraint('s',K.CUT_START_ANCHOR,110),constraint('e',K.CUT_END_ANCHOR,149)),
    (constraint('s',K.CUT_START_ANCHOR,150),constraint('e',K.CUT_END_ANCHOR,110)),
    (constraint('s',K.CUT_START_ANCHOR,110),constraint('e',K.CUT_END_ANCHOR,110)),
])
def test_missing_or_wrong_pair_never_nearest_anchor(constraints):
    assert resolve(constraints).status == S.UNRESOLVED
    assert resolve(constraints).candidates == ()


def test_multiple_anchor_geometries_require_review_not_lexical_preference():
    constraints=(constraint('z-start',K.CUT_START_ANCHOR,110),constraint('a-start',K.CUT_START_ANCHOR,120),
        constraint('z-end',K.CUT_END_ANCHOR,150),constraint('a-end',K.CUT_END_ANCHOR,160))
    result=resolve(constraints)
    assert result.status == S.REVIEW_REQUIRED
    assert {c.removed_range for c in result.candidates} == {CUT,FrameRange(120,160)}


@pytest.mark.parametrize('left',list(GC))
@pytest.mark.parametrize('right',list(GC))
def test_confidence_never_changes_two_candidate_resolution(left,right):
    result=resolve(geometries=(explicit('a',CUT,left),explicit('b',FrameRange(120,160),right)))
    assert result.status == S.REVIEW_REQUIRED and len(result.candidates) == 2


def test_duplicate_geometry_merges_without_losing_producer_confidence_or_support():
    other=replace(PRODUCER,producer_kind=PK.FUTURE_MODEL,producer_name='future',producer_version='99')
    constraints=(constraint('s',K.CUT_START_ANCHOR,110),constraint('e',K.CUT_END_ANCHOR,150),
                 constraint('allowed',K.ALLOWED_REMOVAL_RANGE,PAUSE))
    result=resolve(constraints,(explicit('one',confidence=GC.STRONG),explicit('two',confidence=GC.WEAK,producer=other)))
    assert result.status == S.RESOLVED and len(result.candidates) == 1
    candidate=result.candidates[0]
    assert set(candidate.support_input_ids) == {'s','e','allowed','one','two'}
    assert set(candidate.source_constraint_ids) == {'s','e','allowed'}
    assert {s.producer for s in candidate.supports} == {PRODUCER,other}
    assert set(candidate.geometry_confidences) == {GC.STRONG,GC.WEAK,GC.UNKNOWN}


def test_support_count_never_picks_winner():
    items=(explicit('a'),explicit('b'),explicit('c',FrameRange(120,160)))
    assert resolve(geometries=items).status == S.REVIEW_REQUIRED


def test_preserve_overlap_rejects_without_shifting_cut():
    protected=constraint('p',K.MUST_PRESERVE_RANGE,FrameRange(110,111))
    result=resolve((protected,),(explicit(),))
    assert result.status == S.UNRESOLVED and result.candidates == ()
    assert R.PRESERVE_RANGE_CONFLICT in {d.reason for d in result.diagnostics}
    assert result.inputs.explicit_geometries[0].removed_ranges == (CUT,)


def test_preserve_touching_half_open_boundary_is_valid():
    constraints=(constraint('left',K.MUST_PRESERVE_RANGE,FrameRange(100,110)),
                 constraint('right',K.MUST_PRESERVE_RANGE,FrameRange(150,160)))
    assert resolve(constraints,(explicit(),)).status == S.RESOLVED


def test_allowed_ranges_use_intersection_not_union():
    constraints=(constraint('a',K.ALLOWED_REMOVAL_RANGE,FrameRange(100,150)),
                 constraint('b',K.ALLOWED_REMOVAL_RANGE,FrameRange(110,160)))
    assert resolve(constraints,(explicit(),)).status == S.RESOLVED
    bad=constraints+(constraint('c',K.ALLOWED_REMOVAL_RANGE,FrameRange(120,160)),)
    result=resolve(bad,(explicit(),explicit('other',FrameRange(120,160))))
    assert result.status == S.UNRESOLVED
    assert R.OUTSIDE_ALLOWED_REMOVAL in {d.reason for d in result.diagnostics}


def test_preserve_or_allowed_constraints_alone_do_not_generate_geometry():
    constraints=(constraint('allowed',K.ALLOWED_REMOVAL_RANGE,CUT),)
    assert resolve(constraints).status == S.UNRESOLVED


@pytest.mark.parametrize('field,value',[('timeline_id','other'),('timeline_version',43),('state_token','other')])
def test_current_snapshot_mismatch_stale_no_rebase(field,value):
    result=resolve(geometries=(explicit(),),current_snapshot=replace(SNAP,**{field:value}))
    assert result.status == S.STALE and result.candidates == ()
    assert result.inputs.binding == BINDING


@pytest.mark.parametrize('binding',[
    replace(BINDING,snapshot_ref=replace(SNAP,timeline_version=41)),
    replace(BINDING,snapshot_ref=replace(SNAP,timeline_id='other')),
    replace(BINDING,object_id=TimelineObjectId('audio','other-placement')),
    replace(BINDING,original_pause_range=FrameRange(101,161)),
    replace(BINDING,candidate_ref='other'),
])
def test_mixed_binding_blocks_constraints_and_explicit_inputs(binding):
    bad=replace(explicit(),binding=binding)
    assert resolve(geometries=(bad,)).status in (S.STALE,S.UNSUPPORTED)
    bad_constraint=replace(constraint('s',K.CUT_START_ANCHOR,110),binding=binding)
    assert resolve((bad_constraint,),(explicit(),)).status in (S.STALE,S.UNSUPPORTED)


def test_cross_placement_span_and_multirange_unsupported():
    assert resolve(geometries=(explicit(),),placement_range=FrameRange(100,130)).status == S.UNSUPPORTED
    multi=replace(explicit(),removed_ranges=(FrameRange(100,120),FrameRange(140,160)))
    assert resolve(geometries=(multi,)).status == S.UNSUPPORTED


@pytest.mark.parametrize('status',list(MappingStatus))
def test_nonexact_mapping_not_resolved_or_called(status):
    result=resolve(geometries=(explicit(),),mapping_status=status)
    assert (result.status == S.RESOLVED) == (status == MappingStatus.EXACT)
    if status == MappingStatus.STALE:
        assert result.status == S.STALE


def test_order_independence_and_defensive_input_copy():
    constraints=[constraint('s',K.CUT_START_ANCHOR,110),constraint('e',K.CUT_END_ANCHOR,150)]
    geometries=[explicit('b'),explicit('a',FrameRange(120,160))]
    expected=resolve(constraints,geometries)
    for c in permutations(constraints):
        for g in permutations(geometries):
            assert resolve(c,g) == expected
    constraints.clear(); geometries.clear()
    assert len(expected.inputs.constraints) == 2 and len(expected.inputs.explicit_geometries) == 2


@pytest.mark.parametrize('value,field',[(PRODUCER,'producer_version'),(constraint('a',K.CUT_START_ANCHOR,110),'payload'),
    (explicit(),'removed_ranges'),(BASE,'constraints'),(resolve(geometries=(explicit(),)),'status'),
    (resolve(geometries=(explicit(),)).candidates[0],'removed_range')])
def test_frozen_values(value,field):
    with pytest.raises(FrozenInstanceError):
        setattr(value,field,None)


def test_no_layer_invocations(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('Geometry resolver crossed pure boundary')
    for module,name in [(temporal_mapping,'map_range'),(native_snapshot,'evaluate_readiness'),
        (pause,'classify_pause'),(pause_planning,'plan_pause'),(safety,'preflight'),
        (authority,'transition'),(evidence,'prepare_observation')]:
        monkeypatch.setattr(module,name,forbidden)
    for name in dir(dependency):
        if name.startswith('compile'):
            monkeypatch.setattr(dependency,name,forbidden)
    monkeypatch.setattr(FakeTimeline,'apply',forbidden)
    assert resolve(geometries=(explicit(),)).status == S.RESOLVED
