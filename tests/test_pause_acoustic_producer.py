"""TEST_ONLY_SUPPORT PCM bytes exercise the detector, not real-media qualification."""

import ast
import inspect
import json
from dataclasses import asdict, replace
from fractions import Fraction
from struct import pack

import pytest
from test_observation_pipeline import REF, inputs

from davinci_ai_editor import evidence as e
from davinci_ai_editor import observation_pipeline as obs
from davinci_ai_editor import pause
from davinci_ai_editor import pause_acoustic_producer as p
from davinci_ai_editor.domain import ClipId, FrameRange, TimelineObjectId, TimelineVersion
from davinci_ai_editor.temporal_mapping import (
    FrameRate,
    MappingKind,
    MappingStatus,
    SourceFrameRange,
    TimelineFrameRange,
)


def config() -> p.AcousticConfig:
    return p.AcousticConfig(
        "pcm-frame-energy-v1", 0, 2, 200, 2, Fraction(1, 2), Fraction(3, 2), Fraction(3, 1)
    )


def pcm() -> p.PcmInput:
    _, link, _ = inputs()
    levels = [0 if 20 <= i < 24 or 50 <= i < 54 or 80 <= i < 96 else 100 for i in range(200)]
    data = b"".join(pack("<h", level) * 2 for level in levels)
    return p.PcmInput(
        data,
        "PCM16LE",
        48,
        1,
        0,
        SourceFrameRange(FrameRange(0, 200)),
        "TEST_ONLY_SUPPORT-pcm",
        link,
    )


def test_pcm_silence_is_evidence_not_semantics() -> None:
    native, _, _ = inputs()
    result = p.produce_pause_evidence(pcm(), config(), native, REF)
    assert not result.diagnostics
    silence = [r for r in result.records if r.kind == e.EvidenceKind.SILENCE_REGION]
    assert [r.binding.observed_range for r in silence] == [
        FrameRange(120, 124),
        FrameRange(150, 154),
        FrameRange(180, 196),
    ]
    assert all(isinstance(r.payload, e.Presence) for r in silence)
    assert all(s.candidate is None for s in result.preparation.subjects)


def analyze(
    value: p.PcmInput | None = None,
    policy: p.AcousticConfig | None = None,
    context: tuple[e.EvidenceRecord, ...] = (),
) -> p.AcousticResult:
    native, _, _ = inputs()
    return p.produce_pause_evidence(
        value or pcm(), policy or config(), native, REF, context=context
    )


def levels(values: list[int]) -> p.PcmInput:
    return replace(
        pcm(),
        data=b"".join(pack("<h", v) * 2 for v in values),
        source_range=SourceFrameRange(FrameRange(0, len(values))),
    )


def context_for(
    result: p.AcousticResult, *, question: bool = False
) -> tuple[e.EvidenceRecord, ...]:
    producer = e.ProducerRef(e.ProducerKind.HUMAN_SUPPLIED, "TEST_ONLY_SUPPORT-context", "v1", "v1")
    records: list[e.EvidenceRecord] = []
    for silence in (r for r in result.records if r.kind == e.EvidenceKind.SILENCE_REGION):
        for suffix, kind, payload in (
            ("mode", e.EvidenceKind.CONTENT_MODE, pause.ContentMode.SPOKEN_CONTENT),
            (
                "boundary",
                e.EvidenceKind.TRANSCRIPT_BOUNDARY,
                pause.PauseBoundaryKind.QUESTION_ANSWER
                if question
                else pause.PauseBoundaryKind.SENTENCE_BOUNDARY,
            ),
        ):
            records.append(
                e.EvidenceRecord(
                    silence.evidence_id + ":human:" + suffix,
                    silence.binding,
                    producer,
                    kind,
                    e.EvidenceAssertion.PRESENT,
                    e.EvidenceStrength.STRONG,
                    payload,
                )
            )
    return tuple(records)


