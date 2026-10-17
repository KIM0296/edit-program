"""Millisecond-domain ASR transcript evidence: producer output, never editorial meaning.

This module holds what an external ASR tool *said*, on the tool's own clock, and
nothing more. It never runs an ASR tool, never imports one, never touches media,
the network or Resolve. Ingest functions accept plain JSON-like mappings such as
a serializer would produce from faster-whisper / whisperX output.

Clock warning: both faster-whisper and whisperX decode, resample and downmix the
input to 16 kHz mono before inference. Their timestamps therefore live on a
different clock than the source decode used by compressed-source acquisition
(CSA-001 forbids resampling/downmix). A transcript timestamp can never map EXACT
onto source frames; :func:`project_to_source_frames` always widens to the frame
grid and carries an explicit tolerance.

Nothing here emits PauseBoundaryKind, PauseSignal, ContentMode or any filler /
hesitation / breath label (OPEN-009 stays open). ``VAD_EXCLUDED`` coverage is a
statement about the producer's voice-activity filter, NOT a statement that the
audio is silent.
"""

import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from itertools import pairwise

from .domain import FrameRange
from .temporal_mapping import SourceFrameRange
from .transcript import TranscriptSnapshot, TranscriptWord, WordTimingStatus

UNKNOWN_LANGUAGE = "UNKNOWN"
FASTER_WHISPER_TOOL = "faster-whisper"
WHISPERX_TOOL = "whisperx"
# faster-whisper rounds word timestamps (and VAD-restored times) to 2 decimals:
# faster_whisper/transcribe.py add_word_timestamps ``round(time_offset + ..., 2)``
# and faster_whisper/vad.py SpeechTimestampsMap.get_original_time (time_precision=2).
FASTER_WHISPER_RESOLUTION_MS = 10
# whisperX rounds character / VAD-segment times to 3 decimals:
# whisperx/alignment.py ``round(char_seg.start * ratio + t1, 3)`` and whisperx/asr.py.
WHISPERX_RESOLUTION_MS = 1


