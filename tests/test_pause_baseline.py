from dataclasses import FrozenInstanceError, replace
from itertools import combinations, permutations, product

import pytest

from davinci_ai_editor.domain import (
    ClipId,
    FrameRange,
    TimelineId,
    TimelineObjectId,
    TimelineVersion,
    TrackId,
)
from davinci_ai_editor.pause import (
    CandidateRouting as Routing,
)
from davinci_ai_editor.pause import (
    Confidence,
    ContentMode,
    PauseCandidate,
    PauseObservation,
    classify_pause,
)
from davinci_ai_editor.pause import (
    DecisionReason as Reason,
)
from davinci_ai_editor.pause import (
    PauseAction as Action,
)
from davinci_ai_editor.pause import (
    PauseBoundaryKind as Boundary,
)
from davinci_ai_editor.pause import (
    PauseSignal as Signal,
)
from davinci_ai_editor.pause import (
    RelativePauseBand as Band,
)


def observation(**changes):
    return replace(
        PauseObservation(
            TimelineId("main"),
            TimelineVersion(42),
            TimelineObjectId(TrackId("A1"), ClipId("dialogue")),
            FrameRange(10, 110),
            Band.NORMAL,
            Boundary.SENTENCE_BOUNDARY,
            (),
            None,
            ContentMode.SPOKEN_CONTENT,
        ),
        **changes,
    )


def test_duration_alone_never_changes_ordinary_pause_into_edit():
    for band in Band:
        results = [
            classify_pause(
                observation(relative_pause_band=band, pause_range=FrameRange(10, 10 + n))
            )
            for n in (1, 10, 100, 10000)
        ]
        assert all(c.action not in (Action.REMOVE, Action.TIGHTEN) for c in results)
        assert len({(c.action, c.confidence, c.reasons) for c in results}) == 1


@pytest.mark.parametrize(
    "signal,reason",
    [
        (Signal.RECORDING_DEAD_AIR, Reason.EXPLICIT_DEAD_AIR),
        (Signal.FAILED_TAKE_GAP, Reason.FAILED_TAKE_GAP),
    ],
)
@pytest.mark.parametrize("duration", [1, 100, 10000])
def test_explicit_recording_gap_not_duration_causes_remove(signal, reason, duration):
    c = classify_pause(observation(signals=(signal,), pause_range=FrameRange(0, duration)))
    assert (c.action, c.confidence, c.routing_hint) == (
        Action.REMOVE,
        Confidence.HIGH,
        Routing.SHADOW_ELIGIBLE,
    )
    assert reason in c.reasons
    assert c.suggested_retained_frames is None


@pytest.mark.parametrize("signal", [Signal.EMOTIONAL, Signal.THINKING])
def test_meaningful_very_long_pause_kept(signal):
    c = classify_pause(
        observation(
            relative_pause_band=Band.VERY_LONG, signals=(signal,), local_reference_pause_frames=10
        )
    )
    assert (c.action, c.confidence) == (Action.KEEP, Confidence.HIGH)


@pytest.mark.parametrize("boundary", [Boundary.QUESTION_ANSWER, Boundary.SPEAKER_TRANSITION])
def test_boundary_preserves_long_pause(boundary):
    c = classify_pause(
        observation(
            relative_pause_band=Band.LONG, boundary_kind=boundary, local_reference_pause_frames=10
        )
    )
    assert (c.action, c.confidence) == (Action.KEEP, Confidence.HIGH)


@pytest.mark.parametrize("signals", [(), (Signal.NATURAL_BREATH,), (Signal.HESITATION,)])
@pytest.mark.parametrize("band", [Band.LONG, Band.VERY_LONG])
def test_long_context_uses_supplied_positive_target(signals, band):
    c = classify_pause(
        observation(signals=signals, relative_pause_band=band, local_reference_pause_frames=23)
    )
    assert (c.action, c.confidence) == (Action.TIGHTEN, Confidence.MEDIUM)
    assert c.suggested_retained_frames == 23
    assert c.routing_hint == Routing.BATCH_REVIEW
    assert Reason.RELATIVELY_LONG_PAUSE in c.reasons


@pytest.mark.parametrize("target", [None, -1, 0, 100, 101])
def test_missing_or_unsafe_target_fails_closed(target):
    c = classify_pause(
        observation(relative_pause_band=Band.LONG, local_reference_pause_frames=target)
    )
    assert c.action == Action.REVIEW
    assert Reason.NO_SAFE_TIGHTEN_TARGET in c.reasons
    assert c.suggested_retained_frames is None


