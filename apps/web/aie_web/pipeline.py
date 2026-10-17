"""Pure wiring of the public core modules for the Free web flow (no web framework here).

Everything is re-derived deterministically from the stored inputs (transcript
JSON + media facts + policy) on every request, so digests shown to the user are
always recomputed from the same content and nothing is cached as authority.

Axes stay separate: candidates are proposals only; a marker rename in Resolve
is a SELECTION; the confirmation page is a CONFIRMATION; only the posted
``confirmation_digest`` is the APPROVAL; the applied file is an unverified
Expected artifact; VER-001 on the re-export is the VERIFICATION.
"""

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from fractions import Fraction
from pathlib import PurePosixPath, PureWindowsPath

from davinci_ai_editor.apply_cuts import (
    SKIP_LABELS_KO,
    AppliedTimeline,
    ApplyConfirmation,
    ApplyRefused,
    apply_approved_cuts,
    build_apply_confirmation,
)
from davinci_ai_editor.candidate_markers import (
    MAX_REASON_CHARS,
    CandidateHandoff,
    CutCandidate,
    MarkerSelectionSet,
    attach_candidate_markers,
    read_marker_selections,
)
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffDiagnostic,
    HandoffMediaRef,
    HandoffSeverity,
    HandoffSubtitleCue,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
)
from davinci_ai_editor.korean_text_candidates import (
    KoreanTextCandidatePolicy,
    produce_korean_text_candidates,
)
from davinci_ai_editor.otio_json import OtioProfile, write_otio
from davinci_ai_editor.roundtrip_diff import (
    DiffStatus,
    RoundTripDiff,
    RoundTripFormat,
    diff_xmeml_roundtrip,
    roundtrip_artifact_ref,
)
from davinci_ai_editor.roundtrip_verification import (
    ActualProvenance,
    VerificationReport,
    verify_roundtrip,
)
from davinci_ai_editor.subtitle_io import write_srt
from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.timecode import (
    SMPTE_RATES,
    frames_to_seconds,
    frames_to_timecode,
    parse_timecode,
)
from davinci_ai_editor.transcript import TranscriptSnapshot, TranscriptTokenKind
from davinci_ai_editor.transcript_evidence import (
    AudioClock,
    ProjectionDiagnosticCode,
    TranscriptEvidence,
    TranscriptIngestError,
    TranscriptProducerRef,
    ingest_faster_whisper,
    ingest_whisperx,
    project_to_source_frames,
)
from davinci_ai_editor.xmeml_reader import XmemlReadResult, read_xmeml
from davinci_ai_editor.xmeml_writer import write_xmeml

GAP_POLICY_VERSION = "WEB-001-TRANSCRIPT-GAP-V1"
MAX_NAME_CHARS = 80
MAX_PATH_CHARS = 1024
MAX_DURATION_HOURS = 24
_CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")


class PipelineError(ValueError):
    """A user-facing refusal. ``message`` is Korean; ``codes`` are English diagnostics."""

    def __init__(self, message: str, codes: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.codes = codes


class Profile(str, Enum):
    RESOLVE = "RESOLVE"
    GENERIC = "GENERIC"


class AsrTool(str, Enum):
    FASTER_WHISPER = "faster-whisper"
    WHISPERX = "whisperx"


class CandidateKind(str, Enum):
    FILLER = "FILLER"
    REPETITION = "REPETITION"
    TRANSCRIPT_GAP = "TRANSCRIPT_GAP"


KIND_LABELS_KO = {
    CandidateKind.FILLER: "필러 후보",
    CandidateKind.REPETITION: "반복 후보",
    CandidateKind.TRANSCRIPT_GAP: "전사 공백 후보",
}

RATE_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (
        f"{r.numerator}/{r.denominator}",
        (
            f"{float(Fraction(r.numerator, r.denominator)):.3f}".rstrip("0").rstrip(".")
            + (" (NTSC)" if r.denominator == 1001 else "")
        ),
    )
    for r in SMPTE_RATES
)


# --------------------------------------------------------------------------- inputs


def clean_text(value: str, limit: int) -> str:
    """NFC, control characters -> space, trimmed, bounded."""
    text = _CONTROL.sub(" ", unicodedata.normalize("NFC", value)).strip()
    return text[:limit]


def parse_rate(value: str) -> FrameRate:
    for rate in SMPTE_RATES:
        if value == f"{rate.numerator}/{rate.denominator}":
            return rate
    raise PipelineError(
        "프레임레이트는 목록에서 선택해야 합니다 (추정하지 않습니다).", ("UNKNOWN_RATE",)
    )