def _nonblank(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value


def _optional_nonblank(value: object, message: str) -> None:
    if value is not None:
        _nonblank(value, message)


def _ms(value: object, message: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(message)
    return value


def _fraction_in(value: object, low: Fraction | None, high: Fraction | None, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, Fraction):
        raise TypeError(f"Exact Fraction or explicit None required for {name}")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"{name} out of range")


class EvidenceWordTiming(str, Enum):
    """Mirror of :class:`WordTimingStatus`: how the producer obtained a timing."""

    ALIGNED = "ALIGNED"
    HEURISTIC_ADJUSTED = "HEURISTIC_ADJUSTED"
    INTERPOLATED = "INTERPOLATED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


_TIMED_EVIDENCE = frozenset(
    {
        EvidenceWordTiming.ALIGNED,
        EvidenceWordTiming.HEURISTIC_ADJUSTED,
        EvidenceWordTiming.INTERPOLATED,
    }
)


class ConfidenceKind(str, Enum):
    """What a confidence number is. Values of different kinds are not comparable,
    and none of them is calibrated."""

    WHISPER_WORD_PROB = "WHISPER_WORD_PROB"
    CTC_MEAN_SCORE = "CTC_MEAN_SCORE"
    NONE = "NONE"


class WordsStatus(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PRESENT = "PRESENT"
    ALIGNMENT_FAILED = "ALIGNMENT_FAILED"


class CoverageStatus(str, Enum):
    """Producer coverage of the decoded window.

    VAD_EXCLUDED means the producer's VAD filter skipped the span; it is NOT
    evidence of silence, pause or non-speech.
    """

    TRANSCRIBED = "TRANSCRIBED"
    VAD_EXCLUDED = "VAD_EXCLUDED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class TranscriptProducerRef:
    """Exact producer identity. ``language_detected`` may be the explicit
    ``"UNKNOWN"`` but never empty; nothing here authenticates these facts."""

    tool: str
    tool_version: str
    model_id: str
    model_revision: str | None
    alignment_model_id: str | None
    vad_method: str | None
    vad_config_digest: str | None
    language_requested: str | None
    language_detected: str
    language_probability: Fraction | None

    def __post_init__(self) -> None:
        _nonblank(self.tool, "Explicit producer tool required")
        _nonblank(self.tool_version, "Explicit producer tool version required")
        _nonblank(self.model_id, "Explicit model ID required")
        for value, name in (
            (self.model_revision, "model revision"),
            (self.alignment_model_id, "alignment model ID"),
            (self.vad_method, "VAD method"),
            (self.vad_config_digest, "VAD config digest"),
            (self.language_requested, "requested language"),
        ):
            _optional_nonblank(value, f"{name} must be nonblank when present")
        _nonblank(self.language_detected, "Detected language or explicit UNKNOWN required")
        _fraction_in(self.language_probability, Fraction(0), Fraction(1), "language probability")
        if self.language_detected == UNKNOWN_LANGUAGE and self.language_probability is not None:
            raise ValueError("UNKNOWN detected language cannot carry a probability")


@dataclass(frozen=True)
class AudioClock:
    """The producer's decode clock, which is NOT the source decode clock.

    Both supported tools resample and downmix to 16 kHz mono, so a transcript
    clock can never map EXACT to source frames. ``window_offset_ms`` is where the
    producer's decoded window starts, in ms from the start of the source audio.
    """

    decoded_sample_rate: int
    resampled: bool
    downmixed: bool
    window_offset_ms: int

    def __post_init__(self) -> None:
        if type(self.decoded_sample_rate) is not int or self.decoded_sample_rate <= 0:
            raise ValueError("Positive integer decoded sample rate required")
        if type(self.resampled) is not bool or type(self.downmixed) is not bool:
            raise TypeError("Explicit boolean resample/downmix facts required")
        _ms(self.window_offset_ms, "Nonnegative integer window offset (ms) required")


@dataclass(frozen=True)
class TranscriptEvidenceWord:
    """One producer word in integer ms on the producer clock.

    Timed statuses require both ``start_ms`` and ``end_ms``; MISSING/UNKNOWN
    require both to be None (a half timing is never kept or completed).
    """

    text: str
    start_ms: int | None
    end_ms: int | None
    timing: EvidenceWordTiming
    confidence_kind: ConfidenceKind
    confidence: Fraction | None

    def __post_init__(self) -> None:
        text = _nonblank(self.text, "Nonblank word text required")
        object.__setattr__(self, "text", unicodedata.normalize("NFC", text))
        if not isinstance(self.timing, EvidenceWordTiming):
            raise TypeError("Typed evidence word timing required")
        if not isinstance(self.confidence_kind, ConfidenceKind):
            raise TypeError("Typed confidence kind required")
        timed = self.timing in _TIMED_EVIDENCE
        if timed:
            start = _ms(self.start_ms, "Timed word requires nonnegative integer start_ms")
            end = _ms(self.end_ms, "Timed word requires nonnegative integer end_ms")
            if start > end:
                raise ValueError("Word start_ms must not exceed end_ms")
        elif self.start_ms is not None or self.end_ms is not None:
            raise ValueError("MISSING/UNKNOWN timing forbids start_ms/end_ms")
        if (self.confidence_kind == ConfidenceKind.NONE) != (self.confidence is None):
            raise ValueError("Confidence value present iff confidence kind is not NONE")
        _fraction_in(self.confidence, Fraction(0), Fraction(1), "confidence")

    @property
    def is_timed(self) -> bool:
        return self.timing in _TIMED_EVIDENCE


@dataclass(frozen=True)
class TranscriptEvidenceSegment:
    segment_index: int
    start_ms: int
    end_ms: int
    text: str
    words_status: WordsStatus
    words: tuple[TranscriptEvidenceWord, ...]
    avg_logprob: Fraction | None
    no_speech_prob: Fraction | None
    compression_ratio: Fraction | None

    def __post_init__(self) -> None:
        if type(self.segment_index) is not int or self.segment_index < 0:
            raise ValueError("Nonnegative integer segment index required")
        start = _ms(self.start_ms, "Nonnegative integer segment start_ms required")
        end = _ms(self.end_ms, "Nonnegative integer segment end_ms required")
        if start > end:
            raise ValueError("Segment start_ms must not exceed end_ms")
        if not isinstance(self.text, str):
            raise TypeError("Segment text must be a string")
        object.__setattr__(self, "text", unicodedata.normalize("NFC", self.text))
        if not isinstance(self.words_status, WordsStatus):
            raise TypeError("Typed words status required")
        object.__setattr__(self, "words", tuple(self.words))
        if any(not isinstance(w, TranscriptEvidenceWord) for w in self.words):
            raise TypeError("Typed evidence words required")
        if self.words_status != WordsStatus.PRESENT and self.words:
            raise ValueError("NOT_REQUESTED/ALIGNMENT_FAILED segments carry no words")
        if self.words_status == WordsStatus.ALIGNMENT_FAILED and not self.text.strip():
            raise ValueError("ALIGNMENT_FAILED requires nonblank segment text")
        _fraction_in(self.avg_logprob, None, Fraction(0), "avg_logprob")
        _fraction_in(self.no_speech_prob, Fraction(0), Fraction(1), "no_speech_prob")
        _fraction_in(self.compression_ratio, Fraction(0), None, "compression_ratio")


@dataclass(frozen=True)
class CoverageSpan:
    start_ms: int
    end_ms: int
    status: CoverageStatus

    def __post_init__(self) -> None:
        start = _ms(self.start_ms, "Nonnegative integer coverage start_ms required")
        end = _ms(self.end_ms, "Nonnegative integer coverage end_ms required")
        if start >= end:
            raise ValueError("Coverage span must be nonempty")
        if not isinstance(self.status, CoverageStatus):
            raise TypeError("Typed coverage status required")


@dataclass(frozen=True)
class TranscriptEvidence:
    """Producer transcript for one source on the producer clock.

    ``coverage=None`` means the producer coverage was not declared (unknown); it
    is never inferred from segments. An empty segment tuple is an evaluated,
    empty result, which differs from not-evaluated coverage.
    """

    evidence_id: str
    source_ref: str
    producer: TranscriptProducerRef
    clock: AudioClock
    resolution_ms: int
    segments: tuple[TranscriptEvidenceSegment, ...]
    coverage: tuple[CoverageSpan, ...] | None
    # Input locations whose float value was snapped to the resolution grid
    # (noise within GRID_SNAP_EPSILON_MS only). Kept so the snap is auditable.
    grid_snaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonblank(self.evidence_id, "Explicit evidence ID required")
        object.__setattr__(self, "grid_snaps", tuple(self.grid_snaps))
        if any(not isinstance(g, str) or not g.strip() for g in self.grid_snaps):
            raise ValueError("Grid snap locations must be nonblank strings")
        _nonblank(self.source_ref, "Explicit source reference required")
        if not isinstance(self.producer, TranscriptProducerRef):
            raise TypeError("Typed producer reference required")
        if not isinstance(self.clock, AudioClock):
            raise TypeError("Typed audio clock required")
        if type(self.resolution_ms) is not int or self.resolution_ms <= 0:
            raise ValueError("Positive integer resolution_ms required")
        res = self.resolution_ms
        object.__setattr__(self, "segments", tuple(self.segments))
        if any(not isinstance(s, TranscriptEvidenceSegment) for s in self.segments):
            raise TypeError("Typed evidence segments required")
        for a, b in pairwise(self.segments):
            if b.segment_index <= a.segment_index:
                raise ValueError("Segment indices must be strictly increasing")
            if b.start_ms < a.start_ms:
                raise ValueError("Segments must be in non-decreasing start order")
        timed_starts: list[int] = []
        for seg in self.segments:
            values = [seg.start_ms, seg.end_ms]
            for w in seg.words:
                if w.start_ms is None or w.end_ms is None:
                    continue
                if w.start_ms < seg.start_ms - res or w.end_ms > seg.end_ms + res:
                    raise ValueError("Word outside its segment (beyond resolution_ms)")
                values += [w.start_ms, w.end_ms]
                timed_starts.append(w.start_ms)
            if any(v % res for v in values):
                raise ValueError("Timed values must be exact multiples of resolution_ms")
        if any(b < a for a, b in pairwise(timed_starts)):
            raise ValueError("Timed words must be in non-decreasing start order")
        if self.coverage is not None:
            object.__setattr__(self, "coverage", tuple(self.coverage))
            spans = self.coverage
            if not spans:
                raise ValueError("Declared coverage must be nonempty; use None for undeclared")
            if any(not isinstance(c, CoverageSpan) for c in spans):
                raise TypeError("Typed coverage spans required")
            if any(c.start_ms % res or c.end_ms % res for c in spans):
                raise ValueError("Coverage bounds must be exact multiples of resolution_ms")
            if any(b.start_ms < a.end_ms for a, b in pairwise(spans)):
                raise ValueError("Coverage spans must be ordered and nonoverlapping")


# --------------------------------------------------------------------------- ingest


class IngestErrorCode(str, Enum):
    INVALID_TYPE = "INVALID_TYPE"
    MISSING_FIELD = "MISSING_FIELD"
    NON_FINITE = "NON_FINITE"
    NEGATIVE = "NEGATIVE"
    NOT_ON_RESOLUTION_GRID = "NOT_ON_RESOLUTION_GRID"
    PRODUCER_MISMATCH = "PRODUCER_MISMATCH"
    LANGUAGE_MISMATCH = "LANGUAGE_MISMATCH"
    CONTRACT_VIOLATION = "CONTRACT_VIOLATION"


class TranscriptIngestError(ValueError):
    """Typed fail-closed ingest refusal."""

    def __init__(self, code: IngestErrorCode, detail: str) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: IngestErrorCode, detail: str) -> TranscriptIngestError:
    return TranscriptIngestError(code, detail)


def _mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise _fail(IngestErrorCode.INVALID_TYPE, f"{where} must be a string-keyed mapping")
    return value


def _list(value: object, where: str) -> Sequence[object]:
    if not isinstance(value, list | tuple):
        raise _fail(IngestErrorCode.INVALID_TYPE, f"{where} must be a list")
    return value


def _required(obj: Mapping[str, object], key: str, where: str) -> object:
    if key not in obj:
        raise _fail(IngestErrorCode.MISSING_FIELD, f"{where}.{key} missing")
    return obj[key]


def _decimal(value: object, where: str) -> Decimal:
    # bool is an int subclass; JSON true/false must never become 1/0.
    if type(value) is bool or not isinstance(value, int | float):
        raise _fail(IngestErrorCode.INVALID_TYPE, f"{where} must be a JSON number")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:  # pragma: no cover - str(int|float) always parses
        raise _fail(IngestErrorCode.INVALID_TYPE, f"{where} is not a number") from exc
    if not number.is_finite():
        raise _fail(IngestErrorCode.NON_FINITE, f"{where} must be finite")
    return number


def _fraction(value: object, where: str) -> Fraction | None:
    if value is None:
        return None
    return Fraction(_decimal(value, where))


# Binary floating-point noise tolerance for grid snapping (1 microsecond).
# Producers round to their resolution and may then add offsets in float
# arithmetic (e.g. 0.30000000000000004 s); such noise is ~1e-11 ms. Anything
# farther than this from the resolution grid is a real off-grid value and is
# refused, never rounded.
GRID_SNAP_EPSILON_MS = Decimal("0.001")


def _time_ms(value: object, resolution_ms: int, where: str, snaps: list[str]) -> int:
    seconds = _decimal(value, where)
    if seconds < 0:
        raise _fail(IngestErrorCode.NEGATIVE, f"{where} must be nonnegative")
    millis = seconds * 1000
    nearest = (millis / resolution_ms).to_integral_value() * resolution_ms
    if abs(millis - nearest) > GRID_SNAP_EPSILON_MS:
        raise _fail(
            IngestErrorCode.NOT_ON_RESOLUTION_GRID,
            f"{where}={value!r} is not a multiple of {resolution_ms} ms",
        )
    if millis != nearest:
        snaps.append(where)
    return int(nearest)


def _text(value: object, where: str) -> str:
    if not isinstance(value, str):
        raise _fail(IngestErrorCode.INVALID_TYPE, f"{where} must be a string")
    return value


def _resolve_producer(
    producer: TranscriptProducerRef,
    expected_tool: str,
    language: object,
    language_probability: Fraction | None,
) -> TranscriptProducerRef:
    if not isinstance(producer, TranscriptProducerRef):
        raise _fail(IngestErrorCode.INVALID_TYPE, "Typed producer reference required")
    if producer.tool != expected_tool:
        raise _fail(IngestErrorCode.PRODUCER_MISMATCH, f"producer.tool must be {expected_tool}")
    if language is None:
        if language_probability is not None:
            raise _fail(IngestErrorCode.CONTRACT_VIOLATION, "Language probability without language")
        return producer
    detected = _text(language, "payload.language")
    if not detected.strip():
        raise _fail(IngestErrorCode.INVALID_TYPE, "payload.language must be nonblank")
    if producer.language_detected not in (UNKNOWN_LANGUAGE, detected):
        raise _fail(IngestErrorCode.LANGUAGE_MISMATCH, "producer/payload detected language differ")
    if (
        producer.language_probability is not None
        and language_probability is not None
        and producer.language_probability != language_probability
    ):
        raise _fail(IngestErrorCode.LANGUAGE_MISMATCH, "producer/payload probability differ")
    probability = (
        language_probability
        if language_probability is not None
        else (producer.language_probability if producer.language_detected == detected else None)
    )
    try:
        return replace(producer, language_detected=detected, language_probability=probability)
    except (TypeError, ValueError) as exc:
        raise _fail(IngestErrorCode.CONTRACT_VIOLATION, str(exc)) from exc


def _build(
    *,
    evidence_id: str,
    source_ref: str,
    producer: TranscriptProducerRef,
    clock: AudioClock,
    resolution_ms: int,
    segments: list[TranscriptEvidenceSegment],
    coverage: Sequence[CoverageSpan] | None,
    grid_snaps: Sequence[str],
) -> TranscriptEvidence:
    try:
        return TranscriptEvidence(
            evidence_id=evidence_id,
            source_ref=source_ref,
            producer=producer,
            clock=clock,
            resolution_ms=resolution_ms,
            segments=tuple(segments),
            coverage=None if coverage is None else tuple(coverage),
            grid_snaps=tuple(grid_snaps),
        )
    except (TypeError, ValueError) as exc:
        raise _fail(IngestErrorCode.CONTRACT_VIOLATION, str(exc)) from exc


def _segment(**kwargs: object) -> TranscriptEvidenceSegment:
    try:
        return TranscriptEvidenceSegment(**kwargs)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise _fail(IngestErrorCode.CONTRACT_VIOLATION, str(exc)) from exc


def _word(**kwargs: object) -> TranscriptEvidenceWord:
    try:
        return TranscriptEvidenceWord(**kwargs)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise _fail(IngestErrorCode.CONTRACT_VIOLATION, str(exc)) from exc


def ingest_faster_whisper(
    payload: object,
    *,
    evidence_id: str,
    source_ref: str,
    producer: TranscriptProducerRef,
    clock: AudioClock,
    coverage: Sequence[CoverageSpan] | None = None,
) -> TranscriptEvidence:
    """Ingest a serialized faster-whisper result (the tool is never imported).

    Word timings are HEURISTIC_ADJUSTED: faster-whisper's
    ``WhisperModel.add_word_timestamps`` (faster_whisper/transcribe.py) clamps
    long words around sentence-end marks and re-anchors first/last words using
    ``median_duration``/``max_duration`` heuristics. Confidence is the per-word
    Whisper probability. ``words: null`` -> NOT_REQUESTED; ``words: []`` with
    nonblank text -> ALIGNMENT_FAILED (no word is invented). Resolution 10 ms.
    """
    snaps: list[str] = []
    res = FASTER_WHISPER_RESOLUTION_MS
    top = _mapping(payload, "payload")
    language_probability = _fraction(
        top.get("language_probability"), "payload.language_probability"
    )
    resolved = _resolve_producer(
        producer, FASTER_WHISPER_TOOL, top.get("language"), language_probability
    )
    segments: list[TranscriptEvidenceSegment] = []
    for i, raw in enumerate(_list(_required(top, "segments", "payload"), "payload.segments")):
        where = f"segments[{i}]"
        seg = _mapping(raw, where)
        index = _required(seg, "id", where)
        if type(index) is not int:
            raise _fail(IngestErrorCode.INVALID_TYPE, f"{where}.id must be an integer")
        text = _text(_required(seg, "text", where), f"{where}.text")
        raw_words = seg.get("words")
        words: list[TranscriptEvidenceWord] = []
        if raw_words is None:
            status = WordsStatus.NOT_REQUESTED
        else:
            items = _list(raw_words, f"{where}.words")
            status = (
                WordsStatus.ALIGNMENT_FAILED if not items and text.strip() else WordsStatus.PRESENT
            )
            for j, raw_word in enumerate(items):
                wwhere = f"{where}.words[{j}]"
                w = _mapping(raw_word, wwhere)
                words.append(
                    _word(
                        text=_text(_required(w, "word", wwhere), f"{wwhere}.word"),
                        start_ms=_time_ms(
                            _required(w, "start", wwhere), res, f"{wwhere}.start", snaps
                        ),
                        end_ms=_time_ms(_required(w, "end", wwhere), res, f"{wwhere}.end", snaps),
                        timing=EvidenceWordTiming.HEURISTIC_ADJUSTED,
                        confidence_kind=ConfidenceKind.WHISPER_WORD_PROB,
                        confidence=_fraction(
                            _required(w, "probability", wwhere), f"{wwhere}.probability"
                        ),
                    )
                )
        segments.append(
            _segment(
                segment_index=index,
                start_ms=_time_ms(_required(seg, "start", where), res, f"{where}.start", snaps),
                end_ms=_time_ms(_required(seg, "end", where), res, f"{where}.end", snaps),
                text=text,
                words_status=status,
                words=tuple(words),
                avg_logprob=_fraction(seg.get("avg_logprob"), f"{where}.avg_logprob"),
                no_speech_prob=_fraction(seg.get("no_speech_prob"), f"{where}.no_speech_prob"),
                compression_ratio=_fraction(
                    seg.get("compression_ratio"), f"{where}.compression_ratio"
                ),
            )
        )
    return _build(
        evidence_id=evidence_id,
        source_ref=source_ref,
        producer=resolved,
        clock=clock,
        resolution_ms=res,
        segments=segments,
        coverage=coverage,
        grid_snaps=snaps,
    )


def ingest_whisperx(
    payload: object,
    *,
    evidence_id: str,
    source_ref: str,
    producer: TranscriptProducerRef,
    clock: AudioClock,
    coverage: Sequence[CoverageSpan] | None = None,
) -> TranscriptEvidence:
    """Ingest a serialized whisperX aligned result (the tool is never imported).

    whisperx/alignment.py ``align``: a word whose characters were all
    unalignable has no ``score``; its ``start``/``end`` are then silently filled
    by ``interpolate_nans`` (default method "nearest"). Hence:
    no start/end -> MISSING; start+end without score -> INTERPOLATED;
    with score -> ALIGNED (CTC_MEAN_SCORE). A failed segment alignment keeps
    ``"words": []`` -> ALIGNMENT_FAILED. Missing/null ``words`` -> NOT_REQUESTED.
    Resolution 1 ms.
    """
    snaps: list[str] = []
    res = WHISPERX_RESOLUTION_MS
    top = _mapping(payload, "payload")
    resolved = _resolve_producer(producer, WHISPERX_TOOL, top.get("language"), None)
    segments: list[TranscriptEvidenceSegment] = []
    for i, raw in enumerate(_list(_required(top, "segments", "payload"), "payload.segments")):
        where = f"segments[{i}]"
        seg = _mapping(raw, where)
        text = _text(_required(seg, "text", where), f"{where}.text")
        raw_words = seg.get("words")
        words: list[TranscriptEvidenceWord] = []
        if raw_words is None:
            status = WordsStatus.NOT_REQUESTED
        else:
            items = _list(raw_words, f"{where}.words")
            status = (
                WordsStatus.ALIGNMENT_FAILED if not items and text.strip() else WordsStatus.PRESENT
            )
            for j, raw_word in enumerate(items):
                wwhere = f"{where}.words[{j}]"
                w = _mapping(raw_word, wwhere)
                start = w.get("start")
                end = w.get("end")
                score = _fraction(w.get("score"), f"{wwhere}.score")
                kind = ConfidenceKind.NONE if score is None else ConfidenceKind.CTC_MEAN_SCORE
                start_ms: int | None = None
                end_ms: int | None = None
                if start is None or end is None:
                    timing = EvidenceWordTiming.MISSING
                    # A half timing is validated but never kept or completed.
                    for value, name in ((start, "start"), (end, "end")):
                        if value is not None:
                            _time_ms(value, res, f"{wwhere}.{name}", snaps)
                else:
                    start_ms = _time_ms(start, res, f"{wwhere}.start", snaps)
                    end_ms = _time_ms(end, res, f"{wwhere}.end", snaps)
                    timing = (
                        EvidenceWordTiming.INTERPOLATED
                        if score is None
                        else EvidenceWordTiming.ALIGNED
                    )
                words.append(
                    _word(
                        text=_text(_required(w, "word", wwhere), f"{wwhere}.word"),
                        start_ms=start_ms,
                        end_ms=end_ms,
                        timing=timing,
                        confidence_kind=kind,
                        confidence=score,
                    )
                )
        segments.append(
            _segment(
                segment_index=i,
                start_ms=_time_ms(_required(seg, "start", where), res, f"{where}.start", snaps),
                end_ms=_time_ms(_required(seg, "end", where), res, f"{where}.end", snaps),
                text=text,
                words_status=status,
                words=tuple(words),
                avg_logprob=_fraction(seg.get("avg_logprob"), f"{where}.avg_logprob"),
                no_speech_prob=None,
                compression_ratio=None,
            )
        )
    return _build(
        evidence_id=evidence_id,
        source_ref=source_ref,
        producer=resolved,
        clock=clock,
        resolution_ms=res,
        segments=segments,
        coverage=coverage,
        grid_snaps=snaps,
    )


# ----------------------------------------------------------------------- projection


class ProjectionDiagnosticCode(str, Enum):
    ZERO_LENGTH_AFTER_PROJECTION = "ZERO_LENGTH_AFTER_PROJECTION"
    OVERLAP_AFTER_PROJECTION = "OVERLAP_AFTER_PROJECTION"
    SEGMENT_WORDS_UNAVAILABLE = "SEGMENT_WORDS_UNAVAILABLE"


@dataclass(frozen=True)
class ProjectionDiagnostic:
    """Why a projected word lost its range; the producer timing is kept here."""

    code: ProjectionDiagnosticCode
    segment_index: int
    word_ref: str | None
    start_ms: int | None
    end_ms: int | None
    projected_start_frame: int | None
    projected_end_frame: int | None
    related_word_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.code, ProjectionDiagnosticCode):
            raise TypeError("Typed diagnostic code required")
        object.__setattr__(self, "related_word_refs", tuple(self.related_word_refs))