@pytest.mark.parametrize(
    "signal", [Signal.EMOTIONAL, Signal.THINKING, Signal.NATURAL_BREATH, Signal.HESITATION]
)
@pytest.mark.parametrize("removal", [Signal.RECORDING_DEAD_AIR, Signal.FAILED_TAKE_GAP])
def test_conflicting_signals_have_no_automatic_priority(signal, removal):
    c = classify_pause(observation(signals=(signal, removal)))
    assert (c.action, c.confidence, c.routing_hint) == (
        Action.REVIEW,
        Confidence.MEDIUM,
        Routing.BATCH_REVIEW,
    )
    assert Reason.CONFLICTING_EVIDENCE in c.reasons


@pytest.mark.parametrize("boundary", [Boundary.QUESTION_ANSWER, Boundary.SPEAKER_TRANSITION])
def test_boundary_conflicts_with_dead_air(boundary):
    c = classify_pause(observation(signals=(Signal.RECORDING_DEAD_AIR,), boundary_kind=boundary))
    assert c.action == Action.REVIEW
    assert Reason.CONFLICTING_EVIDENCE in c.reasons


def test_emotional_hesitation_preserves_instead_of_removing():
    c = classify_pause(
        observation(signals=(Signal.EMOTIONAL, Signal.HESITATION), relative_pause_band=Band.LONG)
    )
    assert (c.action, c.confidence) == (Action.KEEP, Confidence.HIGH)


@pytest.mark.parametrize("band", [Band.SHORT, Band.NORMAL])
def test_natural_breath_and_ordinary_short_pacing_kept(band):
    for signals in ((), (Signal.NATURAL_BREATH,)):
        c = classify_pause(observation(relative_pause_band=band, signals=signals))
        assert (c.action, c.confidence, c.routing_hint) == (
            Action.KEEP,
            Confidence.HIGH,
            Routing.NO_CHANGE,
        )


def test_unknown_does_not_proactively_edit():
    cases = [
        observation(relative_pause_band=Band.UNKNOWN, boundary_kind=Boundary.UNKNOWN),
        observation(signals=(Signal.UNKNOWN, Signal.RECORDING_DEAD_AIR)),
        observation(
            relative_pause_band=Band.LONG,
            boundary_kind=Boundary.UNKNOWN,
            local_reference_pause_frames=10,
        ),
        observation(signals=(Signal.HESITATION,)),
    ]
    for obs in cases:
        c = classify_pause(obs)
        assert (c.action, c.confidence) == (Action.KEEP, Confidence.LOW)
        assert Reason.INSUFFICIENT_CONTEXT in c.reasons


def test_take_gap_or_very_long_alone_is_not_removal_evidence():
    c = classify_pause(
        observation(boundary_kind=Boundary.TAKE_GAP, relative_pause_band=Band.VERY_LONG)
    )
    assert c.action == Action.REVIEW


def test_explicit_dead_air_needs_no_invented_band_or_boundary():
    c = classify_pause(
        observation(
            signals=(Signal.RECORDING_DEAD_AIR,),
            relative_pause_band=Band.UNKNOWN,
            boundary_kind=Boundary.UNKNOWN,
        )
    )
    assert (c.action, c.confidence) == (Action.REMOVE, Confidence.HIGH)


@pytest.mark.parametrize("mode", [ContentMode.UNKNOWN, ContentMode.UNSUPPORTED_NARRATIVE])
def test_scope_overrides_explicit_edit_evidence(mode):
    c = classify_pause(observation(content_mode=mode, signals=(Signal.RECORDING_DEAD_AIR,)))
    assert (c.action, c.confidence) == (Action.REVIEW, Confidence.LOW)
    assert c.reasons == (Reason.UNSUPPORTED_CONTENT_SCOPE,)


def test_schema_routing_is_metadata_even_for_high_tighten():
    obs = observation(local_reference_pause_frames=20)
    c = PauseCandidate(obs, Action.TIGHTEN, Confidence.HIGH, (Reason.NATURAL_BREATH,), 20)
    assert c.routing_hint == Routing.SHADOW_ELIGIBLE
    assert not hasattr(c, "apply") and not hasattr(c, "approved")
    assert not hasattr(c, "edit_plan")


def test_signals_are_canonical_immutable_and_classifier_deterministic():
    supplied = [Signal.EMOTIONAL, Signal.HESITATION, Signal.EMOTIONAL]
    obs = observation(signals=supplied)
    supplied.clear()
    expected = classify_pause(obs)
    for perm in permutations((Signal.EMOTIONAL, Signal.HESITATION)):
        assert classify_pause(replace(obs, signals=perm)) == expected
    assert classify_pause(obs) == expected
    assert len(obs.signals) == 2
    with pytest.raises(FrozenInstanceError):
        obs.base_version = 50
    with pytest.raises(FrozenInstanceError):
        expected.action = Action.REMOVE
    with pytest.raises(FrozenInstanceError):
        expected.observation.pause_range = FrameRange(0, 1)