def rate_key(rate: FrameRate) -> str:
    return f"{rate.numerator}/{rate.denominator}"


def parse_frame_or_timecode(value: str, rate: FrameRate, label: str) -> int | None:
    """Empty -> None (UNKNOWN). Digits -> frames. ``HH:MM:SS:FF`` -> frames."""
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        frames, _ = parse_timecode(text, rate)
    except ValueError as exc:
        raise PipelineError(
            f"{label}: 프레임 수(정수) 또는 HH:MM:SS:FF 타임코드를 입력하세요.", ("BAD_TIMECODE",)
        ) from exc
    return frames


@dataclass(frozen=True)
class MediaFacts:
    """What the user tells us about the media, exactly as Resolve sees it. Never guessed."""

    media_path: str
    rate: FrameRate
    duration_frames: int
    media_start_frame: int | None
    profile: Profile
    timeline_name: str
    timeline_start_frame: int

    def __post_init__(self) -> None:
        if not self.media_path or len(self.media_path) > MAX_PATH_CHARS:
            raise PipelineError("미디어 파일 경로를 입력하세요 (Resolve에서 보이는 경로).")
        if "://" in self.media_path:
            raise PipelineError("URL이 아닌 파일 시스템 경로를 입력하세요.", ("UNSUPPORTED_PATH",))
        limit = MAX_DURATION_HOURS * 3600 * math.ceil(self.rate.numerator / self.rate.denominator)
        if not 0 < self.duration_frames <= limit:
            raise PipelineError("미디어 길이(프레임)는 1 이상, 24시간 이하의 정수여야 합니다.")
        if self.profile is Profile.RESOLVE and self.media_start_frame is None:
            raise PipelineError(
                "Resolve 프로필에는 미디어 시작 타임코드(또는 프레임)가 필요합니다. "
                "0으로 가정하지 않습니다. Resolve의 클립 속성(Start TC)에서 확인해 입력하세요.",
                ("MEDIA_START_UNKNOWN",),
            )
        if not self.timeline_name:
            raise PipelineError("타임라인 이름을 입력하세요.")

    @property
    def media_id(self) -> str:
        return "media-" + hashlib.sha256(self.media_path.encode("utf-8")).hexdigest()[:12]

    @property
    def clip_name(self) -> str:
        path = PureWindowsPath(self.media_path) if "\\" in self.media_path else None
        name = path.name if path is not None else PurePosixPath(self.media_path).name
        return name or "clip"

    def to_json(self) -> dict[str, object]:
        return {
            "media_path": self.media_path,
            "rate": rate_key(self.rate),
            "duration_frames": self.duration_frames,
            "media_start_frame": self.media_start_frame,
            "profile": self.profile.value,
            "timeline_name": self.timeline_name,
            "timeline_start_frame": self.timeline_start_frame,
        }

    @classmethod
    def from_json(cls, data: dict[str, object]) -> "MediaFacts":
        start = data["media_start_frame"]
        duration = data["duration_frames"]
        tl_start = data["timeline_start_frame"]
        if not isinstance(duration, int) or not isinstance(tl_start, int):
            raise PipelineError("저장된 프로젝트 정보가 손상되었습니다.")
        if start is not None and not isinstance(start, int):
            raise PipelineError("저장된 프로젝트 정보가 손상되었습니다.")
        return cls(
            media_path=str(data["media_path"]),
            rate=parse_rate(str(data["rate"])),
            duration_frames=duration,
            media_start_frame=start,
            profile=Profile(str(data["profile"])),
            timeline_name=str(data["timeline_name"]),
            timeline_start_frame=tl_start,
        )


@dataclass(frozen=True)
class TranscriptSource:
    tool: AsrTool
    tool_version: str
    model_id: str
    offset_ms: int
    gap_seconds: str  # policy threshold as entered (decimal string)

    def to_json(self) -> dict[str, object]:
        return {
            "tool": self.tool.value,
            "tool_version": self.tool_version,
            "model_id": self.model_id,
            "offset_ms": self.offset_ms,
            "gap_seconds": self.gap_seconds,
        }

    @classmethod
    def from_json(cls, data: dict[str, object]) -> "TranscriptSource":
        offset = data["offset_ms"]
        if not isinstance(offset, int):
            raise PipelineError("저장된 프로젝트 정보가 손상되었습니다.")
        return cls(
            AsrTool(str(data["tool"])),
            str(data["tool_version"]),
            str(data["model_id"]),
            offset,
            str(data["gap_seconds"]),
        )


