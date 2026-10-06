from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor import authority, dependency, evidence, pause, safety, temporal_mapping
from davinci_ai_editor.domain import FrameRange, TrackType
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.native_snapshot import (
    PAUSE_ANALYSIS, AdapterCapability, AdapterProvenance, CapabilityKind as C,
    CapabilityManifest, CapabilityState as CS, CaptureConsistency as CC,
    IdentityBasis as IB, IdentityRef, IdentityScope as IS, NativePlacementSnapshot,
    NativeTimelineSnapshot, NativeTrackSnapshot, ObservedFlag, ObservedValue as V,
    ReadinessReason as R, ReadinessStatus as S, SnapshotCompleteness as SC,
    evaluate_readiness,
)
from davinci_ai_editor.temporal_mapping import (
    FrameRate, MappingKind, NativeSnapshotRef, SourceFrameRange, TimelineFrameRange,
)


def identity(ref,scope=IS.SNAPSHOT_LOCAL):
    return IdentityRef(ref,scope,IB.NATIVE)


PROVENANCE=AdapterProvenance('supplied-adapter','1','v1','20','windows')
MANIFEST=CapabilityManifest(tuple(AdapterCapability(kind,CS.SUPPORTED)
                                 for kind in PAUSE_ANALYSIS.required_capabilities))
TRACK=NativeTrackSnapshot('capture',identity('track'),TrackType.AUDIO,('one',),
                          native_index=1,display_name='A1 Dialogue')
PLACEMENT=NativePlacementSnapshot('capture',identity('one'),'track',identity('media'),
    TimelineFrameRange(FrameRange(10,110)),SourceFrameRange(FrameRange(0,100)),
    FrameRate(24,1),FrameRate(24,1),MappingKind.IDENTITY_1X)
SNAPSHOT=NativeTimelineSnapshot('capture',identity('timeline'),42,'state',FrameRate(24,1),
    (TRACK,),(PLACEMENT,),PROVENANCE,MANIFEST,CC.CONSISTENT,
    SC.COMPLETE_FOR_DECLARED_CAPABILITIES,'consistency-proof')
CURRENT=NativeSnapshotRef('timeline',42,'state')


def manifest(kind,state):
    return CapabilityManifest(tuple(e for e in MANIFEST.entries if e.kind != kind)
                              +(AdapterCapability(kind,state),))


def assess(snapshot=SNAPSHOT,profile=PAUSE_ANALYSIS,current=CURRENT):
    return evaluate_readiness(snapshot,profile,current)


def test_conservative_analysis_ready_is_not_permission():
    result=assess()
    assert result.status == S.READY
    assert result.snapshot == SNAPSHOT and result.profile == PAUSE_ANALYSIS
    assert not hasattr(result,'approved') and not hasattr(result,'apply')


@pytest.mark.parametrize('left,right',[(IS.PERSISTENT_VERIFIED,IS.SESSION_LOCAL_VERIFIED),
    (IS.SESSION_LOCAL_VERIFIED,IS.SNAPSHOT_LOCAL),(IS.SNAPSHOT_LOCAL,IS.UNKNOWN)])
def test_identity_lifetime_is_distinct_not_probability(left,right):
    assert left != right
    with pytest.raises((TypeError,ValueError)):
        identity('item',0.8)
    assert not hasattr(identity('item',left),'confidence')


@pytest.mark.parametrize('value,field',[(PROVENANCE,'adapter_version'),(MANIFEST,'entries'),
    (TRACK,'display_name'),(PLACEMENT,'retime_kind'),(SNAPSHOT,'tracks'),
    (PAUSE_ANALYSIS,'profile_version'),(assess(),'status'),(identity('x'),'scope')])
def test_frozen_values(value,field):
    with pytest.raises(FrozenInstanceError):
        setattr(value,field,None)


def test_defensive_nested_copy():
    tracks=[TRACK]
    placements=[PLACEMENT]
    copy=replace(SNAPSHOT,tracks=tracks,placements=placements)
    tracks.clear(); placements.clear()
    entries=list(MANIFEST.entries)
    caps=CapabilityManifest(entries)
    entries.clear()
    members=['one']
    track=replace(TRACK,placement_refs=members)
    members.clear()
    assert copy == SNAPSHOT and caps == MANIFEST and track == TRACK