@dataclass(frozen=True)
class TranscriptProjection:
    snapshot: TranscriptSnapshot
    diagnostics: tuple[ProjectionDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, TranscriptSnapshot):
            raise TypeError("Typed transcript snapshot required")
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if any(not isinstance(d, ProjectionDiagnostic) for d in self.diagnostics):
            raise TypeError("Typed projection diagnostics required")


def _frames(ms: int, frame_rate: Fraction) -> Fraction:
    return Fraction(ms) * frame_rate / 1000


def project_to_source_frames(
    evidence: TranscriptEvidence,
    *,
    frame_rate: Fraction,
    source_offset_frames: int,
    tolerance_frames: int,
    transcript_id: str,
) -> TranscriptProjection:
    """Project ms evidence onto source frames, widening and never shifting.

    Producer time ``t`` maps to source time ``clock.window_offset_ms + t`` ms;
    ``source_offset_frames`` is the source frame at source time 0. Start uses
    floor, end uses ceil on the frame grid, so a range only widens (<= 1 frame
    per side). Rules (each emits a diagnostic, never a moved boundary):

    * zero-length after projection -> MISSING, ``source_range=None``;
    * any projected timed words that overlap (e.g. touching ms boundaries split
      by floor/ceil, or overlapping producer timings) -> every word of the
      overlapping group becomes UNKNOWN, ``source_range=None``; their producer
      ms timings and projected frames stay in the diagnostic;
    * NOT_REQUESTED / ALIGNMENT_FAILED segments -> no words, one diagnostic.

    ``tolerance_frames`` must be >= ceil(resolution_ms expressed in frames).
    """
    if not isinstance(evidence, TranscriptEvidence):
        raise TypeError("Typed transcript evidence required")
    if not isinstance(frame_rate, Fraction) or frame_rate <= 0:
        raise ValueError("Positive exact Fraction frame rate required")
    if type(source_offset_frames) is not int or source_offset_frames < 0:
        raise ValueError("Nonnegative integer source offset (frames) required")
    if type(tolerance_frames) is not int or tolerance_frames < 0:
        raise ValueError("Nonnegative integer tolerance (frames) required")
    minimum = math.ceil(_frames(evidence.resolution_ms, frame_rate))
    if tolerance_frames < minimum:
        raise ValueError(f"Tolerance must be >= {minimum} frames (producer resolution)")
    _nonblank(transcript_id, "Explicit transcript ID required")

    offset = evidence.clock.window_offset_ms
    diagnostics: list[ProjectionDiagnostic] = []
    # (ref, text, segment_index, evidence word, projected range or None, status)
    rows: list[
        tuple[str, str, int, TranscriptEvidenceWord, tuple[int, int] | None, WordTimingStatus]
    ] = []
    ordinal = 0
    for seg in evidence.segments:
        if seg.words_status != WordsStatus.PRESENT:
            diagnostics.append(
                ProjectionDiagnostic(
                    ProjectionDiagnosticCode.SEGMENT_WORDS_UNAVAILABLE,
                    seg.segment_index,
                    None,
                    seg.start_ms,
                    seg.end_ms,
                    None,
                    None,
                )
            )
            continue
        for w in seg.words:
            ordinal += 1
            ref = f"w{ordinal:06d}"
            status = WordTimingStatus(w.timing.value)
            projected: tuple[int, int] | None = None
            if w.start_ms is not None and w.end_ms is not None:
                start = source_offset_frames + math.floor(_frames(offset + w.start_ms, frame_rate))
                end = source_offset_frames + math.ceil(_frames(offset + w.end_ms, frame_rate))
                if end <= start:
                    diagnostics.append(
                        ProjectionDiagnostic(
                            ProjectionDiagnosticCode.ZERO_LENGTH_AFTER_PROJECTION,
                            seg.segment_index,
                            ref,
                            w.start_ms,
                            w.end_ms,
                            start,
                            end,
                        )
                    )
                    status = WordTimingStatus.MISSING
                else:
                    projected = (start, end)
            rows.append((ref, w.text, seg.segment_index, w, projected, status))

    # Overlap groups: timed starts are non-decreasing (evidence invariant and floor
    # is monotonic), so an active sweep finds every overlapping pair.
    overlapping: dict[int, set[int]] = {}
    active: list[int] = []
    for idx, row in enumerate(rows):
        rng = row[4]
        if rng is None:
            continue
        active = [a for a in active if (r := rows[a][4]) is not None and r[1] > rng[0]]
        for a in active:
            overlapping.setdefault(a, set()).add(idx)
            overlapping.setdefault(idx, set()).add(a)
        active.append(idx)

    words: list[TranscriptWord] = []
    for idx, (ref, text, seg_index, w, rng, status) in enumerate(rows):
        source_range: SourceFrameRange | None = None
        if idx in overlapping and rng is not None:
            diagnostics.append(
                ProjectionDiagnostic(
                    ProjectionDiagnosticCode.OVERLAP_AFTER_PROJECTION,
                    seg_index,
                    ref,
                    w.start_ms,
                    w.end_ms,
                    rng[0],
                    rng[1],
                    tuple(rows[o][0] for o in sorted(overlapping[idx])),
                )
            )
            status = WordTimingStatus.UNKNOWN
        elif rng is not None:
            source_range = SourceFrameRange(FrameRange(rng[0], rng[1]))
        words.append(TranscriptWord(ref, text, source_range, status))

    snapshot = TranscriptSnapshot(
        transcript_id=transcript_id,
        source_ref=evidence.source_ref,
        producer_ref=evidence.evidence_id,
        timing_tolerance_frames=tolerance_frames,
        words=tuple(words),
    )
    return TranscriptProjection(snapshot, tuple(diagnostics))
