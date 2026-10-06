from dataclasses import FrozenInstanceError, replace
from itertools import permutations

import pytest

from davinci_ai_editor import authority, pause, safety
from davinci_ai_editor.domain import (
    Clip, ClipId, FrameRange, MediaId, TimelineId, TimelineObjectId,
    TimelineSnapshot, TimelineVersion, Track, TrackId,
)
from davinci_ai_editor.evidence import (
    CONTRACT_VERSION, EvidenceAssertion as A, EvidenceBinding, EvidenceBundle,
    EvidenceKind as K, EvidenceRecord, EvidenceStrength, LocalPauseReference,
    PreparationReason as R, PreparationStatus as S, Presence, ProducerKind,
    ProducerRef, prepare_observation,
)
from davinci_ai_editor.fake_timeline import FakeTimeline
from davinci_ai_editor.pause import (
    Confidence, ContentMode, PauseBoundaryKind as B, PauseSignal, RelativePauseBand as P,
)

OID = TimelineObjectId(TrackId('a'), ClipId('clip'))
BINDING = EvidenceBinding(TimelineId('main'), TimelineVersion(42), OID, FrameRange(20, 80))
PRODUCER = ProducerRef(ProducerKind.HUMAN_SUPPLIED, 'caller', '1', CONTRACT_VERSION)
SNAPSHOT = TimelineSnapshot(TimelineId('main'), TimelineVersion(42), (
    Track(TrackId('a'), (Clip(ClipId('clip'), MediaId('media'),
                             FrameRange(0, 100), FrameRange(0, 100)),)),
))


def record(kind, payload=Presence(), assertion=A.PRESENT, name=None, **kwargs):
    return EvidenceRecord(name or kind.value, BINDING, PRODUCER, kind, assertion,
                          EvidenceStrength.STRONG, payload, **kwargs)


def base_records():
    return (
        record(K.CONTENT_MODE, ContentMode.SPOKEN_CONTENT),
        record(K.RELATIVE_PAUSE_BAND, P.LONG),
        record(K.TRANSCRIPT_BOUNDARY, B.SENTENCE_BOUNDARY),
    )


def bundle(*extra, records=None, **kwargs):
    return EvidenceBundle('bundle', BINDING.timeline_id, BINDING.base_version, OID,
                          BINDING.observed_range,
                          base_records() + extra if records is None else records,
                          CONTRACT_VERSION, **kwargs)


def prepare(*extra):
    return prepare_observation(bundle(*extra), SNAPSHOT)


def test_ready_is_only_an_observation_and_missing_is_not_an_assertion():
    raw = bundle()
    result = prepare_observation(raw, SNAPSHOT)
    assert result.status == S.READY
    assert result.observation.signals == ()
    assert result.observation.local_reference_pause_frames is None
    assert result.bundle == raw
    assert set(A) == {A.PRESENT, A.ABSENT, A.UNKNOWN}
    assert not hasattr(result, 'approved') and not hasattr(result, 'apply')


@pytest.mark.parametrize('cls,field', [(PRODUCER, 'producer_version'),
    (BINDING, 'base_version'), (record(K.SILENCE_REGION), 'assertion'),
    (bundle(), 'evidence'), (prepare(), 'status')])
def test_frozen_values(cls, field):
    with pytest.raises(FrozenInstanceError):
        setattr(cls, field, None)


def test_defensive_copy_and_order_independence():
    records = list(base_records())
    raw = bundle(records=records)
    records.clear()
    assert len(raw.evidence) == 3
    for order in permutations(raw.evidence):
        assert prepare_observation(bundle(records=order), SNAPSHOT) == prepare()


@pytest.mark.parametrize('field', ['producer_name', 'producer_version', 'evidence_contract_version'])
def test_provenance_required(field):
    with pytest.raises(ValueError):
        replace(PRODUCER, **{field: ' '})


def test_strength_not_candidate_confidence():
    assert EvidenceStrength is not Confidence
    with pytest.raises(TypeError):
        replace(record(K.SILENCE_REGION), strength=Confidence.HIGH)


@pytest.mark.parametrize('field,value', [('timeline_id', 'other'), ('base_version', 41),
    ('object_id', TimelineObjectId(TrackId('a'), ClipId('other')))])