def parse_gap_seconds(value: str) -> Decimal:
    try:
        seconds = Decimal(value.strip() or "1.0")
    except InvalidOperation as exc:
        raise PipelineError("전사 공백 기준(초)은 숫자여야 합니다.") from exc
    if not seconds.is_finite() or not Decimal("0.2") <= seconds <= Decimal(30):
        raise PipelineError("전사 공백 기준(초)은 0.2 ~ 30 사이여야 합니다.")
    return seconds


@dataclass(frozen=True)
class CandidatePolicy:
    """Frame thresholds derived from the rate. Versioned; shown on the candidate page."""

    tolerance_frames: int
    gap_threshold_frames: int
    gap_padding_frames: int
    max_repetition_gap_frames: int
    version: str = GAP_POLICY_VERSION


def _seconds_to_frames(seconds: Decimal, rate: FrameRate) -> int:
    value = Fraction(seconds) * Fraction(rate.numerator, rate.denominator)
    return math.ceil(value)


def candidate_policy(
    source: TranscriptSource, rate: FrameRate, resolution_ms: int
) -> CandidatePolicy:
    minimum = math.ceil(Fraction(resolution_ms) * Fraction(rate.numerator, rate.denominator) / 1000)
    tolerance = max(1, minimum)
    return CandidatePolicy(
        tolerance_frames=tolerance,
        gap_threshold_frames=_seconds_to_frames(parse_gap_seconds(source.gap_seconds), rate),
        gap_padding_frames=max(tolerance, _seconds_to_frames(Decimal("0.1"), rate)),
        max_repetition_gap_frames=_seconds_to_frames(Decimal("0.3"), rate),
    )


# --------------------------------------------------------------------------- transcript


def parse_transcript_json(raw: bytes) -> object:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PipelineError("전사 파일은 UTF-8 JSON이어야 합니다.", ("NOT_UTF8",)) from exc
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise PipelineError(
            "전사 JSON 형식이 올바르지 않습니다. faster-whisper 또는 whisperX 결과 JSON을 올려 주세요.",
            ("MALFORMED_JSON",),
        ) from exc


def _reject_constant(name: str) -> object:
    raise ValueError(f"non-finite constant {name}")


def ingest(
    payload: object, source: TranscriptSource, facts: MediaFacts, raw_sha: str
) -> TranscriptEvidence:
    producer = TranscriptProducerRef(
        tool=source.tool.value,
        tool_version=source.tool_version or "UNDECLARED",
        model_id=source.model_id or "UNDECLARED",
        model_revision=None,
        alignment_model_id=None,
        vad_method=None,
        vad_config_digest=None,
        language_requested=None,
        language_detected="UNKNOWN",
        language_probability=None,
    )
    # Both supported tools decode at 16 kHz mono (TXE-001); the clock is never source-exact.
    clock = AudioClock(16000, True, True, source.offset_ms)
    function = ingest_faster_whisper if source.tool is AsrTool.FASTER_WHISPER else ingest_whisperx
    try:
        return function(
            payload,
            evidence_id="web-" + raw_sha[:16],
            source_ref=facts.media_id,
            producer=producer,
            clock=clock,
        )
    except TranscriptIngestError as exc:
        raise PipelineError(
            "전사 JSON을 받아들일 수 없습니다 (형식 또는 값 오류). 선택한 ASR 도구와 파일이 맞는지 확인하세요.",
            (exc.code.value, exc.detail[:200]),
        ) from exc


# --------------------------------------------------------------------------- candidates


@dataclass(frozen=True)
class CandidateRow:
    kind: CandidateKind
    frame_range: FrameRange | None  # source == timeline frames (one clip at frame 0)
    words: str
    reason: str  # short single-line marker reason
    detail: str  # ambiguity / policy explanation
    candidate_id: str | None = None  # None: shown but not written as a marker
    not_marked: str = ""


@dataclass(frozen=True)
class ProjectBuild:
    facts: MediaFacts
    policy: CandidatePolicy
    snapshot: TranscriptSnapshot
    handoff: CandidateHandoff
    rows: tuple[CandidateRow, ...]
    srt_text: str
    srt_diagnostics: tuple[HandoffDiagnostic, ...]
    projection_issue_count: int
    unavailable_segment_count: int


def _short(text: str, limit: int = 24) -> str:
    cleaned = clean_text(text, 200)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"


def _reason(text: str) -> str:
    return clean_text(text, MAX_REASON_CHARS)