def test_supported_capability_and_unknown_value_is_valid_but_not_ready():
    snapshot=replace(SNAPSHOT,placements=(replace(PLACEMENT,retime_kind=MappingKind.UNKNOWN),))
    assert snapshot.capabilities.state(C.RETIME) == CS.SUPPORTED
    assert snapshot.placements[0].retime_kind == MappingKind.UNKNOWN
    assert assess(snapshot).status == S.UNVERIFIED


@pytest.mark.parametrize('state',[CS.UNKNOWN,CS.UNSUPPORTED])
@pytest.mark.parametrize('value',[V.TRUE,V.FALSE])
def test_unsupported_or_unknown_capability_cannot_carry_known_flag(state,value):
    placement=replace(PLACEMENT,observations=(ObservedFlag(C.EFFECTS,value),))
    with pytest.raises(ValueError):
        replace(SNAPSHOT,placements=(placement,),capabilities=manifest(C.EFFECTS,state))


@pytest.mark.parametrize('state',[CS.UNKNOWN,CS.UNSUPPORTED])
def test_unknown_optional_flag_preserved_not_false(state):
    placement=replace(PLACEMENT,observations=(ObservedFlag(C.EFFECTS,V.UNKNOWN),))
    snapshot=replace(SNAPSHOT,placements=(placement,),capabilities=manifest(C.EFFECTS,state))
    assert snapshot.placements[0].observations[0].value == V.UNKNOWN
    assert assess(snapshot).status == S.READY
    richer=replace(PAUSE_ANALYSIS,profile_id='effects-analysis',
                   required_capabilities=PAUSE_ANALYSIS.required_capabilities+(C.EFFECTS,))
    assert assess(snapshot,richer).status == (S.UNSUPPORTED if state == CS.UNSUPPORTED else S.UNVERIFIED)


def test_complete_does_not_satisfy_richer_profile_even_if_capability_supported():
    snapshot=replace(SNAPSHOT,capabilities=manifest(C.EFFECTS,CS.SUPPORTED),
        placements=(replace(PLACEMENT,observations=(ObservedFlag(C.EFFECTS,V.UNKNOWN),)),))
    richer=replace(PAUSE_ANALYSIS,profile_id='effects-analysis',
        required_capabilities=PAUSE_ANALYSIS.required_capabilities+(C.EFFECTS,))
    assert snapshot.completeness == SC.COMPLETE_FOR_DECLARED_CAPABILITIES
    assert assess(snapshot,richer).status == S.UNVERIFIED
    known=replace(snapshot,placements=(replace(PLACEMENT,observations=(ObservedFlag(C.EFFECTS,V.FALSE),)),))
    assert assess(known,richer).status == S.READY


@pytest.mark.parametrize('consistency,status',[(CC.UNSTABLE,S.REVIEW_REQUIRED),(CC.UNVERIFIED,S.UNVERIFIED)])
def test_capture_consistency_not_silently_upgraded(consistency,status):
    snapshot=replace(SNAPSHOT,capture_consistency=consistency,consistency_evidence_ref=None)
    assert assess(snapshot).status == status
    assert snapshot.capture_consistency == consistency


def test_consistent_requires_supplied_evidence_reference():
    with pytest.raises(ValueError):
        replace(SNAPSHOT,consistency_evidence_ref=None)


def test_partial_capture_never_automatically_ready():
    assert assess(replace(SNAPSHOT,completeness=SC.PARTIAL)).status == S.REVIEW_REQUIRED


def test_missing_supported_fields_cannot_claim_complete():
    incomplete=replace(PLACEMENT,source_range=None)
    with pytest.raises(ValueError):
        replace(SNAPSHOT,placements=(incomplete,))
    partial=replace(SNAPSHOT,placements=(incomplete,),completeness=SC.PARTIAL)
    assert assess(partial).status != S.READY


def test_missing_state_token_preserved_and_blocks_freshness():
    snapshot=replace(SNAPSHOT,state_token=None,capabilities=manifest(C.FRESHNESS,CS.UNKNOWN))
    assert snapshot.state_token is None
    assert assess(snapshot).status == S.UNVERIFIED
    assert snapshot.state_token is None
    assert assess(current=None).status == S.UNVERIFIED