@pytest.mark.parametrize(
    "case",
    [
        "negative-channel",
        "past-channel",
        "zero-channels",
        "format",
        "odd-byte",
        "short",
        "long",
        "rate-zero",
        "non-integral",
        "config",
    ],
)
def test_invalid_pcm_is_typed_unavailable_not_analyzed(case: str) -> None:
    value, policy = pcm(), config()
    assert value.data is not None
    original_data = value.data
    if case == "negative-channel":
        value = replace(value, selected_channel=-1)
    elif case == "past-channel":
        value = replace(value, selected_channel=1)
    elif case == "zero-channels":
        value = replace(value, channels=0)
    elif case == "format":
        value = replace(value, sample_format="FLOAT32")
    elif case == "odd-byte":
        value = replace(value, data=original_data + b"x")
    elif case == "short":
        value = replace(value, data=original_data[:-2])
    elif case == "long":
        value = replace(value, data=original_data + b"\x00\x00")
    elif case == "rate-zero":
        value = replace(value, sample_rate=0)
    elif case == "non-integral":
        value = replace(value, sample_rate=25)
    else:
        policy = replace(policy, version="future")
    result = analyze(value, policy)
    assert result.diagnostics
    assert result.preparation.coverage_status == obs.CoverageStatus.UNAVAILABLE
    assert result.records == () and result.preparation.subjects == ()
    if case == "non-integral":
        assert result.diagnostics == (p.PcmDiagnostic.NON_INTEGRAL_SAMPLES_PER_FRAME,)


def test_explicit_multichannel_selection_no_downmix() -> None:
    value = replace(pcm(), channels=2, data=pack("<hh", 1000, 0) * 400)
    assert analyze(value).records == ()
    selected = analyze(replace(value, selected_channel=1))
    assert [r.binding.observed_range for r in selected.records] == [FrameRange(100, 300)]
    assert selected.selected_channel == 1
    assert selected.producer.producer_kind == e.ProducerKind.RULE
    assert selected.producer.producer_config_ref == config().config_ref
    assert selected.source_ref == value.source_ref


def test_partial_interleaved_sample_frame_rejected() -> None:
    value = replace(pcm(), channels=2, data=pack("<h", 0))
    assert analyze(value).diagnostics == (p.PcmDiagnostic.MALFORMED_BYTES,)


@pytest.mark.parametrize("run_length,expected", [(1, 0), (2, 1), (3, 1)])
def test_minimum_silence_is_explicit_inclusive(run_length: int, expected: int) -> None:
    result = analyze(levels([100] * 2 + [0] * run_length + [100] * 2))
    silence = [r for r in result.records if r.kind == e.EvidenceKind.SILENCE_REGION]
    assert len(silence) == expected
    if silence:
        assert silence[0].binding.observed_range == FrameRange(102, 102 + run_length)


def test_no_gap_bridging_or_non_silence_speech_inference() -> None:
    result = analyze(levels([0, 0, 500, 0, 0]))
    assert [r.binding.observed_range for r in result.records] == [
        FrameRange(100, 102),
        FrameRange(103, 105),
    ]
    assert not any(r.kind == e.EvidenceKind.SPEECH_REGION for r in result.records)


def test_integer_mean_square_threshold_exact_equality_and_negative_pcm() -> None:
    value = replace(levels([0, 0]), data=pack("<hhhh", -1, 3, -1, 3))
    assert analyze(value, replace(config(), mean_square_threshold=4)).records == ()
    assert len(analyze(value, replace(config(), mean_square_threshold=5)).records) == 1
    assert analyze(levels([-32768, 32767])).records == ()


def test_semantic_result_deterministic_and_no_raw_pcm_retention() -> None:
    first, second = analyze(), analyze()
    assert first == second
    encoded = json.dumps(asdict(first), sort_keys=True, default=str).encode()
    assert encoded == json.dumps(asdict(second), sort_keys=True, default=str).encode()
    assert first.pcm_digest is not None and len(first.pcm_digest) == 64
    assert "data" not in asdict(first)
    assert all(not isinstance(r.payload, bytes) for r in first.records)
    assert all("\\x00" not in (r.note or "") for r in first.records)