def _seconds_text(frames: int, rate: FrameRate) -> str:
    value = frames_to_seconds(frames, rate)
    millis = (value.numerator * 1000) // value.denominator
    return f"{millis // 1000}.{millis % 1000:03d}"


def _frames_floor(ms: int, rate: FrameRate) -> int:
    return math.floor(Fraction(ms) * Fraction(rate.numerator, rate.denominator) / 1000)


def _frames_ceil(ms: int, rate: FrameRate) -> int:
    return math.ceil(Fraction(ms) * Fraction(rate.numerator, rate.denominator) / 1000)


def _candidate_rows(
    snapshot: TranscriptSnapshot,
    policy: CandidatePolicy,
    facts: MediaFacts,
    blocked: tuple[FrameRange, ...],
) -> list[CandidateRow]:
    rate = facts.rate
    korean = produce_korean_text_candidates(
        snapshot, KoreanTextCandidatePolicy(policy.max_repetition_gap_frames)
    )
    rows: list[CandidateRow] = []
    for rep in korean.repetitions:
        first, second = snapshot.word(rep.word_refs[0]), snapshot.word(rep.word_refs[1])
        words = f"{first.text.strip()} {second.text.strip()}"
        reason = _reason(f"반복 후보 '{_short(words)}' ({rep.kind.value}, 모호)")
        if first.source_range is None or second.source_range is None:
            rows.append(
                CandidateRow(
                    CandidateKind.REPETITION,
                    None,
                    words,
                    reason,
                    rep.note,
                    not_marked="단어 타이밍 없음 - 마커로 만들지 않음",
                )
            )
            continue
        start, end = first.source_range.frames.start, second.source_range.frames.start
        rows.append(
            CandidateRow(
                CandidateKind.REPETITION,
                FrameRange(start, end) if end > start else None,
                words,
                reason,
                rep.note + " (앞 단어부터 다음 단어 시작까지)",
                not_marked="" if end > start else "길이 0 - 마커로 만들지 않음",
            )
        )
    for hit in korean.filler_hits:
        word = snapshot.word(hit.word_ref)
        reason = _reason(f"필러 후보 '{_short(hit.form)}' (어휘 일치, 모호)")
        rows.append(
            CandidateRow(
                CandidateKind.FILLER,
                None if word.source_range is None else word.source_range.frames,
                word.text.strip(),
                reason,
                f"{hit.note} [{hit.lexicon_version}]",
                not_marked="" if word.source_range else "단어 타이밍 없음 - 마커로 만들지 않음",
            )
        )
    previous = None
    for word in snapshot.words:
        if word.kind is not TranscriptTokenKind.WORD or word.source_range is None:
            previous = None
            continue
        if previous is not None and previous.source_range is not None:
            gap = word.source_range.frames.start - previous.source_range.frames.end
            if gap >= policy.gap_threshold_frames:
                start = previous.source_range.frames.end + policy.gap_padding_frames
                end = word.source_range.frames.start - policy.gap_padding_frames
                words = f"{previous.text.strip()} … {word.text.strip()}"
                reason = _reason(
                    f"전사 공백 {_seconds_text(gap, rate)}초 (음향 무음 아님, 단어 타이밍 기준)"
                )
                detail = (
                    f"단어 사이 전사 공백 {gap}프레임 ≥ 기준 {policy.gap_threshold_frames}프레임; "
                    f"양쪽 {policy.gap_padding_frames}프레임 여유 유지. 소리를 분석한 무음이 아닙니다."
                )
                span = FrameRange(start, end) if end > start else None
                not_marked = "" if span else "여유를 빼면 길이 0 - 마커로 만들지 않음"
                if span is not None and any(span.overlaps(b) for b in blocked):
                    not_marked = "단어 타이밍이 없는 전사 구간과 겹침 - 마커로 만들지 않음"
                rows.append(
                    CandidateRow(
                        CandidateKind.TRANSCRIPT_GAP,
                        span,
                        words,
                        reason,
                        detail,
                        not_marked=not_marked,
                    )
                )
        previous = word
    media = FrameRange(0, facts.duration_frames)
    accepted: list[FrameRange] = []
    resolved: list[CandidateRow] = []
    for row in rows:  # priority: repetition > filler > transcript gap (insertion order)
        if row.not_marked or row.frame_range is None:
            resolved.append(row)
            continue
        if not media.contains(row.frame_range):
            resolved.append(_unmarked(row, "미디어 길이 밖 - 마커로 만들지 않음"))
        elif any(row.frame_range.overlaps(a) for a in accepted):
            resolved.append(_unmarked(row, "다른 후보와 겹침 - 한 후보로만 표시"))
        else:
            accepted.append(row.frame_range)
            resolved.append(row)
    marked = sorted(
        (r for r in resolved if not r.not_marked and r.frame_range is not None),
        key=lambda r: r.frame_range.start if r.frame_range else 0,
    )
    ids = {id(r): f"AIE-{n:04d}" for n, r in enumerate(marked, start=1)}
    final = [
        CandidateRow(
            r.kind, r.frame_range, r.words, r.reason, r.detail, ids.get(id(r)), r.not_marked
        )
        for r in resolved
    ]
    return sorted(
        final,
        key=lambda r: (
            r.candidate_id is None,
            r.frame_range.start if r.frame_range else 0,
            r.kind.value,
        ),
    )