def test_mixed_binding_rejected(field, value):
    wrong = replace(record(K.SILENCE_REGION), binding=replace(BINDING, **{field: value}))
    with pytest.raises(ValueError):
        bundle(wrong)


def test_duplicate_id_and_unrelated_range_rejected():
    with pytest.raises(ValueError):
        bundle(record(K.SILENCE_REGION), record(K.SILENCE_REGION))
    with pytest.raises(ValueError):
        bundle(replace(record(K.SILENCE_REGION), binding=replace(
            BINDING, observed_range=FrameRange(100, 110))))


def test_explicit_context_permits_related_range():
    evidence = replace(record(K.SILENCE_REGION), binding=replace(
        BINDING, observed_range=FrameRange(0, 10)))
    assert prepare_observation(bundle(evidence, context_range=FrameRange(0, 100)),
                               SNAPSHOT).status == S.READY


def test_stale_and_wrong_current_timeline_fail_closed_without_rebase():
    raw = bundle()
    result = prepare_observation(raw, replace(SNAPSHOT, version=45))
    assert result.status == S.STALE and result.observation is None
    assert result.bundle.base_version == 42
    assert prepare_observation(raw, replace(SNAPSHOT, timeline_id='other')).status == S.UNSUPPORTED


@pytest.mark.parametrize('kind,signal', [
    (K.EMOTIONAL_CUE, PauseSignal.EMOTIONAL), (K.THINKING_CUE, PauseSignal.THINKING),
    (K.NATURAL_BREATH_CUE, PauseSignal.NATURAL_BREATH),
    (K.HESITATION_CUE, PauseSignal.HESITATION),
    (K.RECORDING_DEAD_AIR_CUE, PauseSignal.RECORDING_DEAD_AIR),
    (K.FAILED_TAKE_GAP_CUE, PauseSignal.FAILED_TAKE_GAP),
])
def test_explicit_present_mapping(kind, signal):
    assert prepare(record(kind)).observation.signals == (signal,)
    assert prepare(record(kind, assertion=A.ABSENT)).observation.signals == ()
    unknown = prepare(record(kind, assertion=A.UNKNOWN))
    assert unknown.status == S.REVIEW_REQUIRED and unknown.observation is None


def test_semantic_conflict_retains_both_ids_and_raw_records():
    raw = bundle(record(K.EMOTIONAL_CUE), record(K.RECORDING_DEAD_AIR_CUE))
    result = prepare_observation(raw, SNAPSHOT)
    assert result.status == S.REVIEW_REQUIRED and result.observation is None
    assert result.bundle == raw
    assert {i for c in result.conflicts for i in c.evidence_ids} >= {
        'EMOTIONAL_CUE', 'RECORDING_DEAD_AIR_CUE'}


@pytest.mark.parametrize('kind,left,right', [
    (K.TRANSCRIPT_BOUNDARY, B.QUESTION_ANSWER, B.TAKE_GAP),
    (K.RELATIVE_PAUSE_BAND, P.SHORT, P.VERY_LONG),
    (K.CONTENT_MODE, ContentMode.SPOKEN_CONTENT, ContentMode.UNSUPPORTED_NARRATIVE),
    (K.LOCAL_PAUSE_REFERENCE, LocalPauseReference(10), LocalPauseReference(20)),
])
def test_conflicting_values_never_choose_winner(kind, left, right):
    records = tuple(r for r in base_records() if r.kind != kind)
    a = record(kind, left, name='a')
    b = replace(record(kind, right, name='b'), strength=EvidenceStrength.WEAK,
                producer=replace(PRODUCER, producer_kind=ProducerKind.RULE))
    first = prepare_observation(bundle(records=records+(a,b)), SNAPSHOT)
    second = prepare_observation(bundle(records=records+(b,a)), SNAPSHOT)
    assert first == second and first.status == S.REVIEW_REQUIRED and first.conflicts


def test_qa_failed_take_and_present_absent_conflicts():
    result = prepare(record(K.QUESTION_ANSWER_BOUNDARY, B.QUESTION_ANSWER),
                     record(K.FAILED_TAKE_GAP_CUE))
    assert result.status == S.REVIEW_REQUIRED and result.conflicts
    result = prepare(record(K.EMOTIONAL_CUE, name='positive'),
                     record(K.EMOTIONAL_CUE, assertion=A.ABSENT, name='negative'))
    assert result.status == S.REVIEW_REQUIRED and result.conflicts