@pytest.mark.parametrize(
    "forbidden",
    [
        e.EvidenceKind.CONTENT_MODE,
        e.EvidenceKind.TRANSCRIPT_BOUNDARY,
        e.EvidenceKind.QUESTION_ANSWER_BOUNDARY,
        e.EvidenceKind.SPEAKER_CHANGE,
        e.EvidenceKind.SPEAKER_OVERLAP,
        e.EvidenceKind.NATURAL_BREATH_CUE,
        e.EvidenceKind.HESITATION_CUE,
        e.EvidenceKind.THINKING_CUE,
        e.EvidenceKind.EMOTIONAL_CUE,
        e.EvidenceKind.RECORDING_DEAD_AIR_CUE,
        e.EvidenceKind.FAILED_TAKE_GAP_CUE,
        e.EvidenceKind.SPEECH_REGION,
    ],
)
def test_pcm_never_emits_semantic_or_speech_evidence(forbidden: e.EvidenceKind) -> None:
    for value in (pcm(), levels([0] * 200), levels([0] * 20 + [100] * 180)):
        result = analyze(value)
        assert all(r.kind != forbidden for r in result.records)
        assert all(s.candidate is None for s in result.preparation.subjects)


def test_local_population_excludes_current_and_retains_exact_sources() -> None:
    result = analyze()
    bands = [r for r in result.records if r.kind == e.EvidenceKind.RELATIVE_PAUSE_BAND]
    assert len(bands) == 3
    silence = [r for r in result.records if r.kind == e.EvidenceKind.SILENCE_REGION]
    for index, band in enumerate(bands):
        assert band.note is not None
        sources = json.loads(band.note)["neighbors"]
        assert sources == [r.evidence_id for j, r in enumerate(silence) if j != index]
    reference = [r for r in result.records if r.kind == e.EvidenceKind.LOCAL_PAUSE_REFERENCE]
    assert len(reference) == 1
    assert isinstance(reference[0].payload, e.LocalPauseReference)
    assert 0 < reference[0].payload.frames == 4 < reference[0].binding.observed_range.duration


@pytest.mark.parametrize(
    "policy",
    [replace(config(), minimum_neighbors=3), replace(config(), neighborhood_source_frames=1)],
)
def test_insufficient_declared_population_never_invents_timing(policy: p.AcousticConfig) -> None:
    assert {r.kind for r in analyze(policy=policy).records} == {e.EvidenceKind.SILENCE_REGION}


def test_thresholds_identify_policy_and_change_band_without_fixed_duration_meaning() -> None:
    original = analyze()
    changed_config = replace(config(), normal_ratio=Fraction(5), long_ratio=Fraction(6))
    changed = analyze(policy=changed_config)

    def bands(result: p.AcousticResult) -> list[e.EvidencePayload]:
        return [r.payload for r in result.records if r.kind == e.EvidenceKind.RELATIVE_PAUSE_BAND]

    assert bands(original)[-1] == pause.RelativePauseBand.VERY_LONG
    assert bands(changed)[-1] == pause.RelativePauseBand.NORMAL
    assert config().config_ref != changed_config.config_ref


def test_reference_is_local_statistic_not_global_fixed_target() -> None:
    result = analyze(levels([100] + [0] * 6 + [100] * 5 + [0] * 6 + [100] * 5 + [0] * 20 + [100]))
    refs = [r.payload for r in result.records if r.kind == e.EvidenceKind.LOCAL_PAUSE_REFERENCE]
    assert refs == [e.LocalPauseReference(6)]


def test_local_neighborhood_excludes_distant_pause_even_when_shorter() -> None:
    value = levels([100] + [0] * 4 + [100] * 6 + [0] * 8 + [100] * 60 + [0] * 2 + [100])
    result = analyze(value, replace(config(), minimum_neighbors=1, neighborhood_source_frames=20))
    refs = [r.payload for r in result.records if r.kind == e.EvidenceKind.LOCAL_PAUSE_REFERENCE]
    assert refs == [e.LocalPauseReference(4)]


def test_window_edge_runs_never_supply_or_receive_timing_claims() -> None:
    result = analyze(levels([0] * 4 + [100] * 4 + [0] * 8 + [100] * 4 + [0] * 4))
    assert len(result.records) == 3
    assert all(r.kind == e.EvidenceKind.SILENCE_REGION for r in result.records)


