from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.domain import FrameRange, TimelineObjectId
from davinci_ai_editor.expected_diff import (
    ActualDiff, ActualObjectObservation, CompilerProvenance, DiffBinding,
    DiffCompilationInput, DiffVerificationStatus as V, DisplacementParticipant,
    DisplacementParticipationAssessment, ExpectedDiffStatus as S,
    ParticipationStatus as P, PlacementState, PostRelationStatus,
    PreservationScope, compile_expected_diff, verify_diff,
)
from davinci_ai_editor.pause_planning import (
    GeometryProvenance, PauseCutGeometry, PauseEditProposal, PlanningBinding, TemporalEditIntent,
)
from davinci_ai_editor.temporal_mapping import MappingKind, NativeSnapshotRef

BASE = NativeSnapshotRef('main', 42, 'base-state')
POST = NativeSnapshotRef('main', 43, 'post-state')
PRIMARY_ID = TimelineObjectId('audio', 'dialogue')
BINDING = PlanningBinding('candidate', BASE, PRIMARY_ID, FrameRange(100, 160))
CUT = FrameRange(110, 150)
GEOMETRY = PauseCutGeometry('geometry', BINDING, (CUT,), 20, GeometryProvenance('caller', 'v1'), 'v1')
PROPOSAL = PauseEditProposal('proposal', BINDING, TemporalEditIntent.SHORTEN_GAP, GEOMETRY,
                             CUT, 'target', 'snapshot', 'dependency')
DIFF_BINDING = DiffBinding('proposal', BINDING, 'geometry', CUT)
PRIMARY = PlacementState(PRIMARY_ID, 'media', 'audio', FrameRange(0, 200), FrameRange(0, 200))
A = PlacementState(TimelineObjectId('audio', 'a'), 'repeated-media', 'audio',
                   FrameRange(200, 260), FrameRange(10, 70))
B = PlacementState(TimelineObjectId('video', 'b'), 'repeated-media', 'video',
                   FrameRange(210, 290), FrameRange(10, 90))
UNCHANGED = PlacementState(TimelineObjectId('audio', 'unlisted'), 'media', 'audio',
                           FrameRange(300, 400), FrameRange(0, 100))
PA = DisplacementParticipant(A, -40, 'audio')
PB = DisplacementParticipant(B, -40, 'video')
ASSESSMENT = DisplacementParticipationAssessment('assessment', DIFF_BINDING, P.RESOLVED,
                                               (PA, PB), True)
SCOPE = PreservationScope('scope', DIFF_BINDING, (PRIMARY, A, B, UNCHANGED))
INPUT = DiffCompilationInput('diff', PROPOSAL, ASSESSMENT, SCOPE, BASE,
                              CompilerProvenance('pure-diff', 'v1'))


def compiled(**changes):
    return compile_expected_diff(replace(INPUT, **changes))


def expected():
    result = compiled()
    assert result.status == S.READY_FOR_PREFLIGHT
    assert result.expected_diff is not None
    return result.expected_diff


def actual(diff=None):
    diff = expected() if diff is None else diff
    observations = [ActualObjectObservation(d.before.object_id, d.before, d.after)
                    for d in diff.displacements]
    observations.append(ActualObjectObservation(UNCHANGED.object_id, UNCHANGED, UNCHANGED))
    return ActualDiff('actual', diff.expected_diff_ref, BASE, POST, diff.primary_changes,
                      tuple(observations), PostRelationStatus.VERIFIED,
                      'post-relation-evidence', 'identity-evidence')


def verify(value):
    return verify_diff(expected(), value, POST)


def test_exact_effects_and_unchanged_scope():
    result = expected()
    assert result.primary_changes[0].removed_timeline_range == CUT
    assert result.primary_changes[0].before == PRIMARY
    assert {d.before.object_id for d in result.displacements} == {A.object_id, B.object_id}
    assert result.unchanged_object_ids == (UNCHANGED.object_id,)
    assert result.expected_topology_changes == ()
    for d in result.displacements:
        assert d.delta_frames == -40
        assert d.after.timeline_range == FrameRange(d.before.timeline_range.start - 40,
                                                    d.before.timeline_range.end - 40)
        assert replace(d.after, timeline_range=d.before.timeline_range) == d.before
    assert verify(actual()).status == V.MATCH