def _unmarked(row: CandidateRow, why: str) -> CandidateRow:
    return CandidateRow(row.kind, row.frame_range, row.words, row.reason, row.detail, None, why)


def base_timeline(facts: MediaFacts) -> HandoffTimeline:
    media = HandoffMediaRef(
        facts.media_id,
        facts.media_path,
        FrameRange(0, facts.duration_frames),
        facts.media_start_frame,
    )
    source = FrameRange(0, facts.duration_frames)
    video = HandoffTrack(
        "V1", HandoffTrackKind.VIDEO, (HandoffClip(facts.clip_name, media, source),)
    )
    audio = HandoffTrack(
        "A1", HandoffTrackKind.AUDIO, (HandoffClip(facts.clip_name, media, source),)
    )
    return HandoffTimeline(
        facts.timeline_name, facts.rate, facts.timeline_start_frame, (video, audio)
    )


def build_project(raw: bytes, source: TranscriptSource, facts: MediaFacts) -> ProjectBuild:
    payload = parse_transcript_json(raw)
    raw_sha = hashlib.sha256(raw).hexdigest()
    evidence = ingest(payload, source, facts, raw_sha)
    policy = candidate_policy(source, facts.rate, evidence.resolution_ms)
    projection = project_to_source_frames(
        evidence,
        frame_rate=Fraction(facts.rate.numerator, facts.rate.denominator),
        source_offset_frames=0,
        tolerance_frames=policy.tolerance_frames,
        transcript_id="tx-" + raw_sha[:16],
    )
    blocked: list[FrameRange] = []
    unavailable = 0
    issues = 0
    for diag in projection.diagnostics:
        if diag.code is ProjectionDiagnosticCode.SEGMENT_WORDS_UNAVAILABLE:
            unavailable += 1
            if diag.start_ms is not None and diag.end_ms is not None:
                start = _frames_floor(source.offset_ms + diag.start_ms, facts.rate)
                end = _frames_ceil(source.offset_ms + diag.end_ms, facts.rate)
                if end > start:
                    blocked.append(FrameRange(start, end))
        else:
            issues += 1
    rows = _candidate_rows(projection.snapshot, policy, facts, tuple(blocked))
    cuts = [
        CutCandidate(r.candidate_id, r.frame_range, r.reason)
        for r in rows
        if r.candidate_id is not None and r.frame_range is not None
    ]
    try:
        handoff = attach_candidate_markers(base_timeline(facts), cuts)
    except ValueError as exc:
        raise PipelineError("후보 마커를 만들 수 없습니다.", (str(exc)[:200],)) from exc
    cues = []
    for seg in evidence.segments:
        start = _frames_floor(source.offset_ms + seg.start_ms, facts.rate)
        end = _frames_ceil(source.offset_ms + seg.end_ms, facts.rate)
        if end > start and seg.text.strip():
            cues.append(HandoffSubtitleCue(FrameRange(start, end), seg.text.strip()))
    srt = write_srt(cues, facts.rate)
    return ProjectBuild(
        facts,
        policy,
        projection.snapshot,
        handoff,
        tuple(rows),
        srt.text,
        srt.diagnostics,
        issues,
        unavailable,
    )


# --------------------------------------------------------------------------- downloads


def candidate_xml(build: ProjectBuild) -> str:
    result = write_xmeml(build.handoff.timeline)
    if result.text is None:
        raise PipelineError(
            "FCP7 XML을 만들 수 없습니다.", tuple(d.code.value for d in result.diagnostics)
        )
    return result.text