def test_existing_executors_and_authority_never_called(monkeypatch):
    from davinci_ai_editor import authority, safety
    from davinci_ai_editor.fake_timeline import FakeTimeline

    def forbidden(*args, **kwargs):
        raise AssertionError("Execution or authority integration is outside TASK-007")

    monkeypatch.setattr(FakeTimeline, "apply", forbidden)
    monkeypatch.setattr(safety, "preflight", forbidden)
    monkeypatch.setattr(authority, "transition", forbidden)
    for band, signal in product(Band, Signal):
        classify_pause(
            observation(
                relative_pause_band=band, signals=(signal,), local_reference_pause_frames=10
            )
        )


@pytest.mark.parametrize("target", [True, 2.0, "2"])
def test_noninteger_reference_rejected(target):
    with pytest.raises(TypeError):
        observation(local_reference_pause_frames=target)


@pytest.mark.parametrize(
    "field,value",
    [
        ("relative_pause_band", "LONG"),
        ("boundary_kind", "TAKE_GAP"),
        ("content_mode", "SPOKEN_CONTENT"),
        ("signals", ("EMOTIONAL",)),
        ("base_version", True),
        ("object_id", "clip"),
        ("pause_range", (0, 100)),
    ],
)
def test_invalid_observation_types_reject(field, value):
    with pytest.raises(TypeError):
        observation(**{field: value})


@pytest.mark.parametrize(
    "action,confidence,target",
    [
        (Action.REMOVE, Confidence.LOW, None),
        (Action.REMOVE, Confidence.MEDIUM, None),
        (Action.TIGHTEN, Confidence.LOW, 10),
        (Action.TIGHTEN, Confidence.MEDIUM, 0),
        (Action.TIGHTEN, Confidence.MEDIUM, 100),
        (Action.TIGHTEN, Confidence.MEDIUM, 11),
        (Action.KEEP, Confidence.HIGH, 10),
        (Action.REVIEW, Confidence.MEDIUM, 10),
    ],
)
def test_invalid_candidate_shapes_reject(action, confidence, target):
    with pytest.raises(ValueError):
        PauseCandidate(
            observation(local_reference_pause_frames=10),
            action,
            confidence,
            (Reason.NO_SAFE_TIGHTEN_TARGET,),
            target,
        )


def test_systematic_combinations_never_remove_without_uncontested_explicit_evidence():
    sets = [subset for size in range(len(Signal) + 1) for subset in combinations(Signal, size)]
    for band, boundary, signals in product(Band, Boundary, sets):
        obs = observation(
            relative_pause_band=band,
            boundary_kind=boundary,
            signals=signals,
            local_reference_pause_frames=10,
        )
        c = classify_pause(obs)
        if c.action == Action.REMOVE:
            assert set(signals) & {Signal.RECORDING_DEAD_AIR, Signal.FAILED_TAKE_GAP}
            assert not set(signals) & {
                Signal.EMOTIONAL,
                Signal.THINKING,
                Signal.NATURAL_BREATH,
                Signal.HESITATION,
                Signal.UNKNOWN,
            }
            assert boundary not in (Boundary.QUESTION_ANSWER, Boundary.SPEAKER_TRANSITION)
            assert c.confidence == Confidence.HIGH
        if c.action == Action.TIGHTEN:
            assert 0 < c.suggested_retained_frames < obs.pause_range.duration
            assert c.suggested_retained_frames == obs.local_reference_pause_frames
            assert band in (Band.LONG, Band.VERY_LONG)
            assert c.confidence == Confidence.MEDIUM


def test_same_media_like_placement_names_never_merge_observation_identity():
    first = observation()
    second = replace(first, object_id=TimelineObjectId(TrackId("A2"), first.object_id.clip_id))
    a, b = classify_pause(first), classify_pause(second)
    assert a.observation == first and b.observation == second
    assert a != b
    assert (a.action, a.confidence) == (b.action, b.confidence)


def test_reasons_are_defensively_canonicalized():
    reasons = [Reason.NATURAL_BREATH, Reason.NORMAL_LOCAL_PACING, Reason.NATURAL_BREATH]
    c = PauseCandidate(observation(), Action.KEEP, Confidence.HIGH, reasons)
    reasons.clear()
    assert c.reasons == (Reason.NATURAL_BREATH, Reason.NORMAL_LOCAL_PACING)


@pytest.mark.parametrize("changes", [{"timeline_id": ""}, {"base_version": -1}])
def test_empty_identity_or_negative_version_rejected(changes):
    with pytest.raises(ValueError):
        observation(**changes)


def test_same_context_safe_reference_gives_same_tighten_target_across_durations():
    for length in (30, 100, 10000):
        c = classify_pause(
            observation(
                relative_pause_band=Band.LONG,
                pause_range=FrameRange(0, length),
                local_reference_pause_frames=20,
            )
        )
        assert (c.action, c.suggested_retained_frames) == (Action.TIGHTEN, 20)
