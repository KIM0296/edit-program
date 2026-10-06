from dataclasses import FrozenInstanceError, replace
from itertools import permutations

import pytest

from davinci_ai_editor import authority, evidence, pause, safety
from davinci_ai_editor.domain import ClipId, FrameRange, MediaId, TimelineId, TimelineObjectId, TimelineVersion, TrackId
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.temporal_mapping import (
    FrameRate, MappingKind as K, MappingReason as R, MappingRequest,
    MappingStatus as S, NativeSnapshotRef, PlacementTemporalBinding,
    SourceFrameRange as Source, TimelineFrameRange as Timeline,
    TimeDomain, map_range,
)

SNAP = NativeSnapshotRef(TimelineId('main'), TimelineVersion(42), 'captured-state')
OBJECT = TimelineObjectId(TrackId('video'), ClipId('placement'))
MEDIA = MediaId('media')
BINDING = PlacementTemporalBinding('mapping-1', SNAP, OBJECT, MEDIA,
    Timeline(FrameRange(100, 200)), Source(FrameRange(20, 120)),
    FrameRate(24, 1), FrameRate(30, 1), K.IDENTITY_1X)


def request(interval, **kwargs):
    return MappingRequest(SNAP, OBJECT, MEDIA, interval, **kwargs)


def mapped(interval, binding=BINDING):
    return map_range(request(interval), (binding,), SNAP)


def affine():
    return replace(BINDING, mapping_kind=K.AFFINE_FORWARD,
        source_range=Source(FrameRange(20, 50)), timeline_range=Timeline(FrameRange(100, 124)))


def test_rates_are_exact_canonical_values():
    assert FrameRate(60000, 2002) == FrameRate(30000, 1001)
    assert FrameRate(30000, 1001) != FrameRate(30, 1)
    assert FrameRate(60000, 1001) != FrameRate(60, 1)
    assert (FrameRate(48, 2).numerator, FrameRate(48, 2).denominator) == (24, 1)


@pytest.mark.parametrize('n,d', [(0,1),(-1,1),(1,0),(1,-1),(True,1),(24,False),(23.976,1),(24,1.0)])
def test_invalid_rate_rejected(n,d):
    with pytest.raises((ValueError,TypeError)):
        FrameRate(n,d)


def test_domain_is_explicit_and_no_implicit_exchange():
    frames = FrameRange(20,30)
    assert Source(frames) != Timeline(frames)
    assert Source(frames).domain == TimeDomain.SOURCE_FRAME
    assert Timeline(frames).domain == TimeDomain.TIMELINE_FRAME
    with pytest.raises(TypeError):
        request(frames)
    with pytest.raises(TypeError):
        replace(BINDING, source_range=Timeline(frames))
    with pytest.raises(TypeError):
        replace(BINDING, timeline_range=Source(frames))


@pytest.mark.parametrize('interval,source,timeline', [
    (Source(FrameRange(30,50)), FrameRange(30,50), FrameRange(110,130)),
    (Timeline(FrameRange(110,130)), FrameRange(30,50), FrameRange(110,130)),
    (Source(FrameRange(20,120)), FrameRange(20,120), FrameRange(100,200)),
])
def test_identity_mapping_both_directions(interval,source,timeline):
    result=mapped(interval)
    assert result.status == S.EXACT
    assert result.source_range == Source(source)
    assert result.timeline_range == Timeline(timeline)
    assert result.binding == BINDING
    assert not hasattr(result,'approved') and not hasattr(result,'apply')


def test_identity_kind_requires_equal_explicit_spans():
    with pytest.raises(ValueError):
        replace(BINDING, timeline_range=Timeline(FrameRange(100,201)))


@pytest.mark.parametrize('interval', [Source(FrameRange(25,40)),Timeline(FrameRange(104,116))])
def test_affine_mixed_fps_exact_both_directions(interval):
    result=mapped(interval,affine())
    assert result.status == S.EXACT
    assert result.source_range == Source(FrameRange(25,40))
    assert result.timeline_range == Timeline(FrameRange(104,116))


@pytest.mark.parametrize('interval', [Source(FrameRange(21,25)),Source(FrameRange(20,26)),
    Source(FrameRange(21,26)),Timeline(FrameRange(101,104)),Timeline(FrameRange(100,105))])
def test_either_fractional_boundary_is_non_integral_without_output(interval):
    result=mapped(interval,affine())
    assert result.status == S.NON_INTEGRAL
    assert result.source_range is None and result.timeline_range is None
    assert result.binding is None


@pytest.mark.parametrize('interval', [Source(FrameRange(19,30)),Source(FrameRange(100,121)),
    Timeline(FrameRange(99,110)),Timeline(FrameRange(199,201))])
def test_outside_by_one_frame_never_clamped(interval):
    result=mapped(interval)
    assert result.status == S.OUT_OF_RANGE
    assert result.source_range is None and result.timeline_range is None


@pytest.mark.parametrize('field,value', [('timeline_id','another'),('timeline_version',43),('state_token','new-state')])
def test_all_snapshot_axes_stale_without_rebase(field,value):
    current=replace(SNAP,**{field:value})
    req=request(Source(FrameRange(25,30)))
    result=map_range(req,(BINDING,),current)
    assert result.status == S.STALE
    assert result.request.snapshot_ref == SNAP and result.candidate_bindings == (BINDING,)
    assert result.timeline_range is None
    old_binding=replace(BINDING,snapshot_ref=current)
    assert map_range(req,(old_binding,),SNAP).status == S.STALE


