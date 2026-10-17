"""LLM-001: ID-only transcript context views (producer evidence -> prompt text).

A :class:`TranscriptContextView` groups transcript words into numbered segments
(``S0001``...) and renders one line per segment, e.g.::

    S0007 sp1 gap=18f | 그러니까 이 장면은

The rendered text deliberately carries NO timestamps, frame numbers, word refs,
producer refs or file names. An LLM reading it can therefore only point back at
segment IDs; every frame coordinate stays on the deterministic side of the
boundary (ADR-006). The gap value is a relative pacing hint between segments,
never an addressable coordinate.

The view digest is a SHA-256 over the full binding (transcript identity,
producer ref, tolerance, policy, every word's timing/kind/speaker/text, the
segments and the rendered text), so any producer re-run, re-timing or policy
change yields a different view and a stale LLM proposal can be detected.

Phrase grouping on silence/speaker change is a concept also used by the MIT
licensed ``video-use`` helper ``pack_transcripts.py``; no code was copied.
Nothing here labels fillers, pauses or editorial meaning (OPEN-009 stays open).
"""

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass

from .domain import FrameRange
from .transcript import TranscriptSnapshot, TranscriptTokenKind, TranscriptWord

CONTEXT_CONTRACT_VERSION = "llm-001-context-v1"
SEGMENT_ID_PATTERN = re.compile(r"^S[0-9]{4,}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _nonblank(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value


def _positive_int(value: object, message: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(message)
    return value


def segment_id_for(index: int) -> str:
    """Zero-based segment index -> stable display ID (``0 -> S0001``)."""

    if type(index) is not int or index < 0:
        raise ValueError("Nonnegative integer segment index required")
    return f"S{index + 1:04d}"


@dataclass(frozen=True)
class ContextPolicy:
    """Deterministic grouping policy. Frames are source frames of the snapshot."""

    break_gap_frames: int
    max_segment_words: int

    def __post_init__(self) -> None:
        _positive_int(self.break_gap_frames, "Positive integer break gap required")
        _positive_int(self.max_segment_words, "Positive integer max segment words required")

    @property
    def policy_ref(self) -> str:
        return (
            f"{CONTEXT_CONTRACT_VERSION}:gap={self.break_gap_frames}:max={self.max_segment_words}"
        )


@dataclass(frozen=True)
class ContextSegment:
    """A contiguous run of transcript words. Either fully timed or fully untimed.

    ``range`` spans the segment's timed words; it is ``None`` for an untimed
    segment. ``gap_before_frames`` is ``None`` for the first segment and
    whenever either side of the junction is untimed. ``speaker_ref`` is set only
    when every word carries the same speaker.
    """

    segment_id: str
    word_refs: tuple[str, ...]
    range: FrameRange | None
    gap_before_frames: int | None
    speaker_ref: str | None
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.segment_id, str) or not SEGMENT_ID_PATTERN.match(self.segment_id):
            raise ValueError("Segment ID must look like S0001")
        refs = tuple(self.word_refs)
        if not refs:
            raise ValueError("Segment requires at least one word reference")
        for ref in refs:
            _nonblank(ref, "Nonblank word reference required")
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate word reference in segment")
        object.__setattr__(self, "word_refs", refs)
        if self.range is not None and not isinstance(self.range, FrameRange):
            raise TypeError("Segment range must be a FrameRange or None")
        if self.gap_before_frames is not None:
            if type(self.gap_before_frames) is not int or self.gap_before_frames < 0:
                raise ValueError("Gap must be a nonnegative integer or None")
            if self.range is None:
                raise ValueError("Untimed segment cannot carry a gap")
        if self.speaker_ref is not None:
            _nonblank(self.speaker_ref, "Speaker reference must be nonblank when present")
        _nonblank(self.text, "Segment text required")


@dataclass(frozen=True)
class TranscriptContextView:
    """Immutable prompt context bound to one transcript snapshot and policy."""

    view_id: str
    transcript_id: str
    producer_ref: str
    policy_ref: str
    segments: tuple[ContextSegment, ...]
    rendered_text: str
    view_digest: str

    def __post_init__(self) -> None:
        for value, message in (
            (self.view_id, "Explicit view ID required"),
            (self.transcript_id, "Explicit transcript ID required"),
            (self.producer_ref, "Explicit producer reference required"),
            (self.policy_ref, "Explicit policy reference required"),
        ):
            _nonblank(value, message)
        segments = tuple(self.segments)
        if any(not isinstance(s, ContextSegment) for s in segments):
            raise TypeError("Typed context segments required")
        if tuple(s.segment_id for s in segments) != tuple(
            segment_id_for(i) for i in range(len(segments))
        ):
            raise ValueError("Segment IDs must be sequential from S0001")
        refs = [ref for s in segments for ref in s.word_refs]
        if len(set(refs)) != len(refs):
            raise ValueError("A word may belong to only one segment")
        object.__setattr__(self, "segments", segments)
        if not isinstance(self.rendered_text, str):
            raise TypeError("Rendered text must be a string")
        if len(self.rendered_text.splitlines()) != len(segments):
            raise ValueError("Rendered text must have exactly one line per segment")
        if not isinstance(self.view_digest, str) or not _HEX64.match(self.view_digest):
            raise ValueError("View digest must be lowercase SHA-256 hex")

    def segment_index(self, segment_id: str) -> int | None:
        """Zero-based position of ``segment_id`` or ``None`` when unknown."""

        if not isinstance(segment_id, str) or not SEGMENT_ID_PATTERN.match(segment_id):
            return None
        index = int(segment_id[1:]) - 1
        if 0 <= index < len(self.segments) and self.segments[index].segment_id == segment_id:
            return index
        return None


def _display_text(word: TranscriptWord) -> str:
    # Collapse all whitespace (incl. newlines) and drop control/format chars so a
    # producer token can never forge a new line, a fake segment or a field.
    cleaned = "".join(
        " " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else ch
        for ch in word.text
        if unicodedata.category(ch) != "Cf"
    )
    text = " ".join(cleaned.split()).replace("|", "¦")
    if not text:
        text = "?"
    if word.kind == TranscriptTokenKind.AUDIO_EVENT:
        return f"[{text}]"
    if word.kind == TranscriptTokenKind.UNKNOWN:
        return f"<{text}>"
    return text


def _group(snapshot: TranscriptSnapshot, policy: ContextPolicy) -> list[list[TranscriptWord]]:
    groups: list[list[TranscriptWord]] = []
    current: list[TranscriptWord] = []
    for word in snapshot.words:
        if current:
            prev = current[-1]
            breaks = (
                len(current) >= policy.max_segment_words
                or prev.speaker_ref != word.speaker_ref
                or prev.is_timed != word.is_timed
            )
            if not breaks and prev.source_range is not None and word.source_range is not None:
                gap = word.source_range.frames.start - prev.source_range.frames.end
                breaks = gap >= policy.break_gap_frames
            if breaks:
                groups.append(current)
                current = []
        current.append(word)
    if current:
        groups.append(current)
    return groups


def _canonical_digest(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _word_payload(word: TranscriptWord) -> dict[str, object]:
    frames = word.source_range.frames if word.source_range is not None else None
    return {
        "ref": word.word_ref,
        "text": word.text,
        "range": None if frames is None else [frames.start, frames.end],
        "timing": word.timing_status.value,
        "kind": word.kind.value,
        "speaker": word.speaker_ref,
    }


def render_transcript_context(
    snapshot: TranscriptSnapshot, policy: ContextPolicy
) -> TranscriptContextView:
    """Group words into ID-only segments and render prompt lines. Pure function."""

    if not isinstance(snapshot, TranscriptSnapshot):
        raise TypeError("Typed transcript snapshot required")
    if not isinstance(policy, ContextPolicy):
        raise TypeError("Typed context policy required")
    if not snapshot.words:
        raise ValueError("Transcript has no words to render")

    speaker_alias: dict[str, str] = {}
    segments: list[ContextSegment] = []
    lines: list[str] = []
    prev_range: FrameRange | None = None
    for index, words in enumerate(_group(snapshot, policy)):
        timed = words[0].is_timed
        seg_range: FrameRange | None = None
        gap: int | None = None
        if timed:
            first = words[0].source_range
            last = words[-1].source_range
            assert first is not None and last is not None
            seg_range = FrameRange(first.frames.start, last.frames.end)
            if prev_range is not None:
                gap = seg_range.start - prev_range.end
        speakers = {w.speaker_ref for w in words}
        speaker = words[0].speaker_ref if len(speakers) == 1 else None
        text = " ".join(_display_text(w) for w in words)
        segment = ContextSegment(
            segment_id_for(index),
            tuple(w.word_ref for w in words),
            seg_range,
            gap,
            speaker,
            text,
        )
        segments.append(segment)
        if speaker is None:
            label = "sp?"
        else:
            label = speaker_alias.setdefault(speaker, f"sp{len(speaker_alias) + 1}")
        if not timed:
            gap_label = "? untimed"
        elif index == 0:
            gap_label = "-"
        elif gap is None:
            gap_label = "?"
        else:
            gap_label = f"{gap}f"
        lines.append(f"{segment.segment_id} {label} gap={gap_label} | {text}")
        prev_range = seg_range
    rendered = "\n".join(lines)
    payload = {
        "contract": CONTEXT_CONTRACT_VERSION,
        "transcript_id": snapshot.transcript_id,
        "source_ref": snapshot.source_ref,
        "producer_ref": snapshot.producer_ref,
        "timing_tolerance_frames": snapshot.timing_tolerance_frames,
        "policy_ref": policy.policy_ref,
        "words": [_word_payload(w) for w in snapshot.words],
        "segments": [
            {
                "id": s.segment_id,
                "word_refs": list(s.word_refs),
                "range": None if s.range is None else [s.range.start, s.range.end],
                "gap": s.gap_before_frames,
                "speaker": s.speaker_ref,
                "text": s.text,
            }
            for s in segments
        ],
        "rendered_text": rendered,
    }
    digest = _canonical_digest(payload)
    return TranscriptContextView(
        view_id=f"ctxv-{digest[:16]}",
        transcript_id=snapshot.transcript_id,
        producer_ref=snapshot.producer_ref,
        policy_ref=policy.policy_ref,
        segments=tuple(segments),
        rendered_text=rendered,
        view_digest=digest,
    )


def view_matches(
    view: TranscriptContextView, snapshot: TranscriptSnapshot, policy: ContextPolicy
) -> bool:
    """True only when re-rendering ``snapshot`` under ``policy`` reproduces ``view``."""

    if not isinstance(view, TranscriptContextView):
        raise TypeError("Typed context view required")
    return render_transcript_context(snapshot, policy) == view