@pytest.mark.parametrize('status,want', [(P.REVIEW_REQUIRED,S.REVIEW_REQUIRED),
    (P.CONFLICT,S.REVIEW_REQUIRED),(P.UNSUPPORTED,S.UNSUPPORTED),(P.STALE,S.STALE)])
def test_only_resolved_participation(status, want):
    result = compiled(participation=replace(ASSESSMENT, status=status))
    assert result.status == want and result.expected_diff is None


def test_no_implicit_participant_selection():
    assessment = replace(ASSESSMENT, participants=(PA,))
    diff = compiled(participation=assessment).expected_diff
    assert diff is not None and len(diff.displacements) == 1
    assert set(diff.unchanged_object_ids) == {B.object_id, UNCHANGED.object_id}


@pytest.mark.parametrize('delta', [-39, -20, 0, -41])
def test_nonuniform_no_gap_guess(delta):
    result = compiled(participation=replace(ASSESSMENT, participants=(replace(PA, delta_frames=delta),PB)))
    assert result.status == S.UNSUPPORTED
    assert result.expected_diff is None


def test_gap_consequence_requires_explicit_proof():
    assert compiled(participation=replace(ASSESSMENT, uniform_consequence_verified=False)).status == S.REVIEW_REQUIRED


@pytest.mark.parametrize('span',[FrameRange(100,200),FrameRange(120,200),FrameRange(0,100)])
def test_not_fully_downstream_no_trim_move(span):
    state = replace(A, timeline_range=span)
    scope = replace(SCOPE, objects=(PRIMARY,state,B,UNCHANGED))
    result = compiled(scope=scope, participation=replace(ASSESSMENT, participants=(replace(PA,before=state),PB)))
    assert result.status == S.UNSUPPORTED


def test_cross_track_rejected():
    assert compiled(participation=replace(ASSESSMENT, participants=(replace(PA,after_track_id='video'),PB))).status == S.UNSUPPORTED


@pytest.mark.parametrize('kind',[MappingKind.REVERSE,MappingKind.FREEZE,MappingKind.VARIABLE_RETIME,MappingKind.UNKNOWN])
def test_unsupported_retime(kind):
    state=replace(A,retime=kind)
    assert compiled(scope=replace(SCOPE,objects=(PRIMARY,state,B,UNCHANGED)),
                    participation=replace(ASSESSMENT,participants=(replace(PA,before=state),PB))).status == S.UNSUPPORTED


def test_omitted_scope_and_known_impacts():
    assert compiled(scope=replace(SCOPE,objects=(PRIMARY,A,UNCHANGED))).status == S.INCOMPLETE
    absent=TimelineObjectId('video','not-scoped')
    assert compiled(participation=replace(ASSESSMENT,known_impacted_ids=(absent,))).status == S.INCOMPLETE


def test_protected_risk_is_not_safety():
    diff=compiled(participation=replace(ASSESSMENT,protected_risk_ids=(A.object_id,))).expected_diff
    assert diff is not None
    assert not any(hasattr(diff,name) for name in ('safe','approved','apply','safety_pass'))


@pytest.mark.parametrize('snapshot',[NativeSnapshotRef('other',42,'base-state'),
    NativeSnapshotRef('main',43,'base-state'),NativeSnapshotRef('main',42,'drift')])
def test_current_mismatch_stale_no_rebase(snapshot):
    result=compiled(current_snapshot=snapshot)
    assert result.status == S.STALE and result.inputs.proposal == PROPOSAL


def test_scope_or_assessment_binding_stale():
    wrong=replace(DIFF_BINDING,proposal_ref='other')
    assert compiled(scope=replace(SCOPE,binding=wrong)).status == S.STALE
    assert compiled(participation=replace(ASSESSMENT,binding=wrong)).status == S.STALE


@pytest.mark.parametrize('remove_primary',[True,False])
def test_missing_expected_change_mismatch(remove_primary):
    a=actual()
    a=replace(a,primary_changes=()) if remove_primary else replace(a,observations=tuple(o for o in a.observations if o.object_id != A.object_id))
    assert verify(a).status == V.MISMATCH