def test_no_editorial_inference_from_silence_duration_or_take_gap():
    records = tuple(r for r in base_records() if r.kind != K.TRANSCRIPT_BOUNDARY)
    raw = bundle(records=records+(record(K.TRANSCRIPT_BOUNDARY, B.TAKE_GAP),
                                 record(K.SILENCE_REGION)))
    assert prepare_observation(raw, SNAPSHOT).observation.signals == ()
    large = replace(raw, target_pause_range=FrameRange(20, 90))
    assert prepare_observation(large, SNAPSHOT).observation.signals == ()


@pytest.mark.parametrize('frames', [60, 61, 1000])
def test_unsafe_local_reference_not_repaired(frames):
    result = prepare(record(K.LOCAL_PAUSE_REFERENCE, LocalPauseReference(frames)))
    assert result.status == S.REVIEW_REQUIRED and result.observation is None
    assert R.UNSAFE_LOCAL_REFERENCE in result.reasons


@pytest.mark.parametrize('frames', [0, -1, True, 1.5])
def test_local_reference_requires_positive_integer(frames):
    with pytest.raises((TypeError, ValueError)):
        LocalPauseReference(frames)


def test_safe_local_reference_preserved():
    assert prepare(record(K.LOCAL_PAUSE_REFERENCE,
                          LocalPauseReference(10))).observation.local_reference_pause_frames == 10


@pytest.mark.parametrize('kind', [K.CONTENT_MODE, K.TRANSCRIPT_BOUNDARY, K.RELATIVE_PAUSE_BAND])
def test_missing_required_value_reviewed(kind):
    result = prepare_observation(bundle(records=tuple(r for r in base_records() if r.kind != kind)),
                                 SNAPSHOT)
    assert result.status == S.REVIEW_REQUIRED and R.MISSING_REQUIRED_VALUE in result.reasons


def test_unknown_contract_and_unsupported_content():
    assert prepare_observation(replace(bundle(), evidence_contract_version='future'),
                               SNAPSHOT).status == S.UNSUPPORTED
    records = tuple(r for r in base_records() if r.kind != K.CONTENT_MODE)
    assert prepare_observation(bundle(records=records+(record(
        K.CONTENT_MODE, ContentMode.UNSUPPORTED_NARRATIVE),)), SNAPSHOT).status == S.UNSUPPORTED


def test_cross_clip_missing_placement_and_overlap_not_ready():
    assert prepare_observation(replace(bundle(), target_pause_range=FrameRange(20, 110)),
                               SNAPSHOT).status == S.UNSUPPORTED
    assert prepare_observation(bundle(), replace(SNAPSHOT, tracks=(), relationship_graph=None)
                               ).status == S.UNSUPPORTED
    result = prepare(record(K.SPEAKER_OVERLAP))
    assert result.status == S.REVIEW_REQUIRED and result.observation is None


@pytest.mark.parametrize('kind,payload', [(K.CONTENT_MODE, {}), (K.RELATIVE_PAUSE_BAND, B.UNKNOWN),
    (K.TRANSCRIPT_BOUNDARY, P.UNKNOWN), (K.EMOTIONAL_CUE, PauseSignal.EMOTIONAL),
    (K.LOCAL_PAUSE_REFERENCE, 10)])
def test_authoritative_payload_is_typed(kind, payload):
    with pytest.raises(TypeError):
        record(kind, payload)


def test_no_classifier_authority_safety_or_executor_called(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Execution boundary crossed')
    monkeypatch.setattr(pause, 'classify_pause', forbidden)
    monkeypatch.setattr(authority, 'transition', forbidden)
    monkeypatch.setattr(safety, 'preflight', forbidden)
    monkeypatch.setattr(FakeTimeline, 'apply', forbidden)
    raw = bundle(record(K.EMOTIONAL_CUE))
    before = (raw, SNAPSHOT)
    assert prepare_observation(raw, SNAPSHOT) == prepare_observation(raw, SNAPSHOT)
    assert before == (raw, SNAPSHOT)