def test_rational_source_rate_has_exact_integer_sample_partition() -> None:
    native, link, _ = inputs()
    rate = FrameRate(30000, 1001)
    placement = replace(link.placement, timeline_rate=rate, source_rate=rate)
    native = replace(native, timeline_rate=rate, placements=(placement,))
    link = replace(
        link,
        placement=placement,
        binding=replace(link.binding, timeline_rate=rate, source_rate=rate),
    )
    value = replace(levels([0, 0]), link=link, sample_rate=30000, data=b"\x00\x00" * 2002)
    result = p.produce_pause_evidence(value, config(), native, REF)
    assert not result.diagnostics
    assert result.records[0].binding.observed_range == FrameRange(100, 102)


def test_repeated_media_native_order_does_not_change_explicit_pcm_placement() -> None:
    native, link, _ = inputs()
    second = replace(
        link.placement,
        object_ref=replace(link.placement.object_ref, ref="second-native"),
        timeline_range=TimelineFrameRange(FrameRange(400, 600)),
    )
    native = replace(
        native,
        placements=(second, link.placement),
        tracks=(
            replace(
                native.tracks[0], placement_refs=("second-native", link.placement.object_ref.ref)
            ),
        ),
    )
    result = p.produce_pause_evidence(pcm(), config(), native, REF)
    assert result.records == analyze().records
    assert result.preparation.links[0] == link


def test_partial_window_can_prepare_candidates_without_claiming_full_analysis() -> None:
    original = pcm()
    assert original.data is not None
    value = replace(
        original, data=original.data[:400], source_range=SourceFrameRange(FrameRange(0, 100))
    )
    result = analyze(value, context=context_for(analyze(value)))
    assert result.preparation.coverage_status == obs.CoverageStatus.PARTIALLY_ANALYZED
    assert result.preparation.subjects[-1].candidate is not None
    assert result.preparation.subjects[-1].candidate.action == pause.PauseAction.TIGHTEN


def test_unknown_context_never_becomes_absent_or_ready() -> None:
    context = context_for(analyze())
    unknown = replace(
        context[0],
        evidence_id="unknown-context",
        kind=e.EvidenceKind.EMOTIONAL_CUE,
        payload=e.Presence(),
        assertion=e.EvidenceAssertion.UNKNOWN,
    )
    subject = analyze(context=context + (unknown,)).preparation.subjects[0]
    assert subject.preparation is not None
    assert subject.preparation.status == e.PreparationStatus.REVIEW_REQUIRED
    assert unknown in subject.bundle.evidence
    assert subject.candidate is None


def test_external_context_allows_existing_classifier_tighten_and_reordering_is_stable() -> None:
    raw = analyze()
    context = context_for(raw)
    result = analyze(context=context)
    assert result == analyze(context=tuple(reversed(context)))
    subject = result.preparation.subjects[-1]
    assert subject.candidate is not None and subject.observation is not None
    assert subject.candidate == pause.classify_pause(subject.observation)
    assert subject.candidate.action == pause.PauseAction.TIGHTEN
    assert subject.candidate.suggested_retained_frames == 4
    assert {r.kind for r in result.records} == {
        e.EvidenceKind.SILENCE_REGION,
        e.EvidenceKind.RELATIVE_PAUSE_BAND,
        e.EvidenceKind.LOCAL_PAUSE_REFERENCE,
    }


def test_question_context_is_preserved_not_overridden_by_pcm() -> None:
    result = analyze(context=context_for(analyze(), question=True))
    assert all(
        s.candidate is not None and s.candidate.action == pause.PauseAction.KEEP
        for s in result.preparation.subjects
    )


def test_conflicting_context_keeps_existing_preparation_unresolved() -> None:
    context = context_for(analyze())
    boundary = next(r for r in context if r.kind == e.EvidenceKind.TRANSCRIPT_BOUNDARY)
    conflicting = replace(
        boundary, evidence_id="conflict", payload=pause.PauseBoundaryKind.TAKE_GAP
    )
    subject = analyze(context=context + (conflicting,)).preparation.subjects[0]
    assert (
        subject.preparation is not None
        and subject.preparation.status == e.PreparationStatus.REVIEW_REQUIRED
    )
    assert subject.candidate is None


