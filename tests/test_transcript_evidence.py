"""TXE-001B transcript evidence contract tests (hand-written dicts; no ASR, no media)."""

import copy
import unicodedata
from fractions import Fraction

import pytest

from davinci_ai_editor.transcript import WordTimingStatus
from davinci_ai_editor.transcript_evidence import (
    AudioClock,
    ConfidenceKind,
    CoverageSpan,
    CoverageStatus,
    EvidenceWordTiming,
    IngestErrorCode,
    ProjectionDiagnosticCode,
    TranscriptEvidence,
    TranscriptEvidenceSegment,
    TranscriptEvidenceWord,
    TranscriptIngestError,
    TranscriptProducerRef,
    WordsStatus,
    ingest_faster_whisper,
    ingest_whisperx,
    project_to_source_frames,
)

CLOCK = AudioClock(decoded_sample_rate=16000, resampled=True, downmixed=True, window_offset_ms=0)


def producer(tool: str = "faster-whisper", language: str = "UNKNOWN") -> TranscriptProducerRef:
    return TranscriptProducerRef(
        tool=tool,
        tool_version="1.1.1",
        model_id="large-v3",
        model_revision=None,
        alignment_model_id="wav2vec2-ko" if tool == "whisperx" else None,
        vad_method=None,
        vad_config_digest=None,
        language_requested=None,
        language_detected=language,
        language_probability=None,
    )


def fw_payload() -> dict[str, object]:
    return {
        "language": "ko",
        "language_probability": 0.98,
        "segments": [
            {
                "id": 1,
                "start": 0.0,
                "end": 1.2,
                "text": " 안녕하세요 여러분",
                "avg_logprob": -0.25,
                "compression_ratio": 1.1,
                "no_speech_prob": 0.01,
                "words": [
                    {"start": 0.0, "end": 0.6, "word": " 안녕하세요", "probability": 0.9},
                    {"start": 0.6, "end": 1.2, "word": " 여러분", "probability": 0.75},
                ],
            },
            {
                "id": 2,
                "start": 1.5,
                "end": 2.0,
                "text": " 네",
                "avg_logprob": -0.5,
                "compression_ratio": 0.8,
                "no_speech_prob": 0.2,
                "words": None,
            },
        ],
    }


def wx_payload() -> dict[str, object]:
    return {
        "language": "ko",
        "segments": [
            {
                "start": 0.031,
                "end": 1.207,
                "text": "오늘 음 날씨",
                "words": [
                    {"word": "오늘", "start": 0.031, "end": 0.412, "score": 0.871},
                    {"word": "음", "start": 0.412, "end": 0.412},  # interpolated: no score
                    {"word": "날씨", "start": 0.5, "end": 1.207, "score": 0.66},
                ],
            },
            {"start": 1.5, "end": 2.25, "text": "123", "words": []},  # alignment failed
            {
                "start": 2.3,
                "end": 3.0,
                "text": "그리고 ...",
                "words": [
                    {"word": "그리고", "start": 2.3, "end": 2.7, "score": 0.5},
                    {"word": "..."},  # missing
                ],
            },
        ],
    }


def fw(payload: object) -> TranscriptEvidence:
    return ingest_faster_whisper(
        payload, evidence_id="ev-fw", source_ref="src-1", producer=producer(), clock=CLOCK
    )


def wx(payload: object) -> TranscriptEvidence:
    return ingest_whisperx(
        payload,
        evidence_id="ev-wx",
        source_ref="src-1",
        producer=producer("whisperx"),
        clock=CLOCK,
    )


def code_of(exc: pytest.ExceptionInfo[TranscriptIngestError]) -> IngestErrorCode:
    return exc.value.code


# ---------------------------------------------------------------- contracts