@pytest.mark.parametrize('field,value',[('timeline_id','other'),('timeline_version',43),('state_token','changed')])
def test_snapshot_mismatch_is_stale(field,value):
    result=assess(current=replace(CURRENT,**{field:value}))
    assert result.status == S.STALE and result.snapshot.state_token == 'state'


def test_repeated_media_distinct_placements_and_membership():
    second=replace(PLACEMENT,object_ref=identity('two'))
    snapshot=replace(SNAPSHOT,tracks=(replace(TRACK,placement_refs=('one','two')),),
        placements=(PLACEMENT,second))
    assert len(snapshot.placements) == 2 and assess(snapshot).status == S.READY
    assert snapshot.placements[0].media_ref == snapshot.placements[1].media_ref


def test_track_labels_never_generate_roles_or_identity():
    track=replace(TRACK,display_name='B-roll',native_index=99)
    assert track.track_ref == TRACK.track_ref
    assert not hasattr(track,'role')
    assert replace(SNAPSHOT,tracks=(track,)).timeline_ref == SNAPSHOT.timeline_ref


def test_filename_only_identity_rejected_without_filename_inference():
    with pytest.raises(ValueError):
        IdentityRef('clip.mov',IS.PERSISTENT_VERIFIED,IB.FILENAME_ONLY)
    # Opaque caller native reference can contain punctuation; no filename heuristics.
    assert identity('opaque.ref').scope == IS.SNAPSHOT_LOCAL
    with pytest.raises(ValueError):
        IdentityRef('generated',IS.PERSISTENT_VERIFIED,IB.SNAPSHOT_ASSIGNED)


def test_unknown_identity_not_promoted_by_complete_or_name():
    placement=replace(PLACEMENT,object_ref=identity('one',IS.UNKNOWN))
    snapshot=replace(SNAPSHOT,placements=(placement,))
    assert assess(snapshot).status == S.REVIEW_REQUIRED
    assert snapshot.placements[0].object_ref.scope == IS.UNKNOWN


def test_identity_requirements_are_explicit_sets_not_scores():
    profile=replace(PAUSE_ANALYSIS,profile_id='persistent-only',
        allowed_identity_scopes=(IS.PERSISTENT_VERIFIED,))
    assert assess(profile=profile).status == S.REVIEW_REQUIRED


def test_mixed_capture_ids_rejected_not_cached_current_snapshot():
    with pytest.raises(ValueError):
        replace(SNAPSHOT,tracks=(replace(TRACK,capture_id='old'),))
    with pytest.raises(ValueError):
        replace(SNAPSHOT,placements=(replace(PLACEMENT,capture_id='old'),))


@pytest.mark.parametrize('change',[{'tracks':(TRACK,TRACK)}, {'placements':(PLACEMENT,PLACEMENT)},
    {'tracks':(replace(TRACK,placement_refs=()),)}, {'placements':(replace(PLACEMENT,track_ref='missing'),)}])
def test_identity_registry_and_membership_fail_closed(change):
    with pytest.raises(ValueError):
        replace(SNAPSHOT,**change)


def test_provenance_retained_and_required():
    assert assess().snapshot.adapter_provenance == PROVENANCE
    with pytest.raises(ValueError):
        replace(PROVENANCE,adapter_version='')
    assert assess(replace(SNAPSHOT,adapter_provenance=replace(PROVENANCE,snapshot_contract_version='v2'))).status == S.UNSUPPORTED


def test_repeated_input_deterministic_without_mutation():
    before=repr(SNAPSHOT)
    assert assess() == assess()
    assert repr(SNAPSHOT) == before


def test_no_mapper_classifier_relationship_authority_safety_executor(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('Read-only boundary crossed')
    for module,name in [(temporal_mapping,'map_range'),(pause,'classify_pause'),
        (authority,'transition'),(safety,'preflight'),(evidence,'prepare_observation')]:
        monkeypatch.setattr(module,name,forbidden)
    for name in dir(dependency):
        if name.startswith('compile'):
            monkeypatch.setattr(dependency,name,forbidden)
    monkeypatch.setattr(FakeTimeline,'apply',forbidden)
    assert assess().status == S.READY