def test_missing_unchanged_observation_unverified():
    a=actual()
    assert verify(replace(a,observations=tuple(o for o in a.observations if o.object_id != UNCHANGED.object_id))).status == V.UNVERIFIED


@pytest.mark.parametrize('field,value',[
    ('timeline_range',FrameRange(161,221)),('timeline_range',FrameRange(160,221)),
    ('media_id','changed'),('source_range',FrameRange(11,71)),('track_id','video'),
    ('object_id',TimelineObjectId('audio','different'))])
def test_mutated_displacement_mismatch(field,value):
    a=actual(); obs=next(o for o in a.observations if o.object_id == A.object_id)
    changed=replace(obs,after=replace(obs.after,**{field:value}))
    assert verify(replace(a,observations=tuple(changed if o==obs else o for o in a.observations))).status == V.MISMATCH


def test_wrong_primary_range_mismatch():
    a=actual(); effect=replace(a.primary_changes[0],removed_timeline_range=FrameRange(111,150))
    assert verify(replace(a,primary_changes=(effect,))).status == V.MISMATCH


def test_extra_changed_object_in_scope_mismatch():
    a=actual(); obs=ActualObjectObservation(UNCHANGED.object_id,UNCHANGED,replace(UNCHANGED,timeline_range=FrameRange(260,360)))
    assert verify(replace(a,observations=tuple(obs if o.object_id==UNCHANGED.object_id else o for o in a.observations))).status == V.MISMATCH


@pytest.mark.parametrize('changes',[{'identity_evidence_ref':None},{'post_relation_evidence_ref':None},
    {'post_relation_status':PostRelationStatus.UNVERIFIED}])
def test_insufficient_identity_or_relation_unverified(changes):
    assert verify(replace(actual(),**changes)).status == V.UNVERIFIED


def test_stale_post_relation():
    assert verify(replace(actual(),post_relation_status=PostRelationStatus.STALE)).status == V.STALE
    assert verify_diff(expected(),actual(),NativeSnapshotRef('main',44,'human')).status == V.STALE
    assert verify(replace(actual(),base_snapshot=POST)).status == V.STALE


def test_topology_mutation_mismatch():
    assert verify(replace(actual(),topology_change_refs=('track-reorder',))).status == V.MISMATCH


def test_deterministic_defensive_copies():
    participants=[PB,PA]; objects=[UNCHANGED,B,A,PRIMARY]
    i=replace(INPUT,participation=replace(ASSESSMENT,participants=participants),scope=replace(SCOPE,objects=objects))
    participants.clear(); objects.clear()
    assert compile_expected_diff(i)==compiled()
    a=actual()
    assert verify(replace(a,observations=tuple(reversed(a.observations))))==verify(a)


def test_frozen_nested_values():
    diff=expected(); a=actual()
    for value in (INPUT,ASSESSMENT,PA,A,SCOPE,DIFF_BINDING,INPUT.provenance,diff,
                  diff.primary_changes[0],diff.displacements[0],a,a.observations[0],verify(a)):
        with pytest.raises(FrozenInstanceError):
            value.unexpected=True


def test_no_other_layer_calls(monkeypatch):
    from davinci_ai_editor import authority,cut_geometry,dependency,native_snapshot,pause,pause_planning,safety,temporal_mapping
    from davinci_ai_editor.fake_timeline import FakeTimeline
    def forbidden(*args,**kwargs):
        pytest.fail('unexpected layer execution')
    for module,name in [(temporal_mapping,'map_range'),(native_snapshot,'evaluate_readiness'),
        (pause_planning,'plan_pause'),(cut_geometry,'resolve_geometry'),(pause,'classify_pause'),
        (safety,'preflight'),(authority,'transition'),(FakeTimeline,'apply')]:
        monkeypatch.setattr(module,name,forbidden)
    for name in vars(dependency):
        if name.startswith('compile'):
            monkeypatch.setattr(dependency,name,forbidden)
    assert verify(actual()).status == V.MATCH