def test_clock_and_producer_validation() -> None:
    with pytest.raises(TypeError):
        AudioClock(16000, 1, True, 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AudioClock(0, True, True, 0)
    with pytest.raises(ValueError):
        AudioClock(16000, True, True, -10)
    with pytest.raises(ValueError):
        producer(language="")
    with pytest.raises(ValueError):
        TranscriptProducerRef("x", "1", "m", None, None, None, None, None, "ko", Fraction(3, 2))
    with pytest.raises(ValueError, match="UNKNOWN"):
        TranscriptProducerRef("x", "1", "m", None, None, None, None, None, "UNKNOWN", Fraction(1))


def test_word_contract_timing_and_confidence() -> None:
    with pytest.raises(ValueError):
        TranscriptEvidenceWord("a", None, 10, EvidenceWordTiming.ALIGNED, ConfidenceKind.NONE, None)
    with pytest.raises(ValueError):
        TranscriptEvidenceWord("a", 0, 10, EvidenceWordTiming.MISSING, ConfidenceKind.NONE, None)
    with pytest.raises(ValueError):
        TranscriptEvidenceWord("a", 20, 10, EvidenceWordTiming.ALIGNED, ConfidenceKind.NONE, None)
    with pytest.raises(ValueError):
        TranscriptEvidenceWord(
            "a", 0, 10, EvidenceWordTiming.ALIGNED, ConfidenceKind.NONE, Fraction(1, 2)
        )
    with pytest.raises(ValueError):
        TranscriptEvidenceWord(
            "a", 0, 10, EvidenceWordTiming.ALIGNED, ConfidenceKind.CTC_MEAN_SCORE, Fraction(2)
        )
    with pytest.raises(TypeError):
        TranscriptEvidenceWord(
            "a",
            0,
            10,
            "ALIGNED",  # type: ignore[arg-type]
            ConfidenceKind.NONE,
            None,
        )


def test_evidence_word_timing_mirrors_word_timing_status() -> None:
    assert [m.value for m in EvidenceWordTiming] == [m.value for m in WordTimingStatus]


def _seg(
    index: int, start: int, end: int, *words: TranscriptEvidenceWord
) -> TranscriptEvidenceSegment:
    return TranscriptEvidenceSegment(
        index, start, end, "x", WordsStatus.PRESENT, words, None, None, None
    )


def _w(start: int, end: int) -> TranscriptEvidenceWord:
    return TranscriptEvidenceWord(
        "x", start, end, EvidenceWordTiming.ALIGNED, ConfidenceKind.NONE, None
    )


def _ev(*segments: TranscriptEvidenceSegment, res: int = 10, coverage: object = None) -> object:
    return TranscriptEvidence(
        "ev",
        "src",
        producer(),
        CLOCK,
        res,
        segments,
        coverage,  # type: ignore[arg-type]
    )


def test_evidence_structural_validation() -> None:
    _ev(_seg(0, 0, 100, _w(0, 110)))  # within +resolution
    with pytest.raises(ValueError, match="outside its segment"):
        _ev(_seg(0, 0, 100, _w(0, 120)))
    with pytest.raises(ValueError, match="multiples"):
        _ev(_seg(0, 0, 105))
    with pytest.raises(ValueError, match="strictly increasing"):
        _ev(_seg(1, 0, 100), _seg(1, 100, 200))
    with pytest.raises(ValueError, match="non-decreasing start"):
        _ev(_seg(0, 100, 200), _seg(1, 0, 50))
    with pytest.raises(ValueError, match="nonoverlapping"):
        _ev(
            coverage=(
                CoverageSpan(0, 100, CoverageStatus.TRANSCRIBED),
                CoverageSpan(90, 200, CoverageStatus.VAD_EXCLUDED),
            )
        )
    with pytest.raises(ValueError, match="nonempty"):
        _ev(coverage=())
    with pytest.raises(ValueError):
        CoverageSpan(10, 10, CoverageStatus.NOT_EVALUATED)
    with pytest.raises(ValueError):
        TranscriptEvidenceSegment(0, 0, 10, " ", WordsStatus.ALIGNMENT_FAILED, (), None, None, None)
    with pytest.raises(ValueError):
        TranscriptEvidenceSegment(
            0, 0, 10, "a", WordsStatus.NOT_REQUESTED, (_w(0, 10),), None, None, None
        )


# ---------------------------------------------------------------- faster-whisper


def test_faster_whisper_ingest() -> None:
    ev = fw(fw_payload())
    assert ev.resolution_ms == 10
    assert ev.coverage is None
    assert ev.producer.language_detected == "ko"
    assert ev.producer.language_probability == Fraction(98, 100)
    seg0, seg1 = ev.segments
    assert seg0.segment_index == 1 and (seg0.start_ms, seg0.end_ms) == (0, 1200)
    assert seg0.words_status == WordsStatus.PRESENT
    assert [(w.start_ms, w.end_ms) for w in seg0.words] == [(0, 600), (600, 1200)]
    assert all(w.timing == EvidenceWordTiming.HEURISTIC_ADJUSTED for w in seg0.words)
    assert seg0.words[0].confidence_kind == ConfidenceKind.WHISPER_WORD_PROB
    assert seg0.words[0].confidence == Fraction(9, 10)
    assert seg0.avg_logprob == Fraction(-1, 4)
    assert seg1.words_status == WordsStatus.NOT_REQUESTED and seg1.words == ()


def test_faster_whisper_empty_words_is_alignment_failed() -> None:
    payload = fw_payload()
    payload["segments"][1]["words"] = []  # type: ignore[index]
    assert fw(payload).segments[1].words_status == WordsStatus.ALIGNMENT_FAILED


def test_empty_segments_is_evaluated_empty_result() -> None:
    ev = fw({"language": "ko", "language_probability": 0.5, "segments": []})
    assert ev.segments == () and ev.coverage is None


@pytest.mark.parametrize(
    ("path", "value", "code"),
    [
        (("segments", 0, "start"), float("nan"), IngestErrorCode.NON_FINITE),
        (("segments", 0, "end"), float("inf"), IngestErrorCode.NON_FINITE),
        (("segments", 0, "start"), True, IngestErrorCode.INVALID_TYPE),
        (("segments", 0, "words", 0, "probability"), False, IngestErrorCode.INVALID_TYPE),
        (("segments", 0, "start"), "0.0", IngestErrorCode.INVALID_TYPE),
        (("segments", 0, "start"), -0.01, IngestErrorCode.NEGATIVE),
        (("segments", 0, "words", 1, "start"), 0.1 + 0.2, IngestErrorCode.NOT_ON_RESOLUTION_GRID),
        (("segments", 0, "words", 1, "start"), 0.605, IngestErrorCode.NOT_ON_RESOLUTION_GRID),
        (("segments", 0, "words", 1, "end"), 1.5, IngestErrorCode.CONTRACT_VIOLATION),
        (("segments", 0, "id"), 1.0, IngestErrorCode.INVALID_TYPE),
        (("segments", 0, "words"), {"a": 1}, IngestErrorCode.INVALID_TYPE),
        (("segments", 0, "words", 0, "probability"), 1.5, IngestErrorCode.CONTRACT_VIOLATION),
        (("language",), "en", IngestErrorCode.CONTRACT_VIOLATION),
    ],
)
def test_faster_whisper_fail_closed(
    path: tuple[object, ...], value: object, code: IngestErrorCode
) -> None:
    payload = fw_payload()
    target: object = payload
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    if path == ("language",):
        # Mismatch only when the producer already declared a different language.
        p = producer(language="ko")
        with pytest.raises(TranscriptIngestError) as exc:
            ingest_faster_whisper(payload, evidence_id="e", source_ref="s", producer=p, clock=CLOCK)
        assert code_of(exc) == IngestErrorCode.LANGUAGE_MISMATCH
        return
    with pytest.raises(TranscriptIngestError) as exc:
        fw(payload)
    assert code_of(exc) == code


@pytest.mark.parametrize("payload", [[], "x", None, 3, {"segments": "abc"}, {1: 2}])
def test_unknown_top_level_types_refused(payload: object) -> None:
    with pytest.raises(TranscriptIngestError) as exc:
        fw(payload)
    assert code_of(exc) == IngestErrorCode.INVALID_TYPE


def test_missing_fields_and_producer_mismatch() -> None:
    with pytest.raises(TranscriptIngestError) as exc:
        fw({"language": "ko"})
    assert code_of(exc) == IngestErrorCode.MISSING_FIELD
    payload = fw_payload()
    del payload["segments"][0]["words"][0]["start"]  # type: ignore[index]
    with pytest.raises(TranscriptIngestError) as exc:
        fw(payload)
    assert code_of(exc) == IngestErrorCode.MISSING_FIELD
    with pytest.raises(TranscriptIngestError) as exc:
        ingest_faster_whisper(
            fw_payload(),
            evidence_id="e",
            source_ref="s",
            producer=producer("whisperx"),
            clock=CLOCK,
        )
    assert code_of(exc) == IngestErrorCode.PRODUCER_MISMATCH


def test_korean_text_is_nfc_normalized() -> None:
    payload = fw_payload()
    nfd = unicodedata.normalize("NFD", " 안녕하세요")
    assert nfd != " 안녕하세요"
    payload["segments"][0]["words"][0]["word"] = nfd  # type: ignore[index]
    payload["segments"][0]["text"] = unicodedata.normalize("NFD", " 안녕하세요 여러분")  # type: ignore[index]
    ev = fw(payload)
    assert ev.segments[0].words[0].text == " 안녕하세요"
    assert ev.segments[0].text == " 안녕하세요 여러분"


# ---------------------------------------------------------------- whisperX


def test_whisperx_ingest_statuses() -> None:
    ev = wx(wx_payload())
    assert ev.resolution_ms == 1
    seg0, seg1, seg2 = ev.segments
    assert [s.segment_index for s in ev.segments] == [0, 1, 2]
    aligned, interp, aligned2 = seg0.words
    assert aligned2.timing == EvidenceWordTiming.ALIGNED
    assert aligned.timing == EvidenceWordTiming.ALIGNED
    assert aligned.confidence_kind == ConfidenceKind.CTC_MEAN_SCORE
    assert aligned.confidence == Fraction(871, 1000)
    assert (aligned.start_ms, aligned.end_ms) == (31, 412)
    assert interp.timing == EvidenceWordTiming.INTERPOLATED
    assert interp.confidence_kind == ConfidenceKind.NONE and interp.confidence is None
    assert seg1.words_status == WordsStatus.ALIGNMENT_FAILED and seg1.words == ()
    assert seg2.words[1].timing == EvidenceWordTiming.MISSING
    assert seg2.words[1].start_ms is None and seg2.words[1].end_ms is None


def test_whisperx_half_timing_is_missing_not_completed() -> None:
    payload = wx_payload()
    payload["segments"][2]["words"][1] = {"word": "...", "start": 2.7}  # type: ignore[index]
    word = wx(payload).segments[2].words[1]
    assert word.timing == EvidenceWordTiming.MISSING and word.start_ms is None


def test_whisperx_missing_words_key_is_not_requested() -> None:
    ev = wx({"language": "ko", "segments": [{"start": 0.0, "end": 1.0, "text": "a"}]})
    assert ev.segments[0].words_status == WordsStatus.NOT_REQUESTED


def test_whisperx_out_of_segment_word_refused() -> None:
    payload = wx_payload()
    payload["segments"][0]["words"][2]["end"] = 1.209  # type: ignore[index]
    with pytest.raises(TranscriptIngestError) as exc:
        wx(payload)
    assert code_of(exc) == IngestErrorCode.CONTRACT_VIOLATION
    payload["segments"][0]["words"][2]["end"] = 1.208  # type: ignore[index]
    wx(payload)  # exactly +resolution is tolerated


def test_whisperx_sub_ms_precision_refused() -> None:
    payload = wx_payload()
    payload["segments"][0]["words"][0]["start"] = 0.0315  # type: ignore[index]
    with pytest.raises(TranscriptIngestError) as exc:
        wx(payload)
    assert code_of(exc) == IngestErrorCode.NOT_ON_RESOLUTION_GRID


def test_coverage_is_carried_when_declared() -> None:
    coverage = (
        CoverageSpan(0, 1500, CoverageStatus.TRANSCRIBED),
        CoverageSpan(1500, 2300, CoverageStatus.VAD_EXCLUDED),
        CoverageSpan(2300, 3000, CoverageStatus.TRANSCRIBED),
    )
    ev = ingest_whisperx(
        wx_payload(),
        evidence_id="e",
        source_ref="s",
        producer=producer("whisperx"),
        clock=CLOCK,
        coverage=coverage,
    )
    assert ev.coverage == coverage


# ---------------------------------------------------------------- projection


def test_projection_rounding_at_25_fps() -> None:
    projection = project_to_source_frames(
        fw(fw_payload()),
        frame_rate=Fraction(25),
        source_offset_frames=100,
        tolerance_frames=1,
        transcript_id="tx",
    )
    snap = projection.snapshot
    assert snap.producer_ref == "ev-fw" and snap.source_ref == "src-1"
    assert [w.word_ref for w in snap.words] == ["w000001", "w000002"]
    # 0..600 ms -> frames 0..15 ; 600..1200 ms -> 15..30 (exact grid, touching).
    assert [(w.source_range.frames.start, w.source_range.frames.end) for w in snap.words] == [  # type: ignore[union-attr]
        (100, 115),
        (115, 130),
    ]
    assert all(w.timing_status == WordTimingStatus.HEURISTIC_ADJUSTED for w in snap.words)
    codes = [d.code for d in projection.diagnostics]
    assert codes == [ProjectionDiagnosticCode.SEGMENT_WORDS_UNAVAILABLE]


def test_projection_ntsc_floor_ceil_and_overlap_rule() -> None:
    # 30000/1001 fps: 600 ms = 17.982 frames -> end ceil 18, next start floor 17.
    projection = project_to_source_frames(
        fw(fw_payload()),
        frame_rate=Fraction(30000, 1001),
        source_offset_frames=0,
        tolerance_frames=1,
        transcript_id="tx",
    )
    w1, w2 = projection.snapshot.words
    assert w1.timing_status == WordTimingStatus.UNKNOWN and w1.source_range is None
    assert w2.timing_status == WordTimingStatus.UNKNOWN and w2.source_range is None
    overlap = [
        d
        for d in projection.diagnostics
        if d.code == ProjectionDiagnosticCode.OVERLAP_AFTER_PROJECTION
    ]
    assert [(d.word_ref, d.start_ms, d.end_ms) for d in overlap] == [
        ("w000001", 0, 600),
        ("w000002", 600, 1200),
    ]
    assert (overlap[0].projected_start_frame, overlap[0].projected_end_frame) == (0, 18)
    assert (overlap[1].projected_start_frame, overlap[1].projected_end_frame) == (17, 36)
    assert overlap[0].related_word_refs == ("w000002",)


def test_projection_zero_length_becomes_missing_and_statuses_carry() -> None:
    projection = project_to_source_frames(
        wx(wx_payload()),
        frame_rate=Fraction(25),
        source_offset_frames=0,
        tolerance_frames=1,
        transcript_id="tx",
    )
    words = projection.snapshot.words
    # "음" 412..412 ms: floor(10.3)=10, ceil(10.3)=11 -> 1 frame, but it overlaps
    # "오늘" (0..11) -> UNKNOWN pair. 날씨 500..1207 -> 12..31 stays timed.
    assert [w.timing_status for w in words] == [
        WordTimingStatus.UNKNOWN,
        WordTimingStatus.UNKNOWN,
        WordTimingStatus.ALIGNED,
        WordTimingStatus.ALIGNED,
        WordTimingStatus.MISSING,
    ]
    assert words[2].source_range.frames.start == 12  # type: ignore[union-attr]
    # A zero-duration word exactly on the frame grid -> MISSING, never invented.
    payload = wx_payload()
    payload["segments"][0]["words"][1] = {"word": "음", "start": 0.44, "end": 0.44}  # type: ignore[index]
    projection = project_to_source_frames(
        wx(payload),
        frame_rate=Fraction(25),
        source_offset_frames=0,
        tolerance_frames=1,
        transcript_id="tx",
    )
    assert projection.snapshot.words[1].timing_status == WordTimingStatus.MISSING
    assert projection.snapshot.words[1].source_range is None
    zero = [
        d
        for d in projection.diagnostics
        if d.code == ProjectionDiagnosticCode.ZERO_LENGTH_AFTER_PROJECTION
    ]
    assert [(d.word_ref, d.projected_start_frame, d.projected_end_frame) for d in zero] == [
        ("w000002", 11, 11)
    ]


def test_projection_window_offset_and_tolerance_floor() -> None:
    clock = AudioClock(16000, True, True, window_offset_ms=1000)
    ev = ingest_faster_whisper(
        fw_payload(), evidence_id="e", source_ref="s", producer=producer(), clock=clock
    )
    snap = project_to_source_frames(
        ev, frame_rate=Fraction(25), source_offset_frames=0, tolerance_frames=1, transcript_id="t"
    ).snapshot
    assert snap.words[0].source_range.frames.start == 25  # type: ignore[union-attr]
    # 10 ms at 120 fps = 1.2 frames -> tolerance must be >= 2.
    with pytest.raises(ValueError, match="Tolerance"):
        project_to_source_frames(
            ev,
            frame_rate=Fraction(120),
            source_offset_frames=0,
            tolerance_frames=1,
            transcript_id="t",
        )
    with pytest.raises(ValueError):
        project_to_source_frames(
            ev,
            frame_rate=Fraction(0),
            source_offset_frames=0,
            tolerance_frames=1,
            transcript_id="t",
        )
    with pytest.raises(ValueError):
        project_to_source_frames(
            ev,
            frame_rate=Fraction(25),
            source_offset_frames=-1,
            tolerance_frames=1,
            transcript_id="t",
        )


def test_determinism() -> None:
    a = wx(copy.deepcopy(wx_payload()))
    b = wx(copy.deepcopy(wx_payload()))
    assert a == b
    kwargs = {
        "frame_rate": Fraction(30000, 1001),
        "source_offset_frames": 7,
        "tolerance_frames": 1,
        "transcript_id": "tx",
    }
    assert project_to_source_frames(a, **kwargs) == project_to_source_frames(b, **kwargs)  # type: ignore[arg-type]