def test_no_reference_defers_to_classifier_review_not_producer_decision() -> None:
    value = levels([0] * 40)
    raw = analyze(value)
    context = context_for(raw)
    band = replace(
        context[0],
        evidence_id="external-long",
        kind=e.EvidenceKind.RELATIVE_PAUSE_BAND,
        payload=pause.RelativePauseBand.LONG,
    )
    subject = analyze(value, context=context + (band,)).preparation.subjects[0]
    assert subject.candidate is not None and subject.candidate.action == pause.PauseAction.REVIEW


@pytest.mark.parametrize("case", ["unavailable", "not-evaluated", "zero", "partial", "stale"])
def test_coverage_meanings_remain_distinct(case: str) -> None:
    value, current = pcm(), REF
    native, _, _ = inputs()
    expected = obs.CoverageStatus.ANALYZED
    if case == "unavailable":
        value, expected = replace(value, data=None), obs.CoverageStatus.UNAVAILABLE
    elif case == "not-evaluated":
        expected = obs.CoverageStatus.NOT_EVALUATED
    elif case == "zero":
        value = levels([100] * 200)
    elif case == "partial":
        value, expected = levels([0, 0, 100, 100]), obs.CoverageStatus.PARTIALLY_ANALYZED
    else:
        current, expected = replace(REF, state_token="human-edit"), obs.CoverageStatus.STALE
    result = p.produce_pause_evidence(
        value, config(), native, current, analyze=case != "not-evaluated"
    )
    assert result.preparation.coverage_status == expected
    if case != "partial":
        assert result.preparation.subjects == ()
    assert value.link.binding.snapshot_ref == REF


def test_source_window_offset_uses_existing_mapping() -> None:
    value = replace(levels([0, 0]), source_range=SourceFrameRange(FrameRange(40, 42)))
    result = analyze(value)
    assert result.records[0].binding.observed_range == FrameRange(140, 142)
    assert all(m.status == MappingStatus.EXACT for m in result.mappings)
    assert result.preparation.coverage is not None
    assert result.preparation.coverage.covered_range == FrameRange(140, 142)


@pytest.mark.parametrize(
    "case", ["not-evaluated", "unavailable", "format", "channel", "rate", "config"]
)
def test_partial_requested_window_is_retained_on_early_stop(case: str) -> None:
    native, _, _ = inputs()
    value = replace(levels([0, 0]), source_range=SourceFrameRange(FrameRange(40, 42)))
    policy = config()
    if case == "unavailable":
        value = replace(value, data=None)
    elif case == "format":
        value = replace(value, sample_format="FLOAT32")
    elif case == "channel":
        value = replace(value, selected_channel=9)
    elif case == "rate":
        value = replace(value, sample_rate=0)
    elif case == "config":
        policy = replace(policy, version="future")
    result = p.produce_pause_evidence(value, policy, native, REF, analyze=case != "not-evaluated")
    assert result.preparation.coverage_status == (
        obs.CoverageStatus.NOT_EVALUATED
        if case == "not-evaluated"
        else obs.CoverageStatus.UNAVAILABLE
    )
    assert result.preparation.coverage is not None
    assert result.preparation.coverage.covered_range == FrameRange(140, 142)
    assert result.mappings[0].status == MappingStatus.EXACT
    assert result.records == () and result.preparation.subjects == ()


@pytest.mark.parametrize("analyze_requested", [False, True])
def test_unmappable_requested_window_is_explicit_not_full_placement_request(
    analyze_requested: bool,
) -> None:
    native, _, _ = inputs()
    value = replace(levels([0, 0]), data=None, source_range=SourceFrameRange(FrameRange(200, 202)))
    result = p.produce_pause_evidence(value, config(), native, REF, analyze=analyze_requested)
    assert result.diagnostics == (p.PcmDiagnostic.MAPPING_NOT_EXACT,)
    assert result.preparation.coverage_status == obs.CoverageStatus.UNAVAILABLE
    assert result.preparation.coverage is not None
    assert any(
        "not the requested window" in text for text in result.preparation.coverage.limitations
    )
    assert result.source_range == value.source_range
    assert result.mappings[0].status == MappingStatus.OUT_OF_RANGE
    assert result.records == ()