def candidate_otio(build: ProjectBuild) -> str:
    profile = (
        OtioProfile.RESOLVE_SHAPED
        if build.facts.profile is Profile.RESOLVE
        else OtioProfile.DEFAULT
    )
    result = write_otio(build.handoff.timeline, profile)
    if result.text is None:
        raise PipelineError(
            "OTIO 파일을 만들 수 없습니다.", tuple(d.code.value for d in result.diagnostics)
        )
    return result.text


def timecode(facts: MediaFacts, frame: int) -> str:
    return frames_to_timecode(facts.timeline_start_frame + frame, facts.rate)


def seconds(frames: int, rate: FrameRate) -> str:
    return _seconds_text(frames, rate)


# --------------------------------------------------------------------------- approval


def decode_xml(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PipelineError("XML 파일은 UTF-8이어야 합니다.", ("NOT_UTF8",)) from exc


def _read(text: str, max_chars: int) -> XmemlReadResult:
    result = read_xmeml(text, max_chars=max_chars)
    if result.timeline is None:
        codes = tuple(
            f"{d.code.value} @ {d.location}"
            for d in result.diagnostics
            if d.severity is HandoffSeverity.REFUSAL
        )
        raise PipelineError(
            "FCP7 XML을 읽을 수 없습니다. Resolve에서 File > Export > Timeline… 의 "
            "FCP 7 XML (.xml) 형식으로 내보낸 파일인지 확인하세요.",
            codes[:10],
        )
    return result


@dataclass(frozen=True)
class ApprovalView:
    selection: MarkerSelectionSet
    diff: RoundTripDiff
    confirmation: ApplyConfirmation
    unknown_region_count: int


def build_approval(build: ProjectBuild, text: str, max_chars: int) -> ApprovalView:
    result = _read(text, max_chars)
    timeline = result.timeline
    if timeline is None:  # pragma: no cover - _read refuses
        raise PipelineError("FCP7 XML을 읽을 수 없습니다.")
    artifact = roundtrip_artifact_ref("approval-export.xml", text, RoundTripFormat.XMEML)
    diff = diff_xmeml_roundtrip(build.handoff.timeline, result, artifact_ref=artifact)
    selection = read_marker_selections(timeline, build.handoff.candidates)
    try:
        confirmation = build_apply_confirmation(selection, build.handoff.timeline, diff)
    except ValueError as exc:
        raise PipelineError(
            "확인 요약을 만들 수 없습니다 (입력이 서로 맞지 않음).", (str(exc)[:200],)
        ) from exc
    return ApprovalView(selection, diff, confirmation, len(result.unknown_regions))


def apply(view: ApprovalView, digest: str) -> AppliedTimeline:
    try:
        return apply_approved_cuts(view.confirmation, confirmed_digest=digest)
    except ApplyRefused as exc:
        raise PipelineError(
            "확인 코드가 현재 확인 요약과 일치하지 않습니다. 아무것도 적용하지 않았습니다. "
            "확인 페이지를 다시 열어 내용을 확인한 뒤 다시 누르세요.",
            ("APPLY_REFUSED",),
        ) from exc


def applied_xml(applied: AppliedTimeline) -> str:
    result = write_xmeml(applied.timeline)
    if result.text is None:
        raise PipelineError(
            "적용된 FCP7 XML을 만들 수 없습니다.", tuple(d.code.value for d in result.diagnostics)
        )
    return result.text


def diff_is_unknown(diff: RoundTripDiff) -> bool:
    return diff.status is DiffStatus.UNKNOWN


# --------------------------------------------------------------------------- verification


def verify(
    applied: AppliedTimeline, text: str, provenance: ActualProvenance, max_chars: int
) -> VerificationReport:
    result = _read(text, max_chars)
    artifact = roundtrip_artifact_ref("reexport.xml", text, RoundTripFormat.XMEML)
    diff = diff_xmeml_roundtrip(applied.timeline, result, artifact_ref=artifact)
    return verify_roundtrip(applied.revision, applied.timeline, diff, provenance=provenance)


__all__ = [
    "KIND_LABELS_KO",
    "RATE_CHOICES",
    "SKIP_LABELS_KO",
    "ApprovalView",
    "AsrTool",
    "CandidateKind",
    "CandidatePolicy",
    "CandidateRow",
    "MediaFacts",
    "PipelineError",
    "Profile",
    "ProjectBuild",
    "TranscriptSource",
    "applied_xml",
    "apply",
    "build_approval",
    "build_project",
    "candidate_otio",
    "candidate_xml",
    "decode_xml",
    "parse_frame_or_timecode",
    "parse_rate",
    "verify",
]
