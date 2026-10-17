"""Frame-domain transcript words: producer output, never editorial meaning.

A transcript is evidence produced by an external ASR tool on its own clock
(typically resampled/downmixed 16 kHz audio). Its word timings are therefore
approximate with respect to source frames: every projection carries an explicit
tolerance and a timing status, and a word whose timing is unknown keeps
``source_range=None`` instead of an invented range.

Nothing here emits PauseBoundaryKind, PauseSignal, ContentMode or any filler /
hesitation / breath label (OPEN-009 stays open).
"""

import unicodedata
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

from .temporal_mapping import SourceFrameRange


class WordTimingStatus(str, Enum):
    """How the producer obtained a word's timing (not how accurate it is)."""

    ALIGNED = "ALIGNED"
    HEURISTIC_ADJUSTED = "HEURISTIC_ADJUSTED"
    INTERPOLATED = "INTERPOLATED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class TranscriptTokenKind(str, Enum):
    WORD = "WORD"
    AUDIO_EVENT = "AUDIO_EVENT"
    UNKNOWN = "UNKNOWN"


TIMED_STATUSES = frozenset(
    {
        WordTimingStatus.ALIGNED,
        WordTimingStatus.HEURISTIC_ADJUSTED,
        WordTimingStatus.INTERPOLATED,
    }
)


def _nonblank(value: object, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class TranscriptWord:
    """One producer token projected onto source frames.

    ``text`` is stored NFC-normalized exactly as produced (no lowercasing, no
    punctuation stripping); derived keys belong to consumers.
    """

    word_ref: str
    text: str
    source_range: SourceFrameRange | None
    timing_status: WordTimingStatus
    kind: TranscriptTokenKind = TranscriptTokenKind.WORD
    speaker_ref: str | None = None

    def __post_init__(self) -> None:
        _nonblank(self.word_ref, "Explicit word reference required")
        text = _nonblank(self.text, "Nonblank token text required")
        object.__setattr__(self, "text", unicodedata.normalize("NFC", text))
        if not isinstance(self.timing_status, WordTimingStatus):
            raise TypeError("Typed timing status required")
        if not isinstance(self.kind, TranscriptTokenKind):
            raise TypeError("Typed token kind required")
        if self.source_range is not None and not isinstance(self.source_range, SourceFrameRange):
            raise TypeError("Source-frame range or explicit None required")
        timed = self.timing_status in TIMED_STATUSES
        if timed != (self.source_range is not None):
            raise ValueError("Timed status requires a range; MISSING/UNKNOWN forbid one")
        if self.speaker_ref is not None:
            _nonblank(self.speaker_ref, "Speaker reference must be nonblank when present")

    @property
    def is_timed(self) -> bool:
        return self.source_range is not None


@dataclass(frozen=True)
class TranscriptSnapshot:
    """Ordered producer tokens for one source, bound to a producer evidence ref.

    Timed words must be ordered and nonoverlapping in source frames; untimed
    words keep their producer order. ``timing_tolerance_frames`` states how far
    any timed boundary may be from the true acoustic boundary (clock mismatch,
    rounding); consumers must not treat transcript boundaries as exact.
    """

    transcript_id: str
    source_ref: str
    producer_ref: str
    timing_tolerance_frames: int
    words: tuple[TranscriptWord, ...]

    def __post_init__(self) -> None:
        for value, message in (
            (self.transcript_id, "Explicit transcript ID required"),
            (self.source_ref, "Explicit source reference required"),
            (self.producer_ref, "Explicit producer evidence reference required"),
        ):
            _nonblank(value, message)
        if type(self.timing_tolerance_frames) is not int or self.timing_tolerance_frames < 0:
            raise ValueError("Nonnegative integer timing tolerance required")
        object.__setattr__(self, "words", tuple(self.words))
        if any(not isinstance(word, TranscriptWord) for word in self.words):
            raise TypeError("Typed transcript words required")
        refs = [word.word_ref for word in self.words]
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate word reference")
        timed = [word.source_range.frames for word in self.words if word.source_range is not None]
        if any(a.end > b.start for a, b in pairwise(timed)):
            raise ValueError("Timed words must be ordered and nonoverlapping")

    def word(self, word_ref: str) -> TranscriptWord:
        for word in self.words:
            if word.word_ref == word_ref:
                return word
        raise KeyError(word_ref)

    @property
    def timed_words(self) -> tuple[TranscriptWord, ...]:
        return tuple(word for word in self.words if word.is_timed)