def test_source_outside_placement_or_nonexact_affine_never_emits_evidence() -> None:
    outside = replace(levels([0, 0]), source_range=SourceFrameRange(FrameRange(200, 202)))
    assert analyze(outside).diagnostics == (p.PcmDiagnostic.MAPPING_NOT_EXACT,)
    native, link, _ = inputs()
    source = SourceFrameRange(FrameRange(0, 300))
    placement = replace(link.placement, source_range=source, retime_kind=MappingKind.AFFINE_FORWARD)
    native = replace(native, placements=(placement,))
    link = replace(
        link,
        placement=placement,
        binding=replace(link.binding, source_range=source, mapping_kind=MappingKind.AFFINE_FORWARD),
    )
    result = p.produce_pause_evidence(replace(levels([0, 0]), link=link), config(), native, REF)
    assert result.diagnostics == (p.PcmDiagnostic.MAPPING_NOT_EXACT,)
    assert result.records == ()


def test_link_wrong_placement_does_not_select_similar_media() -> None:
    value = pcm()
    wrong = replace(
        value.link.binding,
        object_id=TimelineObjectId(value.link.binding.object_id.track_id, ClipId("other")),
    )
    # Explicit native link remains necessary: a nonexistent native identity cannot be inferred.
    native_placement = replace(
        value.link.placement, object_ref=replace(value.link.placement.object_ref, ref="not-present")
    )
    result = analyze(
        replace(value, link=replace(value.link, binding=wrong, placement=native_placement))
    )
    assert result.diagnostics == (p.PcmDiagnostic.OBS_BLOCKED,)
    assert result.records == ()


@pytest.mark.parametrize("case", ["version", "placement", "range", "duplicate"])
def test_context_is_never_retargeted(case: str) -> None:
    record = context_for(analyze())[0]
    if case == "version":
        record = replace(record, binding=replace(record.binding, base_version=TimelineVersion(99)))
    elif case == "placement":
        record = replace(
            record,
            binding=replace(
                record.binding,
                object_id=TimelineObjectId(record.binding.object_id.track_id, ClipId("other")),
            ),
        )
    elif case == "range":
        record = replace(
            record, binding=replace(record.binding, observed_range=FrameRange(121, 124))
        )
    result = analyze(context=(record, record) if case == "duplicate" else (record,))
    assert result.diagnostics == (p.PcmDiagnostic.CONTEXT_MISMATCH,)
    assert result.records  # Honest acoustic analysis survives invalid contextual composition.
    assert result.preparation.subjects == ()


def test_external_removal_evidence_is_not_pcm_inference_or_execution_authority() -> None:
    context = context_for(analyze())
    cue = replace(
        context[0],
        evidence_id="external-dead-air",
        kind=e.EvidenceKind.RECORDING_DEAD_AIR_CUE,
        payload=e.Presence(),
    )
    result = analyze(context=context + (cue,))
    subject = result.preparation.subjects[0]
    assert subject.candidate is not None and subject.candidate.action == pause.PauseAction.REMOVE
    assert all(r.kind != e.EvidenceKind.RECORDING_DEAD_AIR_CUE for r in result.records)
    assert not hasattr(result, "authorization") and not hasattr(result, "transaction")


def test_architecture_no_rounding_network_execution_or_classifier_reimplementation() -> None:
    tree = ast.parse(inspect.getsource(p))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {
        "hashlib",
        "json",
        "struct",
        "dataclasses",
        "enum",
        "fractions",
        "domain",
        "evidence",
        "native_snapshot",
        "observation_pipeline",
        "pause",
        "temporal_mapping",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"round", "float", "classify_pause", "prepare_observation"} & names
    assert not any(isinstance(node, ast.Div) for node in ast.walk(tree))