@pytest.mark.parametrize('field,value', [('object_id',TimelineObjectId(TrackId('video'),ClipId('other'))),
    ('media_id',MediaId('other'))])
def test_wrong_identity_never_maps(field,value):
    result=map_range(replace(request(Source(FrameRange(20,30))),**{field:value}),(BINDING,),SNAP)
    assert result.status != S.EXACT and result.timeline_range is None
    assert R.IDENTITY_MISMATCH in result.reasons


def test_repeated_media_requires_requested_placement():
    other=replace(BINDING,mapping_ref='second',object_id=TimelineObjectId(TrackId('video'),ClipId('other')),
        timeline_range=Timeline(FrameRange(300,400)))
    req=replace(request(Source(FrameRange(20,30))),object_id=other.object_id)
    result=map_range(req,(BINDING,other),SNAP)
    assert result.status == S.EXACT and result.timeline_range == Timeline(FrameRange(300,310))


def test_ambiguous_bindings_never_choose_first_or_latest():
    other=replace(BINDING,mapping_ref='second',timeline_range=Timeline(FrameRange(300,400)))
    results=[map_range(request(Source(FrameRange(20,30))),order,SNAP)
             for order in permutations((BINDING,other))]
    assert results[0] == results[1]
    assert results[0].status == S.AMBIGUOUS


def test_split_lineage_uses_one_concrete_fragment_not_union():
    left=replace(BINDING,source_range=Source(FrameRange(20,70)),timeline_range=Timeline(FrameRange(100,150)))
    right=replace(BINDING,mapping_ref='right',source_range=Source(FrameRange(70,120)),
        timeline_range=Timeline(FrameRange(150,200)))
    result=map_range(request(Source(FrameRange(75,80))),(left,right),SNAP)
    assert result.status == S.EXACT and result.binding == right
    assert result.timeline_range == Timeline(FrameRange(155,160))
    cross=map_range(request(Source(FrameRange(65,75))),(left,right),SNAP)
    assert cross.status == S.AMBIGUOUS and cross.timeline_range is None


def test_cross_placement_range_cannot_be_combined():
    second=replace(BINDING,mapping_ref='second',object_id=TimelineObjectId(TrackId('video'),ClipId('other')),
        timeline_range=Timeline(FrameRange(200,300)))
    result=map_range(request(Timeline(FrameRange(190,210))),(BINDING,second),SNAP)
    assert result.status != S.EXACT and result.source_range is None


@pytest.mark.parametrize('kind',[K.REVERSE,K.FREEZE,K.VARIABLE_RETIME,K.UNKNOWN])
def test_unsupported_kind_not_lowered_as_identity(kind):
    result=mapped(Source(FrameRange(30,40)),replace(BINDING,mapping_kind=kind))
    assert result.status == S.UNSUPPORTED and result.timeline_range is None


def test_fps_alone_never_creates_mapping_and_metadata_does_not_change_math():
    assert map_range(request(Source(FrameRange(20,30))),(),SNAP).status == S.UNSUPPORTED
    a=affine()
    b=replace(a,source_rate=FrameRate(30000,1001),timeline_rate=FrameRate(60,1))
    assert mapped(Source(FrameRange(25,40)),a).timeline_range == mapped(Source(FrameRange(25,40)),b).timeline_range
    with pytest.raises(TypeError):
        PlacementTemporalBinding(source_rate=FrameRate(30,1),timeline_rate=FrameRate(24,1))


def test_exact_roundtrip_large_integers_no_float_loss():
    origin=10**30
    binding=replace(affine(),source_range=Source(FrameRange(origin,origin+30)),
        timeline_range=Timeline(FrameRange(origin+100,origin+124)))
    result=mapped(Source(FrameRange(origin+5,origin+20)),binding)
    assert result.timeline_range == Timeline(FrameRange(origin+104,origin+116))
    assert mapped(result.timeline_range,binding).source_range == result.source_range


@pytest.mark.parametrize('value,field',[ (FrameRate(24,1),'numerator'),(SNAP,'state_token'),
    (BINDING,'mapping_ref'),(Source(FrameRange(20,30)),'frames'),
    (request(Source(FrameRange(20,30))),'media_id'),(mapped(Source(FrameRange(20,30))),'status')])
def test_immutable_values(value,field):
    with pytest.raises(FrozenInstanceError):
        setattr(value,field,None)


def test_defensive_binding_copy_and_determinism():
    bindings=[BINDING]
    req=request(Source(FrameRange(20,30)))
    result=map_range(req,bindings,SNAP)
    bindings.clear()
    assert result.candidate_bindings == (BINDING,)
    assert result == map_range(req,(BINDING,),SNAP)


def test_stale_binding_is_not_silently_replaced_by_fresh_one():
    stale=replace(BINDING,mapping_ref='old',snapshot_ref=replace(SNAP,state_token='old'))
    assert map_range(request(Source(FrameRange(20,30))),(stale,BINDING),SNAP).status == S.STALE


def test_no_execution_or_evidence_generation(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('Mapping crossed an execution/evidence boundary')
    for module,name in [(pause,'classify_pause'),(authority,'transition'),(safety,'preflight'),
                        (evidence,'prepare_observation'),(evidence,'EvidenceRecord')]:
        monkeypatch.setattr(module,name,forbidden)
    monkeypatch.setattr(FakeTimeline,'apply',forbidden)
    assert mapped(Source(FrameRange(20,30))).status == S.EXACT
